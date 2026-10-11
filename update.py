"""Główny skrypt aktualizacji: FIA -> PDF -> parser -> SQLite. Uruchamiany ręcznie lub cronem."""
import csv
from pathlib import Path

import db
from fetch_fia import download, list_documents
from ingest import ingest_pdf_bytes
from parse_car_presentation import PARSER_VERSION

MANUAL_CSV = Path(__file__).parent / "data" / "manual_upgrades.csv"


def import_manual():
    """Plan B: ręczne wpisy z CSV (kolumny: year,grand_prix,team,component,description,source_url)."""
    if not MANUAL_CSV.exists():
        return
    with open(MANUAL_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"CSV: {db.upsert_upgrades(rows)} nowych wpisów z {len(rows)}")


def main():
    db.init()
    import_manual()
    docs = list_documents()
    print(f"Sprawdzam {len(docs)} możliwych dokumentów…")
    found = 0
    for doc in docs:  # kolejność kalendarza = kolejność w dashboardzie
        if db.is_processed(doc["url"], PARSER_VERSION):
            continue
        try:
            pdf = download(doc["url"])
            if pdf is None:
                continue  # jeszcze nieopublikowany
            found += 1
            res = ingest_pdf_bytes(pdf, doc["url"], doc["year"], doc["grand_prix"])
            db.mark_processed(doc["url"], doc["grand_prix"], doc["year"], res["updates"], PARSER_VERSION)
            print(f"  {res['grand_prix']} {res['year']}: {res['updates']} zmian, {res['teams']} zespołów")
            if res["unread"] or res["warnings"]:
                print(f"    UWAGA – do sprawdzenia: nieodczytane={res['unread']} niepewne={res['warnings']}")
        except Exception as e:
            print(f"  BŁĄD przy {doc['url']}: {e}")
    print(f"Gotowe. Nowych dokumentów: {found}.")


if __name__ == "__main__":
    main()
