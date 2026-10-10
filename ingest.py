"""Wspólna logika: bajty PDF -> parser -> baza (z awaryjnym użyciem Claude'a)."""
import os

import db
from parse_car_presentation import parse_pdf


def ingest_pdf_bytes(pdf_bytes, source_url="", year=None, gp=None):
    parsed = parse_pdf(pdf_bytes)
    year, gp = year or parsed["year"], gp or parsed["grand_prix"]
    if not (year and gp and parsed["teams"]):
        raise ValueError("Nie rozpoznano formatu dokumentu.")

    rows, failed = [], []
    for t in parsed["teams"]:
        updates = t["updates"]
        if t["needs_llm"]:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                failed.append(t["team"])
                continue
            from extract import extract_upgrades
            updates = [{"component": i["component"], "reason": "", "change_detail": "",
                        "description": i["description"]} for i in extract_upgrades(t["text"])]
        for u in updates:
            rows.append({**u, "year": year, "grand_prix": gp, "team": t["team"], "source_url": source_url})
        db.upsert_submission(year, gp, t["team"], len(updates), source_url)

    new = db.upsert_upgrades(rows)
    return {"year": year, "grand_prix": gp, "teams": len(parsed["teams"]),
            "updates": len(rows), "new": new, "failed": failed}
