import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, date
from math import exp

st.set_page_config(page_title="Voetbal AI", layout="wide")
st.title("⚽ Voetbal AI – Wedstrijden, Odds & Win-kans")

API_KEY = st.secrets["API_KEY"]
BASE_URL = "https://v3.football.api-sports.io/"
HEADERS = {"x-apisports-key": API_KEY}

# ---------- UITGEBREIDE LEAGUES ----------
TOP_LEAGUES = {
    # England
    "Premier League (ENG)": 39,
    "Championship (ENG)": 40,
    "League One (ENG)": 41,
    "League Two (ENG)": 42,

    # Scotland
    "Premiership (SCO)": 179,
    "Championship (SCO)": 180,

    # Netherlands
    "Eredivisie (NED)": 88,
    "Eerste Divisie (NED)": 89,

    # Spain
    "La Liga (ESP)": 140,
    "Segunda División (ESP)": 141,

    # Italy
    "Serie A (ITA)": 135,
    "Serie B (ITA)": 136,

    # Germany
    "Bundesliga (GER)": 78,
    "2. Bundesliga (GER)": 79,

    # France
    "Ligue 1 (FRA)": 61,
    "Ligue 2 (FRA)": 62,
}

# ---------- Helpers ----------
def api_get(endpoint, params=None):
    r = requests.get(BASE_URL + endpoint, headers=HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=600)
def get_fixtures(date_str):
    return api_get("fixtures", {"date": date_str}).get("response", [])

@st.cache_data(ttl=1800)
def get_standings(league_id, season):
    data = api_get("standings", {"league": league_id, "season": season})
    resp = data.get("response", [])
    out = {}
    try:
        table = resp[0]["league"]["standings"][0]
        for row in table:
            team_id = row["team"]["id"]
            played = row["all"]["played"] or 1
            points = row["points"]
            out[team_id] = points / played
    except:
        pass
    return out

def probs_from_strength(home_strength, away_strength):
    diff = home_strength - away_strength
    ph = 1 / (1 + exp(-2.2 * diff))
    draw = max(0.18, 0.30 - abs(diff) * 0.12)
    rem = 1 - draw
    return {
        "H": ph * rem,
        "D": draw,
        "A": (1 - ph) * rem
    }

def fmt_pct(x):
    return f"{round(x*100)}%"

def season_guess():
    today = datetime.now().date()
    return today.year if today.month >= 7 else today.year - 1

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("⚙️ Instellingen")

    leagues_selected = st.multiselect(
        "Competities",
        list(TOP_LEAGUES.keys()),
        default=list(TOP_LEAGUES.keys())[:6]
    )

    start = st.date_input("Startdatum", value=date.today())
    end = st.date_input("Einddatum", value=date.today() + timedelta(days=1))

    show_logos = st.toggle("Toon logo’s", value=True)
    show_compact = st.toggle("Compacte tabel", value=False)

# ---------- DATE RANGE ----------
if end < start:
    st.error("Einddatum moet later zijn dan startdatum.")
    st.stop()

dates = []
d = start
while d <= end:
    dates.append(d.strftime("%Y-%m-%d"))
    d += timedelta(days=1)

league_ids = {TOP_LEAGUES[n] for n in leagues_selected}
season = season_guess()

# ---------- FETCH DATA ----------
rows = []

with st.spinner("Wedstrijden ophalen..."):
    for ds in dates:
        fixtures = get_fixtures(ds)
        for m in fixtures:
            if m["league"]["id"] not in league_ids:
                continue

            rows.append({
                "Datum": ds,
                "Tijd": m["fixture"]["date"][11:16],
                "Competitie": m["league"]["name"],
                "LeagueID": m["league"]["id"],
                "Home": m["teams"]["home"]["name"],
                "Away": m["teams"]["away"]["name"],
                "HomeID": m["teams"]["home"]["id"],
                "AwayID": m["teams"]["away"]["id"],
                "Status": m["fixture"]["status"]["short"],
                "LeagueLogo": m["league"]["logo"],
                "HomeLogo": m["teams"]["home"]["logo"],
                "AwayLogo": m["teams"]["away"]["logo"],
            })

if not rows:
    st.warning("Geen wedstrijden gevonden.")
    st.stop()

df = pd.DataFrame(rows).sort_values(["Datum", "Tijd"])
st.success(f"{len(df)} wedstrijden gevonden")

# ---------- PREDICTIONS ----------
standings_cache = {}

preds = []

with st.spinner("Win-kansen berekenen..."):
    for _, r in df.iterrows():
        lid = r["LeagueID"]

        if lid not in standings_cache:
            standings_cache[lid] = get_standings(lid, season)

        standings = standings_cache[lid]

        home_strength = standings.get(r["HomeID"], 1.2)
        away_strength = standings.get(r["AwayID"], 1.2)

        probs = probs_from_strength(home_strength, away_strength)
        preds.append(probs)

df["Win% Home"] = [fmt_pct(p["H"]) for p in preds]
df["Win% Draw"] = [fmt_pct(p["D"]) for p in preds]
df["Win% Away"] = [fmt_pct(p["A"]) for p in preds]

# ---------- DISPLAY ----------
if show_compact:
    st.dataframe(df[[
        "Datum","Tijd","Competitie","Home","Away",
        "Win% Home","Win% Draw","Win% Away"
    ]], use_container_width=True)
else:
    for ds, group in df.groupby("Datum"):
        st.subheader(ds)
        for _, r in group.iterrows():
            col1, col2 = st.columns([4, 2])

            with col1:
                if show_logos:
                    cols = st.columns([1,6,1,6])
                    with cols[0]: st.image(r["HomeLogo"], width=28)
                    with cols[1]: st.write(f"**{r['Home']}**")
                    with cols[2]: st.image(r["AwayLogo"], width=28)
                    with cols[3]: st.write(f"**{r['Away']}**")
                else:
                    st.write(f"**{r['Home']} vs {r['Away']}**")

                st.caption(f"{r['Tijd']} • {r['Competitie']} • {r['Status']}")

            with col2:
                st.write("**Win-kans**")
                st.write(f"H {r['Win% Home']}")
                st.write(f"D {r['Win% Draw']}")
                st.write(f"A {r['Win% Away']}")
