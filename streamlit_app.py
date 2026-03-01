import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Voetbal AI", layout="wide")
st.title("⚽ Voetbal AI – Topcompetities (vandaag + morgen)")

API_KEY = st.secrets["API_KEY"]
BASE_URL = "https://v3.football.api-sports.io/"
HEADERS = {"x-apisports-key": API_KEY}

TOP_LEAGUES = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "Eredivisie": 88,
}

league_names = list(TOP_LEAGUES.keys())
selected = st.multiselect("Selecteer competities", league_names, default=league_names)

days_ahead = st.radio("Welke dagen?", ["Vandaag", "Morgen", "Vandaag + morgen"], index=2, horizontal=True)

def fetch_fixtures(date_str: str):
    r = requests.get(
        BASE_URL + "fixtures",
        headers=HEADERS,
        params={"date": date_str},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("response", [])

today = datetime.now().date()
tomorrow = today + timedelta(days=1)

dates = []
if days_ahead == "Vandaag":
    dates = [today]
elif days_ahead == "Morgen":
    dates = [tomorrow]
else:
    dates = [today, tomorrow]

selected_ids = {TOP_LEAGUES[name] for name in selected}

rows = []
for d in dates:
    date_str = d.strftime("%Y-%m-%d")
    fixtures = fetch_fixtures(date_str)

    for fx in fixtures:
        league_id = fx["league"]["id"]
        if league_id not in selected_ids:
            continue

        kickoff = fx["fixture"]["date"]  # ISO string
        rows.append(
            {
                "Datum": date_str,
                "Tijd": kickoff[11:16],
                "Competitie": fx["league"]["name"],
                "Wedstrijd": f"{fx['teams']['home']['name']} vs {fx['teams']['away']['name']}",
                "Status": fx["fixture"]["status"]["short"],
            }
        )

if rows:
    df = pd.DataFrame(rows).sort_values(["Datum", "Tijd", "Competitie"])
    st.success(f"{len(df)} wedstrijden gevonden")
    st.dataframe(df, use_container_width=True)
else:
    st.warning("Geen wedstrijden gevonden voor jouw selectie.")
