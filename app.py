"""Dashboard Streamlit: zmiany w bolidach, weekend po weekendzie."""
import pandas as pd
import streamlit as st

import db

st.set_page_config(page_title="F1 – zmiany w bolidach", page_icon="🏎️", layout="wide")
db.init()


@st.cache_data(ttl=300)
def load():
    with db.connect() as c:
        up = pd.read_sql_query("SELECT rowid AS seq, * FROM upgrades", c).fillna("")
        subs = pd.read_sql_query("SELECT rowid AS seq, * FROM submissions", c)
    return up, subs


df, subs = load()
st.title("🏎️ Zmiany w bolidach F1 – weekend po weekendzie")

if df.empty and subs.empty:
    st.info("Baza jest pusta. Uruchom `python update.py` (dane z FIA), "
            "`python ingest_pdf.py plik.pdf` (ręcznie pobrany dokument) lub `python seed_demo.py` (dane demo).")
    st.stop()

if df.is_demo.any():
    st.warning("Widzisz dane DEMO (fikcyjne). Usuń je: `python seed_demo.py --clear`.")

years = sorted(set(df.year) | set(subs.year), reverse=True)
year = st.sidebar.selectbox("Sezon", years)
season, season_subs = df[df.year == year], subs[subs.year == year]

# kolejność GP: wg kalendarza (fetch_fia.GP_SLUGS); nieznane na końcu, wg kolejności wczytania
from fetch_fia import GP_SLUGS

CALENDAR = [s.replace("_", " ").replace("-", " ").title() + " Grand Prix" for s in GP_SLUGS]
seen = season_subs.sort_values("seq").grand_prix.drop_duplicates().tolist()
seen += [g for g in season.sort_values("seq").grand_prix.drop_duplicates() if g not in seen]
gp_order = sorted(seen, key=lambda g: CALENDAR.index(g) if g in CALENDAR else len(CALENDAR) + seen.index(g))
gp = st.sidebar.selectbox("Grand Prix", gp_order[::-1])  # najnowsze na górze
teams = st.sidebar.multiselect("Zespoły", sorted(season.team.unique()))
components = st.sidebar.multiselect("Komponenty", sorted(season.component.unique()))

this_gp = season[season.grand_prix == gp]
if teams:
    this_gp = this_gp[this_gp.team.isin(teams)]
if components:
    this_gp = this_gp[this_gp.component.isin(components)]
no_change = season_subs[(season_subs.grand_prix == gp) & (season_subs.n_updates == 0)].team.tolist()

tab1, tab2, tab3 = st.tabs(["Ten weekend", "Cały sezon", "Historia zespołu"])

with tab1:
    st.subheader(gp)
    c1, c2, c3 = st.columns(3)
    c1.metric("Liczba zmian", len(this_gp))
    c2.metric("Zespoły ze zmianami", this_gp.team.nunique())
    c3.metric("Zespoły bez zmian", len(no_change) if no_change else "–")

    if this_gp.empty:
        st.write("Brak zmian dla wybranych filtrów.")
    for team, g in this_gp.groupby("team"):
        with st.container(border=True):
            st.markdown(f"### {team}")
            for _, r in g.iterrows():
                st.markdown(f"**{r.component}**" + (f" · _{r.reason}_" if r.reason else ""))
                if r.change_detail:
                    st.caption(f"Zmiana: {r.change_detail}")
                if r.description:
                    st.write(r.description)
                if r.source_url:
                    st.markdown(f"[źródło]({r.source_url})")
    if no_change:
        st.caption("Bez zmian w tym weekendzie: " + ", ".join(sorted(no_change)))

with tab2:
    st.subheader(f"Liczba zmian na zespół – sezon {year}")
    if season.empty:
        st.write("Brak danych.")
    else:
        pivot = (season.pivot_table(index="grand_prix", columns="team", values="id",
                                    aggfunc="count", fill_value=0)
                 .reindex(gp_order).fillna(0).astype(int))
        st.bar_chart(pivot)
        st.dataframe(pivot, width="stretch")

with tab3:
    all_teams = sorted(set(season.team) | set(season_subs.team))
    team = st.selectbox("Zespół", all_teams)
    hist = season[season.team == team].sort_values("seq")
    if hist.empty:
        st.write("Ten zespół nie zgłosił zmian w wczytanych weekendach.")
    else:
        st.dataframe(hist[["grand_prix", "component", "reason", "change_detail", "description"]],
                     width="stretch", hide_index=True)

latest = max(df.added_at.max() if not df.empty else "", "")
st.caption(f"Ostatnia aktualizacja bazy: {latest} UTC · dane: dokumenty FIA (Car Presentation Submissions)")
