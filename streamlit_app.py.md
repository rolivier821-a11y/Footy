# streamlit_app.py  
#   
import streamlit as st  
import requests  
import pandas as pd  
from datetime import datetime, timedelta, date  
from math import exp, factorial  
from typing import Optional, Dict, Any, List, Tuple  
  
# =========================  
# Streamlit config  
# =========================  
st.set_page_config(page_title="Voetbal AI", layout="wide")  
st.title("⚽ Voetbal AI – Wedstrijden, Vorm, Odds & Bets")  
  
API_KEY = st.secrets["API_KEY"]  
BASE_URL = "https://v3.football.api-sports.io/"  
HEADERS = {"x-apisports-key": API_KEY}  
  
TOTAL_LINES = [1.5, 2.5, 3.5, 4.5]  
  
# =========================  
# API helpers  
# =========================  
def api_get(endpoint: str, params: Optional[Dict[str, Any]] = None) -> dict:  
    r = requests.get(BASE_URL + endpoint, headers=HEADERS, params=params or {}, timeout=30)  
    r.raise_for_status()  
    return r.json()  
  
def season_guess() -> int:  
    today = datetime.now().date()  
    return today.year if today.month >= 7 else today.year - 1  
  
@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)  # 6 uur cache  
def get_all_leagues(season: int) -> List[dict]:  
    return api_get("leagues", {"season": season}).get("response", [])  
  
@st.cache_data(ttl=60 * 10, show_spinner=False)  
def get_fixtures(date_str: str) -> list:  
    return api_get("fixtures", {"date": date_str}).get("response", [])  
  
@st.cache_data(ttl=60 * 30, show_spinner=False)  
def get_standings_ppg(league_id: int, season: int) -> Dict[int, float]:  
    out: Dict[int, float] = {}  
    try:  
        data = api_get("standings", {"league": league_id, "season": season})  
        resp = data.get("response", [])  
        table = resp[0]["league"]["standings"][0]  
        for row in table:  
            team_id = row["team"]["id"]  
            played = row["all"]["played"] or 1  
            points = row["points"]  
            out[team_id] = points / played  
    except Exception:  
        pass  
    return out  
  
@st.cache_data(ttl=60 * 30, show_spinner=False)  
def get_team_recent(team_id: int, season: int, league_id: int, last_n: int = 5) -> list:  
    try:  
        data = api_get("fixtures", {"team": team_id, "season": season, "league": league_id, "last": last_n})  
        return data.get("response", [])  
    except Exception:  
        return []  
  
def parse_form_and_goals(fixtures: list, team_id: int) -> Dict[str, Any]:  
    form: List[str] = []  
    pts = 0  
    n = 0  
    gf = 0  
    ga = 0  
  
    for m in fixtures:  
        if m.get("fixture", {}).get("status", {}).get("short") not in ("FT", "AET", "PEN"):  
            continue  
        home_id = m["teams"]["home"]["id"]  
        away_id = m["teams"]["away"]["id"]  
        hg = m["goals"]["home"]  
        ag = m["goals"]["away"]  
        if hg is None or ag is None:  
            continue  
  
        n += 1  
        if team_id == home_id:  
            gf += hg; ga += ag  
            if hg > ag:  
                form.append("W"); pts += 3  
            elif hg == ag:  
                form.append("D"); pts += 1  
            else:  
                form.append("L")  
        else:  
            gf += ag; ga += hg  
            if ag > hg:  
                form.append("W"); pts += 3  
            elif ag == hg:  
                form.append("D"); pts += 1  
            else:  
                form.append("L")  
  
    if n == 0:  
        return {"form_str": "—", "avg_pts": None, "gf_avg": None, "ga_avg": None}  
  
    return {  
        "form_str": "-".join(form),  
        "avg_pts": pts / n,  
        "gf_avg": gf / n,  
        "ga_avg": ga / n,  
    }  
  
# =========================  
# Odds parsing  
# =========================  
def _as_float(x) -> Optional[float]:  
    try:  
        if x is None:  
            return None  
        return float(x)  
    except Exception:  
        return None  
  
@st.cache_data(ttl=60 * 10, show_spinner=False)  
def get_odds_markets(fixture_id: int) -> Dict[str, Any]:  
    out: Dict[str, Any] = {"1X2": None, "DC": None, "BTTS": None, "TOTALS": {ln: None for ln in TOTAL_LINES}}  
    try:  
        data = api_get("odds", {"fixture": fixture_id})  
        resp = data.get("response", [])  
        if not resp:  
            return out  
  
        for bkm in resp[0].get("bookmakers", []):  
            for bet in bkm.get("bets", []):  
                nm = (bet.get("name") or "").lower()  
                vals = bet.get("values", [])  
  
                if nm in ("match winner", "1x2", "match result"):  
                    tmp = {}  
                    for v in vals:  
                        label = v.get("value")  
                        odd = _as_float(v.get("odd"))  
                        if odd is None:  
                            continue  
                        if label in ("Home", "1"): tmp["1"] = odd  
                        elif label in ("Draw", "X"): tmp["X"] = odd  
                        elif label in ("Away", "2"): tmp["2"] = odd  
                    if {"1","X","2"}.issubset(tmp.keys()):  
                        out["1X2"] = tmp  
  
                if nm == "double chance":  
                    tmp = {}  
                    for v in vals:  
                        label = str(v.get("value") or "")  
                        odd = _as_float(v.get("odd"))  
                        if odd is None:  
                            continue  
                        if label in ("1X","Home/Draw"): tmp["1X"] = odd  
                        elif label in ("12","Home/Away"): tmp["12"] = odd  
                        elif label in ("X2","Draw/Away"): tmp["X2"] = odd  
                    if {"1X","12","X2"}.issubset(tmp.keys()):  
                        out["DC"] = tmp  
  
                if nm in ("both teams score", "both teams to score", "btts"):  
                    tmp = {}  
                    for v in vals:  
                        label = str(v.get("value") or "").lower()  
                        odd = _as_float(v.get("odd"))  
                        if odd is None:  
                            continue  
                        if label in ("yes","y"): tmp["Yes"] = odd  
                        elif label in ("no","n"): tmp["No"] = odd  
                    if {"Yes","No"}.issubset(tmp.keys()):  
                        out["BTTS"] = tmp  
  
                if nm in ("goals over/under", "over/under", "total goals", "goals over under"):  
                    tmp_tot = {ln: {"Over": None, "Under": None} for ln in TOTAL_LINES}  
                    for v in vals:  
                        label = str(v.get("value") or "").lower().replace(",", ".").strip()  
                        odd = _as_float(v.get("odd"))  
                        if odd is None:  
                            continue  
                        for ln in TOTAL_LINES:  
                            ln_str = str(ln).replace(",", ".")  
                            if f"over {ln_str}" in label:  
                                tmp_tot[ln]["Over"] = odd  
                            if f"under {ln_str}" in label:  
                                tmp_tot[ln]["Under"] = odd  
                    for ln in TOTAL_LINES:  
                        if tmp_tot[ln]["Over"] and tmp_tot[ln]["Under"]:  
                            out["TOTALS"][ln] = tmp_tot[ln]  
  
            all_tot = all(out["TOTALS"][ln] is not None for ln in TOTAL_LINES)  
            if out["1X2"] and out["DC"] and out["BTTS"] and all_tot:  
                break  
  
        return out  
    except Exception:  
        return out  
  
# =========================  
# Model helpers  
# =========================  
def implied_probs_from_odds(odds: Dict[str, float]) -> Dict[str, float]:  
    inv = {k: 1.0 / max(v, 1e-9) for k, v in odds.items()}  
    s = sum(inv.values())  
    return {k: inv[k] / s for k in inv}  
  
def probs_1x2_from_strength(home_strength: float, away_strength: float) -> Dict[str, float]:  
    diff = home_strength - away_strength  
    ph_raw = 1 / (1 + exp(-2.2 * diff))  
    pa_raw = 1 - ph_raw  
    draw = max(0.18, 0.30 - abs(diff) * 0.12)  
    rem = 1 - draw  
    return {"H": ph_raw * rem, "D": draw, "A": pa_raw * rem}  
  
def form_bonus(avg_pts: Optional[float]) -> float:  
    if avg_pts is None:  
        return 0.0  
    return (avg_pts - 1.4) * 0.10  
  
def fmt_pct(x: float) -> str:  
    return f"{round(x*100)}%"  
  
def poisson_pmf(k: int, lam: float) -> float:  
    lam = max(lam, 1e-6)  
    return exp(-lam) * (lam ** k) / factorial(k)  
  
def btts_prob(lh: float, la: float) -> float:  
    p_h0 = poisson_pmf(0, lh)  
    p_a0 = poisson_pmf(0, la)  
    p = 1 - p_h0 - p_a0 + (p_h0 * p_a0)  
    return min(max(p, 0.0), 1.0)  
  
def over_prob_total(l_total: float, line: float) -> float:  
    cutoff = int(line // 1)  
    p_le = 0.0  
    for k in range(0, cutoff + 1):  
        p_le += poisson_pmf(k, l_total)  
    return min(max(1 - p_le, 0.0), 1.0)  
  
def safe_avg(a: Optional[float], b: Optional[float], fallback: float) -> float:  
    if a is None or b is None:  
        return fallback  
    return (a + b) / 2  
  
# =========================  
# League selector (dynamic)  
# =========================  
def league_label(item: dict) -> str:  
    c = item.get("country", {}).get("name", "—")  
    lg = item.get("league", {})  
    name = lg.get("name", "—")  
    typ = lg.get("type", "—")  # League / Cup  
    return f"{c} — {name} ({typ})"  
  
def build_options(season: int, countries: List[str], include_cups: bool, include_internationals: bool) -> List[Tuple[str, int]]:  
    all_lg = get_all_leagues(season)  
    wanted = set(countries)  
  
    out: List[Tuple[str, int]] = []  
    for it in all_lg:  
        country = it.get("country", {}).get("name", "")  
        typ = (it.get("league", {}).get("type", "") or "").lower()  # league/cup  
        lid = int(it.get("league", {}).get("id"))  
  
        # Internationals zitten vaak onder country == "World" of "Europe"  
        is_international = country in ("World", "Europe")  
  
        if is_international:  
            if not include_internationals:  
                continue  
        else:  
            if countries and country not in wanted:  
                continue  
  
        if not include_cups and typ == "cup":  
            continue  
  
        out.append((league_label(it), lid))  
  
    out.sort(key=lambda x: x[0].lower())  
    return out  
  
# =========================  
# Sidebar UI  
# =========================  
season = season_guess()  
  
with st.sidebar:  
    st.header("⚙️ Instellingen")  
  
    # Landen die jij noemde + handig extra  
    default_countries = ["England", "Scotland", "Netherlands", "France", "Spain", "Italy", "Germany"]  
    countries = st.multiselect("Landen", default_countries, default=default_countries)  
  
    include_cups = st.toggle("Bekers meenemen (FA Cup, KNVB Beker, etc.)", value=True)  
    include_internationals = st.toggle("Internationals/Europees (CL/EL/ECL, Nations League, etc.)", value=True)  
  
    # Zoekfilter (super handig)  
    search = st.text_input("Zoek competitie (bv. Championship, Champions, Cup, Nations)", value="")  
  
    # Bouw opties  
    options = build_options(season, countries, include_cups, include_internationals)  
    if search.strip():  
        options = [x for x in options if search.lower() in x[0].lower()]  
  
    labels = [o[0] for o in options]  
    label_to_id = {lab: lid for lab, lid in options}  
  
    # Default selectie: jouw relevante divisies + UEFA  
    default_keywords = [  
        "premier league", "championship", "league one", "league two",  
        "premiership", "scottish championship",  
        "eredivisie", "eerste divisie",  
        "ligue 1", "ligue 2",  
        "la liga", "segunda",  
        "serie a", "serie b",  
        "bundesliga", "2. bundesliga",  
        "champions league", "europa league", "conference league",  
    ]  
    default_labels = [lab for lab in labels if any(k in lab.lower() for k in default_keywords)][:25]  
  
    selected_labels = st.multiselect("Competities", labels, default=default_labels)  
    selected_league_ids = {label_to_id[lab] for lab in selected_labels}  
  
    st.divider()  
    day_mode = st.radio("Welke dagen?", ["Vandaag", "Morgen", "Vandaag + morgen", "Kies range"], index=2)  
    if day_mode == "Kies range":  
        start = st.date_input("Startdatum", value=date.today(), min_value=date.today(), max_value=date.today() + timedelta(days=14))  
        end = st.date_input("Einddatum", value=date.today() + timedelta(days=1), min_value=date.today(), max_value=date.today() + timedelta(days=14))  
    else:  
        start = date.today() + (timedelta(days=1) if day_mode == "Morgen" else timedelta(days=0))  
        end = start if day_mode in ("Vandaag", "Morgen") else date.today() + timedelta(days=1)  
  
    show_logos = st.toggle("Toon logo’s", value=True)  
    show_odds = st.toggle("Toon odds (als beschikbaar)", value=True)  
    use_odds_for_1x2 = st.toggle("Gebruik odds voor 1X2% (als beschikbaar)", value=True)  
  
    st.divider()  
    show_value = st.toggle("Toon value bets tabel", value=True)  
    edge_threshold = st.slider("Value drempel (model - implied)", 0.00, 0.25, 0.05, 0.01)  
  
    show_compact_table = st.toggle("Compacte tabel (sneller)", value=False)  
  
# Validate dates  
if end < start:  
    st.error("Einddatum moet gelijk of later zijn dan startdatum.")  
    st.stop()  
  
# Build dates  
dates = []  
d = start  
while d <= end:  
    dates.append(d.strftime("%Y-%m-%d"))  
    d += timedelta(days=1)  
  
st.caption(f"Seizoen (auto): **{season}** • Datums: **{dates[0]} → {dates[-1]}** • Competities geselecteerd: **{len(selected_league_ids)}**")  
  
if not selected_league_ids:  
    st.warning("Selecteer minimaal 1 competitie in de sidebar.")  
    st.stop()  
  
# =========================  
# Fetch fixtures  
# =========================  
rows = []  
with st.spinner("Wedstrijden ophalen…"):  
    for ds in dates:  
        fx = get_fixtures(ds)  
        for m in fx:  
            lid = m["league"]["id"]  
            if lid not in selected_league_ids:  
                continue  
  
            kickoff = m["fixture"]["date"]  
            rows.append({  
                "Datum": ds,  
                "Tijd": kickoff[11:16],  
                "Competitie": m["league"]["name"],  
                "LeagueID": lid,  
                "FixtureID": m["fixture"]["id"],  
                "Home": m["teams"]["home"]["name"],  
                "Away": m["teams"]["away"]["name"],  
                "HomeID": m["teams"]["home"]["id"],  
                "AwayID": m["teams"]["away"]["id"],  
                "Status": m["fixture"]["status"]["short"],  
                "LeagueLogo": m["league"].get("logo"),  
                "HomeLogo": m["teams"]["home"].get("logo"),  
                "AwayLogo": m["teams"]["away"].get("logo"),  
            })  
  
if not rows:  
    st.warning("Geen wedstrijden gevonden voor jouw selectie/datums.")  
    st.stop()  
  
df = pd.DataFrame(rows).sort_values(["Datum", "Tijd", "Competitie"]).reset_index(drop=True)  
st.success(f"{len(df)} wedstrijden gevonden")  
  
# =========================  
# Compute form + model + odds + bets  
# =========================  
standings_cache: Dict[int, Dict[int, float]] = {}  
  
def get_ppg_strength(league_id: int, team_id: int) -> float:  
    if league_id not in standings_cache:  
        standings_cache[league_id] = get_standings_ppg(league_id, season)  
    return float(standings_cache[league_id].get(team_id, 1.2))  
  
home_form, away_form = [], []  
home_pts, away_pts = [], []  
home_gf, home_ga = [], []  
away_gf, away_ga = [], []  
  
pH_list, pD_list, pA_list = [], [], []  
dc_1x_list, dc_12_list, dc_x2_list = [], [], []  
btts_yes_list, btts_no_list = [], []  
  
ou_over = {ln: [] for ln in TOTAL_LINES}  
ou_under = {ln: [] for ln in TOTAL_LINES}  
  
odds_1x2_col, odds_dc_col, odds_btts_col = [], [], []  
odds_ou_col = {ln: [] for ln in TOTAL_LINES}  
  
best_value_name, best_value_edge = [], []  
  
with st.spinner("Vorm, bets & (optioneel) odds berekenen…"):  
    for _, r in df.iterrows():  
        fixture_id = int(r["FixtureID"])  
        league_id = int(r["LeagueID"])  
        hid = int(r["HomeID"])  
        aid = int(r["AwayID"])  
  
        # Form + goals last 5  
        h_recent = get_team_recent(hid, season, league_id, last_n=5)  
        a_recent = get_team_recent(aid, season, league_id, last_n=5)  
        h_info = parse_form_and_goals(h_recent, hid)  
        a_info = parse_form_and_goals(a_recent, aid)  
  
        home_form.append(h_info["form_str"])  
        away_form.append(a_info["form_str"])  
        home_pts.append(None if h_info["avg_pts"] is None else round(h_info["avg_pts"], 2))  
        away_pts.append(None if a_info["avg_pts"] is None else round(a_info["avg_pts"], 2))  
        home_gf.append(None if h_info["gf_avg"] is None else round(h_info["gf_avg"], 2))  
        home_ga.append(None if h_info["ga_avg"] is None else round(h_info["ga_avg"], 2))  
        away_gf.append(None if a_info["gf_avg"] is None else round(a_info["gf_avg"], 2))  
        away_ga.append(None if a_info["ga_avg"] is None else round(a_info["ga_avg"], 2))  
  
        # Model 1X2  
        hs = get_ppg_strength(league_id, hid) + form_bonus(h_info["avg_pts"])  
        a_s = get_ppg_strength(league_id, aid) + form_bonus(a_info["avg_pts"])  
        probs = probs_1x2_from_strength(hs, a_s)  
  
        # Odds markets  
        mk = get_odds_markets(fixture_id) if show_odds else {"1X2": None, "DC": None, "BTTS": None, "TOTALS": {ln: None for ln in TOTAL_LINES}}  
        o1x2 = mk["1X2"]  
        odc = mk["DC"]  
        obtts = mk["BTTS"]  
        otot = mk["TOTALS"]  
  
        odds_1x2_col.append(o1x2)  
        odds_dc_col.append(odc)  
        odds_btts_col.append(obtts)  
  
        # Use odds for 1X2% if available  
        if use_odds_for_1x2 and o1x2:  
            imp = implied_probs_from_odds(o1x2)  
            pH = imp.get("1", probs["H"])  
            pD = imp.get("X", probs["D"])  
            pA = imp.get("2", probs["A"])  
        else:  
            pH, pD, pA = probs["H"], probs["D"], probs["A"]  
  
        pH_list.append(pH); pD_list.append(pD); pA_list.append(pA)  
  
        # Double chance  
        dc_1x = pH + pD  
        dc_12 = pH + pA  
        dc_x2 = pD + pA  
        dc_1x_list.append(dc_1x)  
        dc_12_list.append(dc_12)  
        dc_x2_list.append(dc_x2)  
  
        # Lambdas from last-5 averages  
        lam_home = safe_avg(h_info["gf_avg"], a_info["ga_avg"], fallback=1.25)  
        lam_away = safe_avg(a_info["gf_avg"], h_info["ga_avg"], fallback=1.05)  
        lam_total = lam_home + lam_away  
  
        # BTTS  
        p_btts = btts_prob(lam_home, lam_away)  
        btts_yes_list.append(p_btts)  
        btts_no_list.append(1 - p_btts)  
  
        # O/U  
        for ln in TOTAL_LINES:  
            p_over = over_prob_total(lam_total, ln)  
            ou_over[ln].append(p_over)  
            ou_under[ln].append(1 - p_over)  
            odds_ou_col[ln].append(otot.get(ln) if (otot and otot.get(ln)) else None)  
  
        # Best value  
        best_name = "—"  
        best_edge = 0.0  
  
        def consider(name: str, model_p: float, odd: Optional[float]):  
            nonlocal best_name, best_edge  
            if odd is None or odd <= 1.01:  
                return  
            implied = 1.0 / odd  
            edge = model_p - implied  
            if edge > best_edge:  
                best_edge = edge  
                best_name = name  
  
        if o1x2:  
            consider("1 (Home)", pH, o1x2.get("1"))  
            consider("X (Draw)", pD, o1x2.get("X"))  
            consider("2 (Away)", pA, o1x2.get("2"))  
        if odc:  
            consider("1X", dc_1x, odc.get("1X"))  
            consider("12", dc_12, odc.get("12"))  
            consider("X2", dc_x2, odc.get("X2"))  
        if obtts:  
            consider("BTTS Yes", p_btts, obtts.get("Yes"))  
            consider("BTTS No", 1 - p_btts, obtts.get("No"))  
        for ln in TOTAL_LINES:  
            ouo = odds_ou_col[ln][-1]  
            if ouo:  
                consider(f"Over {ln}", ou_over[ln][-1], ouo.get("Over"))  
                consider(f"Under {ln}", ou_under[ln][-1], ouo.get("Under"))  
  
        best_value_name.append(best_name)  
        best_value_edge.append(round(best_edge, 3))  
  
# Attach columns  
df["Vorm Home (L5)"] = home_form  
df["Vorm Away (L5)"] = away_form  
df["Pts Home (avg)"] = home_pts  
df["Pts Away (avg)"] = away_pts  
df["GF Home (L5)"] = home_gf  
df["GA Home (L5)"] = home_ga  
df["GF Away (L5)"] = away_gf  
df["GA Away (L5)"] = away_ga  
  
df["1X2 Home%"] = [fmt_pct(x) for x in pH_list]  
df["1X2 Draw%"] = [fmt_pct(x) for x in pD_list]  
df["1X2 Away%"] = [fmt_pct(x) for x in pA_list]  
df["DC 1X%"] = [fmt_pct(x) for x in dc_1x_list]  
df["DC 12%"] = [fmt_pct(x) for x in dc_12_list]  
df["DC X2%"] = [fmt_pct(x) for x in dc_x2_list]  
df["BTTS Yes%"] = [fmt_pct(x) for x in btts_yes_list]  
df["BTTS No%"] = [fmt_pct(x) for x in btts_no_list]  
for ln in TOTAL_LINES:  
    df[f"Over {ln}%"] = [fmt_pct(x) for x in ou_over[ln]]  
    df[f"Under {ln}%"] = [fmt_pct(x) for x in ou_under[ln]]  
  
# Odds formatting (optional)  
def fmt_1x2(o):  
    if not o: return ""  
    return f'{o.get("1","")} / {o.get("X","")} / {o.get("2","")}'  
  
def fmt_dc(o):  
    if not o: return ""  
    return f'{o.get("1X","")} / {o.get("12","")} / {o.get("X2","")}'  
  
def fmt_btts(o):  
    if not o: return ""  
    return f'Yes {o.get("Yes","")} • No {o.get("No","")}'  
  
def fmt_ou(o, ln):  
    if not o: return ""  
    return f'Over {ln}: {o.get("Over","")} • Under {ln}: {o.get("Under","")}'  
  
if show_odds:  
    df["Odds 1/X/2"] = [fmt_1x2(o) for o in odds_1x2_col]  
    df["Odds DC (1X/12/X2)"] = [fmt_dc(o) for o in odds_dc_col]  
    df["Odds BTTS"] = [fmt_btts(o) for o in odds_btts_col]  
    for ln in TOTAL_LINES:  
        df[f"Odds O/U {ln}"] = [fmt_ou(o, ln) if o else "" for o in odds_ou_col[ln]]  
  
df["Beste value"] = best_value_name  
df["Edge"] = best_value_edge  
  
# =========================  
# Value table (top)  
# =========================  
if show_value:  
    val_df = df[df["Edge"] >= edge_threshold].copy().sort_values("Edge", ascending=False).head(30)  
    if len(val_df) > 0:  
        st.subheader("💰 Top Value Bets (model% > implied%)")  
        cols = [  
            "Datum","Tijd","Competitie","Home","Away",  
            "Beste value","Edge",  
            "1X2 Home%","1X2 Draw%","1X2 Away%",  
            "DC 1X%","DC 12%","DC X2%",  
            "BTTS Yes%","Over 2.5%","Over 3.5%",  
            "Vorm Home (L5)","Vorm Away (L5)"  
        ]  
        if show_odds:  
            cols += ["Odds 1/X/2","Odds DC (1X/12/X2)","Odds BTTS","Odds O/U 2.5","Odds O/U 3.5"]  
        st.dataframe(val_df[cols], use_container_width=True)  
    else:  
        st.caption("Geen value bets gevonden met jouw drempel (of odds niet beschikbaar op jouw plan).")  
  
# =========================  
# Main display  
# =========================  
st.subheader("📅 Alle wedstrijden")  
  
if show_compact_table:  
    cols = [  
        "Datum","Tijd","Competitie","Home","Away","Status",  
        "Vorm Home (L5)","Vorm Away (L5)","Pts Home (avg)","Pts Away (avg)",  
        "1X2 Home%","1X2 Draw%","1X2 Away%",  
        "DC 1X%","DC 12%","DC X2%",  
        "BTTS Yes%","BTTS No%",  
        "Over 1.5%","Under 1.5%","Over 2.5%","Under 2.5%","Over 3.5%","Under 3.5%","Over 4.5%","Under 4.5%",  
        "Beste value","Edge",  
    ]  
    if show_odds:  
        cols += ["Odds 1/X/2","Odds DC (1X/12/X2)","Odds BTTS","Odds O/U 1.5","Odds O/U 2.5","Odds O/U 3.5","Odds O/U 4.5"]  
    st.dataframe(df[cols], use_container_width=True)  
else:  
    for ds, group in df.groupby("Datum"):  
        st.subheader(ds)  
        for _, r in group.iterrows():  
            c1, c2, c3, c4 = st.columns([1.2, 4.2, 3.2, 3.2])  
  
            with c1:  
                if show_logos and r.get("LeagueLogo"):  
                    st.image(r["LeagueLogo"], width=40)  
                st.caption(r["Competitie"])  
  
            with c2:  
                if show_logos:  
                    cols2 = st.columns([1, 6, 1, 6])  
                    with cols2[0]:  
                        if r.get("HomeLogo"): st.image(r["HomeLogo"], width=28)  
                    with cols2[1]:  
                        st.write(f"**{r['Home']}**")  
                        st.caption(f"Vorm: {r['Vorm Home (L5)']} • Pts: {r['Pts Home (avg)']} • GF/GA: {r['GF Home (L5)']}/{r['GA Home (L5)']}")  
                    with cols2[2]:  
                        if r.get("AwayLogo"): st.image(r["AwayLogo"], width=28)  
                    with cols2[3]:  
                        st.write(f"**{r['Away']}**")  
                        st.caption(f"Vorm: {r['Vorm Away (L5)']} • Pts: {r['Pts Away (avg)']} • GF/GA: {r['GF Away (L5)']}/{r['GA Away (L5)']}")  
                else:  
                    st.write(f"**{r['Home']} vs {r['Away']}**")  
  
                st.caption(f"{r['Tijd']} • Status: {r['Status']}")  
  
            with c3:  
                st.write("**1X2 %**")  
                st.write(f"Home {r['1X2 Home%']} • Draw {r['1X2 Draw%']} • Away {r['1X2 Away%']}")  
                st.write("**Dubbele kans %**")  
                st.write(f"1X {r['DC 1X%']} • 12 {r['DC 12%']} • X2 {r['DC X2%']}")  
                st.write("**BTTS %**")  
                st.write(f"Yes {r['BTTS Yes%']} • No {r['BTTS No%']}")  
  
            with c4:  
                st.write("**Over/Under %**")  
                st.write(f"O1.5 {r['Over 1.5%']} • U1.5 {r['Under 1.5%']}")  
                st.write(f"O2.5 {r['Over 2.5%']} • U2.5 {r['Under 2.5%']}")  
                st.write(f"O3.5 {r['Over 3.5%']} • U3.5 {r['Under 3.5%']}")  
                st.write(f"O4.5 {r['Over 4.5%']} • U4.5 {r['Under 4.5%']}")  
  
                st.write("**Beste bet (value)**")  
                st.write(f"{r['Beste value']}  (edge: {r['Edge']})")  
  
                if show_odds:  
                    st.write("**Odds (als beschikbaar)**")  
                    st.write(f"1/X/2: {r.get('Odds 1/X/2','—') or '—'}")  
                    st.write(f"DC: {r.get('Odds DC (1X/12/X2)','—') or '—'}")  
                    st.write(f"BTTS: {r.get('Odds BTTS','—') or '—'}")  
                    st.write(f"O/U 2.5: {r.get('Odds O/U 2.5','—') or '—'}")  
