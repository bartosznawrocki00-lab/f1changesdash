"""Parser dokumentu FIA 'Car Presentation Submissions' (bez LLM).

Układ dokumentu: okładka; potem dla każdego zespołu strona z nagłówkiem 'Car Presentation – <GP>'
+ nazwa zespołu + tabela (albo 'No updates...'); przy dłuższych tabelach kolejne strony BEZ nagłówka;
na końcu strona z rysunkiem.

Komórki tabeli przypisujemy do pól (numer / komponent / powód / geometria / opis) po ich położeniu
poziomym, a nie po numerze kolumny siatki (ta bywa różna na różnych stronach). Scalone komórki
(jeden powód/opis dla kilku wierszy) są dziedziczone z wiersza powyżej.
"""
import io
import re

import pdfplumber

PARSER_VERSION = 2   # zwiększ po zmianie parsera: dokumenty zostaną wczytane ponownie

FIELDS = {1: "component", 2: "reason", 3: "change_detail", 4: "description"}
DEFAULT_EDGES = [73, 100, 179, 277, 531]   # lewe krawędzie kolumn na stronie szerokiej 842 pt

TEAM_MAP = [
    ("racing bulls", "Racing Bulls"), ("red bull", "Red Bull"), ("mclaren", "McLaren"),
    ("mercedes", "Mercedes"), ("ferrari", "Ferrari"), ("williams", "Williams"),
    ("aston martin", "Aston Martin"), ("haas", "Haas"), ("alpine", "Alpine"),
    ("audi", "Audi"), ("cadillac", "Cadillac"),
]


def short_team(name: str) -> str:
    low = name.lower()
    for key, short in TEAM_MAP:
        if key in low:
            return short
    return name.strip().title()


def _clean(*cells) -> str:
    return re.sub(r"\s+", " ", " ".join(c for c in cells if c)).strip()


def _event(text: str):
    m = re.search(r"(20\d{2})\s+([A-Za-z ]+?)\s+Grand Prix", text, re.I)
    return (int(m.group(1)), m.group(2).strip().title() + " Grand Prix") if m else (None, None)


def _main_table(page):
    tables = page.find_tables()
    if not tables:
        return None
    t = max(tables, key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1]))
    return t if (t.bbox[2] - t.bbox[0]) > 0.6 * page.width else None   # reszta to drobne pod-tabele


def _col(x0, edges):
    col = 0
    for k, e in enumerate(edges):
        if x0 >= e - 3:
            col = k
    return col


def _parse_table(page, table, state):
    ext = table.extract()
    rows = []
    for i, row in enumerate(table.rows):
        cells = []
        for j, bbox in enumerate(row.cells):
            if bbox is None or j >= len(ext[i]):
                continue
            txt = _clean(ext[i][j])
            if txt:
                cells.append((bbox[0], txt))
        rows.append(cells)

    if state["edges"] is None:   # krawędzie kolumn z pierwszego pełnego wiersza (5 komórek z numerem)
        for cells in rows:
            if len(cells) >= 5 and cells[0][1].isdigit():
                state["edges"] = [c[0] for c in cells[:5]]
                break
    edges = state["edges"] or [e * page.width / 842 for e in DEFAULT_EDGES]

    for cells in rows:
        if not cells:
            continue
        if cells[0][1].isdigit() and _col(cells[0][0], edges) == 0:      # nowy wiersz (zmiana)
            rec = {"num": int(cells[0][1]), "component": "", "reason": "", "change_detail": "", "description": ""}
            state["recs"].append(rec)
            state["cur"] = rec
            cells = cells[1:]
        elif state["cur"] is None:                                       # nagłówek tabeli
            continue
        for x0, txt in cells:                                            # także linie ciągłe opisu
            field = FIELDS.get(_col(x0, edges))
            if field:
                state["cur"][field] = _clean(state["cur"][field], txt)


def _finish(team):
    recs = team["state"]["recs"]
    for prev, cur in zip(recs, recs[1:]):    # scalone komórki: dziedzicz z wiersza powyżej
        for f in ("reason", "change_detail", "description"):
            if not cur[f]:
                cur[f] = prev[f]
    team["updates"] = [{k: v for k, v in r.items() if k != "num"} for r in recs]
    nums = [r["num"] for r in recs]
    incomplete = any(not (r["component"] and r["reason"] and r["description"]) for r in recs)
    team["needs_llm"] = team["needs_llm"] or incomplete or nums != list(range(1, len(nums) + 1))


def parse_pdf(pdf_bytes: bytes) -> dict:
    year = gp = None
    teams, current = [], None
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = (page.extract_text() or "").strip()
            if not text:                      # strony z samymi rysunkami
                continue
            if i == 0:
                year, gp = _event(text)
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if lines[0].lower().startswith("car presentation") and len(lines) > 1:
                current = {"team": short_team(lines[1]), "raw_team": lines[1], "updates": [],
                           "needs_llm": False, "text": "",
                           "state": {"recs": [], "edges": None, "cur": None}}
                teams.append(current)
            elif current is None:             # okładka
                continue
            current["text"] += "\n" + text
            table = _main_table(page)
            if table is not None:
                _parse_table(page, table, current["state"])
            elif not re.search(r"\bno updates?\b", text, re.I) and not current["state"]["recs"]:
                current["needs_llm"] = True   # strona z treścią, ale nierozpoznany układ
    for t in teams:
        _finish(t)
        if not t["updates"] and re.search(r"\bno updates?\b", t["text"], re.I):
            t["needs_llm"] = False
        elif not t["updates"]:
            t["needs_llm"] = True
    return {"year": year, "grand_prix": gp, "teams": teams}
