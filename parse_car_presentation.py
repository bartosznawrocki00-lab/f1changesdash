"""Parser dokumentu FIA 'Car Presentation Submissions' (bez LLM).

Format: strona okładki, potem dla każdego zespołu strona z nagłówkiem
'Car Presentation – <GP>' + nazwa zespołu + tabela (albo 'No updates...') + strona z rysunkiem.
"""
import io
import re

import pdfplumber

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


def _rows_from_tables(tables) -> list[dict]:
    """Kolumny: 0 = nr, 1-3 = komponent, 4-6 = powód, 7-9 = zmiana geometrii, 10+ = opis.
    Wiersze bez numeru to kolejne linie opisu poprzedniego wiersza."""
    out = []
    for table in tables:
        for row in table:
            if len(row) < 10:          # śmieciowe pod-tabele
                continue
            first = (row[0] or "").strip()
            if first.isdigit():
                out.append({
                    "component": _clean(*row[1:4]),
                    "reason": _clean(*row[4:7]),
                    "change_detail": _clean(*row[7:10]),
                    "description": _clean(*row[10:]),
                })
            elif out and not first and not any(row[1:10]):
                out[-1]["description"] = _clean(out[-1]["description"], *row[10:])
    for prev, cur in zip(out, out[1:]):   # scalona komórka opisu obejmuje dwa wiersze
        if not cur["description"]:
            cur["description"] = prev["description"]
    return out


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
                current = {"team": short_team(lines[1]), "raw_team": lines[1],
                           "updates": [], "needs_llm": False, "text": ""}
                teams.append(current)
            elif current is None:             # okładka
                continue
            current["text"] += "\n" + text
            tables = page.extract_tables()
            rows = _rows_from_tables(tables)
            if rows:
                current["updates"] += rows
            elif not re.search(r"\bno updates?\b", text, re.I):
                current["needs_llm"] = True   # strona z treścią, ale nierozpoznanym układem
    for t in teams:
        if any(not u["component"] for u in t["updates"]):
            t["needs_llm"] = True
    return {"year": year, "grand_prix": gp, "teams": teams}
