# F1 – dashboard zmian w bolidach

Automatycznie uzupełniany dashboard: dokumenty FIA → tekst z PDF → Claude → SQLite → Streamlit.

## Szybki start
```bash
pip install -r requirements.txt
python seed_demo.py          # dane DEMO, żeby zobaczyć wygląd
streamlit run app.py
```

## Prawdziwe dane z FIA
1. Wejdź na fia.com → Documents → Formula One → wybierz sezon. Skopiuj adres strony.
2. ```bash
   # FIA_DOCS_URL jest opcjonalne – adresy PDF-ów FIA mają stały schemat i są wyliczane automatycznie
   export ANTHROPIC_API_KEY="<twój klucz>"
   python seed_demo.py --clear
   python update.py
   ```
3. Automatyzacja: wypchnij projekt na GitHub, dodaj sekret `ANTHROPIC_API_KEY` i zmienną
   `FIA_DOCS_URL`; workflow `.github/workflows/update.yml` odpala się środa–sobota co 6 h.
   Hosting dashboardu: Streamlit Community Cloud (podłączasz repo).

## Ręczne wczytanie dokumentu (działa zawsze)
Pobierz PDF "Car Presentation Submissions" z fia.com i wpisz:
```bash
python ingest_pdf.py "2026_Singapore_Grand_Prix_-_Car_Presentation_Submissions.pdf"
```
Parser jest dopasowany do prawdziwego formatu FIA (przetestowany na GP Singapuru 2026) i **nie wymaga klucza API**.
Klucz jest potrzebny tylko awaryjnie, gdy FIA zmieni układ dokumentu.

## Plan B
Wpisy ręczne: `data/manual_upgrades.csv` z kolumnami
`year,grand_prix,team,component,description,source_url`.

## Do sprawdzenia / dostosowania
- `fetch_fia.py`: szuka linków PDF zawierających "car presentation" – dopasuj do realnej struktury strony FIA.
- `parse_car_presentation.py`: parser tabel FIA; `extract.py`: awaryjny odczyt przez Claude'a.
- Kolejność GP w dashboardzie = kolejność dodania do bazy (`update.py` przetwarza dokumenty od najstarszego).
