"""Dane DEMO (fikcyjne!), żeby od razu zobaczyć dashboard. Usuń: python seed_demo.py --clear"""
import sys
import db

DEMO = [
    ("Demo GP #1", "Ferrari", "Front wing", "Nowa konstrukcja końcówek skrzydła."),
    ("Demo GP #1", "McLaren", "Floor", "Zmodyfikowane krawędzie podłogi."),
    ("Demo GP #1", "Mercedes", "Cooling", "Przeprojektowane wloty chłodzenia."),
    ("Demo GP #2", "Ferrari", "Floor", "Nowy tunel podłogi."),
    ("Demo GP #2", "Red Bull", "Rear wing", "Lżejsza konstrukcja tylnego skrzydła."),
    ("Demo GP #2", "Williams", "Front wing", "Zmiana profilu klap."),
    ("Demo GP #2", "Audi", "Sidepods", "Nowy kształt wlotów bocznych."),
    ("Demo GP #3", "McLaren", "Rear wing", "Zmieniony profil górnej klapy."),
    ("Demo GP #3", "Cadillac", "Floor", "Pierwszy większy pakiet podłogi."),
    ("Demo GP #3", "Mercedes", "Front wing", "Korekta kąta klap."),
]

if __name__ == "__main__":
    db.init()
    if "--clear" in sys.argv:
        with db.connect() as c:
            c.execute("DELETE FROM upgrades WHERE is_demo=1")
        print("Usunięto dane demo.")
    else:
        rows = [dict(year=2026, grand_prix=g, team=t, component=c, description="[DEMO] " + d, is_demo=1)
                for g, t, c, d in DEMO]
        print(f"Dodano {db.upsert_upgrades(rows)} wierszy demo.")
