import streamlit as st
import requests

st.title("⚽ Voetbal AI – Top Competities")

API_KEY = st.secrets["API_KEY"]

competities = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61
}

league = st.selectbox("Kies competitie", list(competities.keys()))

if st.button("Bekijk wedstrijden van vandaag"):
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"

    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    params = {
        "league": competities[league],
        "season": 2024,
        "date": "2024-03-01"
    }

    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    wedstrijden = data.get("response", [])

    if wedstrijden:
        for match in wedstrijden:
            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]
            st.write(f"⚽ {home} vs {away}")
    else:
        st.write("Geen wedstrijden gevonden.")
