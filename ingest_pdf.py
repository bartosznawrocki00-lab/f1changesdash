"""Ręczne wczytanie pobranego PDF-a: python ingest_pdf.py plik.pdf [adres_źródła]"""
import sys

import db
from ingest import ingest_pdf_bytes

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Użycie: python ingest_pdf.py plik.pdf [adres_źródła]")
    db.init()
    with open(sys.argv[1], "rb") as f:
        res = ingest_pdf_bytes(f.read(), sys.argv[2] if len(sys.argv) > 2 else "")
    print(res)
