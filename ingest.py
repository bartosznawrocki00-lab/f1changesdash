"""Wspólna logika: bajty PDF -> parser -> baza (z awaryjnym użyciem Claude'a, jeśli jest klucz)."""
import os

import db
from parse_car_presentation import parse_pdf


def ingest_pdf_bytes(pdf_bytes, source_url="", year=None, gp=None):
    parsed = parse_pdf(pdf_bytes)
    year, gp = year or parsed["year"], gp or parsed["grand_prix"]
    if not (year and gp and parsed["teams"]):
        raise ValueError("Nie rozpoznano formatu dokumentu.")

    rows, subs, unread, warnings = [], [], [], []
    for t in parsed["teams"]:
        updates = t["updates"]
        if t["needs_llm"] and os.environ.get("ANTHROPIC_API_KEY"):
            try:
                from extract import extract_upgrades
                updates = [{"component": i["component"], "reason": "", "change_detail": "",
                            "description": i["description"]} for i in extract_upgrades(t["text"])]
            except Exception as e:
                warnings.append(f"{t['team']}: błąd odczytu przez LLM ({e})")
        elif t["needs_llm"]:
            (warnings if updates else unread).append(t["team"])
        for k, u in enumerate(updates, 1):
            rows.append({**u, "team": t["team"], "uid": f"{t['team']}#{k}"})
        subs.append((t["team"], -1 if (t["needs_llm"] and not updates) else len(updates)))

    db.replace_event(year, gp, rows, subs, source_url)
    return {"year": year, "grand_prix": gp, "teams": len(parsed["teams"]),
            "updates": len(rows), "unread": unread, "warnings": warnings}
