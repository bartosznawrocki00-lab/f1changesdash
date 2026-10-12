"""Tłumaczenie na polski.

* nazwy komponentów i powody zmian: słownik (deterministyczny, bez API, jednolita terminologia),
* opisy i różnice w geometrii: Claude (wymaga ANTHROPIC_API_KEY), wyniki w tabeli tr_cache,
  więc ten sam tekst nigdy nie jest tłumaczony dwa razy.
Bez klucza API opisy po prostu zostają po angielsku.
"""
import json
import os
import re

import db

MODEL = os.environ.get("TRANSLATE_MODEL", "claude-haiku-5-5")

COMPONENTS = {
    "front wing": "Przednie skrzydło",
    "front wing endplate": "Końcówka przedniego skrzydła",
    "rear wing": "Tylne skrzydło",
    "rear wing endplate": "Końcówka tylnego skrzydła",
    "beam wing": "Beam wing (dolne skrzydło tylne)",
    "nose": "Nos",
    "floor": "Podłoga",
    "floor body": "Korpus podłogi",
    "floor edge": "Krawędź podłogi",
    "floor body & diffuser": "Korpus podłogi i dyfuzor",
    "floor leading edge devices": "Elementy krawędzi natarcia podłogi",
    "diffuser": "Dyfuzor",
    "sidepod": "Pontony boczne",
    "sidepods": "Pontony boczne",
    "sidepod inlet": "Wlot pontonów bocznych",
    "coke/engine cover": "Pokrywa silnika (coke)",
    "cooling": "Chłodzenie",
    "cooling louvres": "Żaluzje chłodzące",
    "mirrors": "Lusterka",
    "halo": "Halo",
    "tail": "Tylna część nadwozia",
    "front suspension": "Przednie zawieszenie",
    "rear suspension": "Tylne zawieszenie",
    "front corner": "Przedni narożnik (koło, hamulce)",
    "rear corner": "Tylny narożnik (koło, hamulce)",
    "rear wheel bodywork": "Owiewki tylnego koła",
    "front wheel bodywork": "Owiewki przedniego koła",
}

REASON_PARTS = {
    "performance": "osiągi",
    "reliability": "niezawodność",
    "circuit specific": "specyficzne dla toru",
    "flow conditioning": "kondycjonowanie przepływu",
    "local load": "lokalne obciążenie aerodynamiczne",
    "drag reduction": "redukcja oporu",
    "brake cooling": "chłodzenie hamulców",
    "cooling range": "zakres chłodzenia",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("–", "-").replace("—", "-")).strip().lower()


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def translate_component(name: str) -> str:
    return COMPONENTS.get(_norm(name), "")


def translate_reason(reason: str) -> str:
    """'Performance - Flow Conditioning' -> 'Osiągi – kondycjonowanie przepływu' ('' gdy nieznane)."""
    parts = [p.strip() for p in re.split(r"\s+-\s+|\s*-\s*", _norm(reason)) if p.strip()]
    if not parts or any(p not in REASON_PARTS for p in parts):
        return ""
    return _cap(" – ".join(REASON_PARTS[p] for p in parts))


# ---------- Claude: opisy ----------
SYSTEM = (
    "You translate short technical texts from Formula 1 car-development documents from English into Polish. "
    "Use standard Polish motorsport terminology (floor=podłoga, diffuser=dyfuzor, front wing=przednie skrzydło, "
    "downforce=docisk, drag=opór, flow=przepływ, sidepod=ponton boczny, brake duct=kanał chłodzenia hamulca, "
    "louvres=żaluzje). Keep names, abbreviations and numbers unchanged (e.g. RIS, FW, SM). "
    "Translate faithfully and add nothing. The user message is a JSON array of strings; "
    "return ONLY a JSON array of the same length with the Polish translations, in the same order."
)


def _call_llm(strings: list[str]) -> list[str]:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL, max_tokens=4000, system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(strings, ensure_ascii=False)}],
    )
    raw = resp.content[0].text
    out = json.loads(raw[raw.find("["): raw.rfind("]") + 1])
    if len(out) != len(strings) or not all(isinstance(x, str) and x.strip() for x in out):
        raise ValueError("Nieprawidłowa odpowiedź tłumacza")
    return out


def fill_missing(batch_size: int = 12) -> dict:
    """Uzupełnia brakujące tłumaczenia w bazie. Bezpieczne do wielokrotnego uruchamiania."""
    db.init()
    stats = {"glossary": 0, "llm": 0, "failed": 0}

    with db.connect() as c:                                   # 1) słownik – zawsze, bez API
        rows = c.execute("SELECT id, component, reason, component_pl, reason_pl FROM upgrades "
                         "WHERE component_pl='' OR reason_pl=''").fetchall()
        for id_, comp, reason, comp_pl, reason_pl in rows:
            new_c = comp_pl or translate_component(comp)
            new_r = reason_pl or translate_reason(reason)
            if (new_c, new_r) != (comp_pl, reason_pl):
                c.execute("UPDATE upgrades SET component_pl=?, reason_pl=? WHERE id=?", (new_c, new_r, id_))
                stats["glossary"] += 1

    if not os.environ.get("ANTHROPIC_API_KEY"):               # 2) opisy – tylko z kluczem
        return stats
    with db.connect() as c:
        pending = [r[0] for r in c.execute(
            "SELECT description FROM upgrades WHERE is_demo=0 AND description!='' AND description_pl='' "
            "UNION SELECT change_detail FROM upgrades WHERE is_demo=0 AND change_detail!='' AND change_detail_pl=''")]
        cached = {r[0] for r in c.execute("SELECT src FROM tr_cache")}
    todo = [s for s in pending if s not in cached]
    for i in range(0, len(todo), batch_size):
        chunk = todo[i: i + batch_size]
        try:
            out = _call_llm(chunk)
        except Exception as e:
            print(f"  Tłumaczenie nie powiodło się dla {len(chunk)} tekstów: {e}")
            stats["failed"] += len(chunk)
            continue
        with db.connect() as c:
            c.executemany("INSERT OR REPLACE INTO tr_cache (src, pl) VALUES (?,?)", list(zip(chunk, out)))
        stats["llm"] += len(chunk)
    with db.connect() as c:
        for col in ("description", "change_detail"):
            c.execute(f"UPDATE upgrades SET {col}_pl = (SELECT pl FROM tr_cache WHERE src = upgrades.{col}) "
                      f"WHERE is_demo=0 AND {col}_pl='' AND EXISTS (SELECT 1 FROM tr_cache WHERE src = upgrades.{col})")
    return stats


if __name__ == "__main__":
    print(fill_missing())
