"""Pobieranie dokumentów 'Car Presentation Submissions' z fia.com.

Adresy FIA mają przewidywalny schemat, np.:
https://www.fia.com/system/files/decision-document/2026_singapore_grand_prix_-_car_presentation_submissions.pdf
więc dla każdego GP z kalendarza po prostu próbujemy pobrać taki adres (404 = jeszcze nie opublikowany).
Opcjonalnie (zmienna FIA_DOCS_URL) dodatkowo przeglądamy stronę z listą dokumentów.
"""
import os
import re
import time
from datetime import date
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "f1-upgrades-dashboard/1.0 (projekt studencki)"}
URL_TPL = ("https://www.fia.com/system/files/decision-document/"
           "{year}_{slug}_grand_prix_-_car_presentation_submissions.pdf")

# Kolejność = kalendarz (od tego zależy kolejność w dashboardzie). Nazwy, których FIA nie użyje,
# dadzą 404 i zostaną pominięte – dopisz/popraw w razie potrzeby.
GP_SLUGS = [
    "australian", "chinese", "japanese", "bahrain", "saudi_arabian", "miami", "canadian", "monaco",
    "barcelona-catalunya", "austrian", "british", "belgian", "hungarian", "dutch", "italian",
    "spanish", "azerbaijan", "singapore", "united_states", "mexico_city", "sao_paulo",
    "las_vegas", "qatar", "abu_dhabi",
]


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-]+", " ", unquote(s)).lower().strip()


def parse_event(text: str):
    """Z nazwy pliku wyciąga (rok, 'Japanese Grand Prix'). Zwraca (None, None), gdy się nie da."""
    m = re.search(r"(20\d{2}) ([a-z ]+?) grand prix", _norm(text))
    return (int(m.group(1)), m.group(2).title() + " Grand Prix") if m else (None, None)


def candidate_documents(year: int | None = None) -> list[dict]:
    year = year or int(os.environ.get("F1_YEAR", date.today().year))
    return [{"url": URL_TPL.format(year=year, slug=s), "year": year,
             "grand_prix": s.replace("_", " ").replace("-", " ").title() + " Grand Prix"}
            for s in GP_SLUGS]


def list_documents_from_page(page_url: str) -> list[dict]:
    """Opcjonalnie: linki z oficjalnej strony z dokumentami sezonu."""
    resp = requests.get(page_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    docs, seen = [], set()
    for a in BeautifulSoup(resp.text, "html.parser").find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        if href in seen or not href.lower().endswith(".pdf"):
            continue
        if "car presentation" not in _norm(a.get_text(" ", strip=True) + " " + href):
            continue
        year, gp = parse_event(href + " " + a.get_text(" ", strip=True))
        if gp:
            seen.add(href)
            docs.append({"url": href, "year": year, "grand_prix": gp})
    return docs


def list_documents() -> list[dict]:
    docs = candidate_documents()
    page = os.environ.get("FIA_DOCS_URL", "")
    if page:
        known = {d["url"].lower() for d in docs}
        try:
            docs += [d for d in list_documents_from_page(page) if d["url"].lower() not in known]
        except Exception as e:
            print(f"Uwaga: nie udało się przejrzeć FIA_DOCS_URL ({e}); używam samego schematu adresów.")
    return docs


def download(url: str) -> bytes | None:
    """Zwraca bajty PDF-a albo None, gdy dokument jeszcze nie istnieje (404)."""
    time.sleep(1)  # grzecznie wobec serwera
    r = requests.get(url, headers=HEADERS, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    if "pdf" not in r.headers.get("content-type", "").lower() and not r.content.startswith(b"%PDF"):
        return None
    return r.content
