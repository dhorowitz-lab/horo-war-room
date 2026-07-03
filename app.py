import json
from pathlib import Path
from datetime import datetime, timezone
import requests
import pandas as pd
import streamlit as st

LEAGUE_ID = "1322264688641216512"
DRAFT_ID = "1322264688645390336"
HORO_DISPLAY = "HORO1"
BASE = "https://api.sleeper.app/v1"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="HoRo Dynasty War Room", page_icon="🏈", layout="wide")

@st.cache_data(ttl=60)
def get_json(url):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

def sleeper(path):
    return get_json(f"{BASE}{path}")

def save_snapshot(name, obj):
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / f"{name}.json").write_text(json.dumps(obj, indent=2), encoding="utf-8")

def load_rankings():
    files = ["fantasycalc_dynasty_rankings.csv", "fantasycalc_dynasty_rookie_rankings.csv"]
    dfs = []
    for f in files:
        p = Path(f)
        if p.exists():
            df = pd.read_csv(p)
            df["source_file"] = f
            dfs.append(df)
    return dfs

def normalize_rankings(dfs):
    rows = []
    for df in dfs:
        cols = {c.lower().strip(): c for c in df.columns}
        name_col = next((cols[x] for x in cols if x in ["player", "name", "player name"] or "player" in x and "id" not in x), None)
        pos_col = next((cols[x] for x in cols if x in ["pos", "position"]), None)
        team_col = next((cols[x] for x in cols if x in ["team", "nfl team"]), None)
        rank_col = next((cols[x] for x in cols if x in ["rank", "overall rank", "overall"] or "rank" in x), None)
        value_col = next((cols[x] for x in cols if "value" in x), None)
        sleeper_col = next((cols[x] for x in cols if "sleeper" in x and "id" in x), None)
        for _, r in df.iterrows():
            name = r.get(name_col, None) if name_col else None
            if pd.isna(name) or not name:
                continue
            sid = str(r.get(sleeper_col, "")).replace(".0", "") if sleeper_col else ""
            val = r.get(value_col, None) if value_col else None
            rank = r.get(rank_col, None) if rank_col else None
            rows.append({
                "player": str(name),
                "pos": r.get(pos_col, "") if pos_col else "",
                "team": r.get(team_col, "") if team_col else "",
                "rank": rank,
                "value": val,
                "sleeper_id": sid,
                "source": r.get("source_file", "rankings")
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["rank_num"] = pd.to_numeric(out["rank"], errors="coerce")
    out["value_num"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.sort_values(["rank_num", "value_num"], ascending=[True, False], na_position="last")
    out = out.drop_duplicates(subset=["player", "pos"], keep="first")
    return out

st.title("🏈 HoRo Dynasty War Room")
st.caption("Free shared web app powered by Sleeper + your FantasyCalc rankings")

with st.sidebar:
    st.header("Controls")
    if st.button("🔄 Update Sleeper Data", use_container_width=True):
        st.cache_data.clear()
        st.success("Refreshed. Reloading latest Sleeper data...")
    st.markdown(f"**League:** `{LEAGUE_ID}`")
    st.markdown(f"**Draft:** `{DRAFT_ID}`")
    st.markdown(f"**Your account:** `{HORO_DISPLAY}`")

try:
    league = sleeper(f"/league/{LEAGUE_ID}")
    users = sleeper(f"/league/{LEAGUE_ID}/users")
    rosters = sleeper(f"/league/{LEAGUE_ID}/rosters")
    draft = sleeper(f"/draft/{DRAFT_ID}")
    picks = sleeper(f"/draft/{DRAFT_ID}/picks")
    traded = sleeper(f"/league/{LEAGUE_ID}/traded_picks")
    trending_add = sleeper("/players/nfl/trending/add?lookback_hours=24&limit=25")
    trending_drop = sleeper("/players/nfl/trending/drop?lookback_hours=24&limit=25")
    for n, o in [("league", league),("users", users),("rosters", rosters),("draft", draft),("draft_picks", picks),("traded_picks", traded)]:
        save_snapshot(n, o)
except Exception as e:
    st.error(f"Could not reach Sleeper API: {e}")
    st.stop()

user_by_id = {u["user_id"]: u for u in users}
owner_to_roster = {r.get("owner_id"): r.get("roster_id") for r in rosters}
horo_user = next((u for u in users if str(u.get("display_name", "")).lower() == HORO_DISPLAY.lower()), None)
horo_roster_id = owner_to_roster.get(horo_user["user_id"]) if horo_user else None

# Draft table
pick_rows = []
drafted_ids = set()
for p in picks:
    md = p.get("metadata", {}) or {}
    player = f"{md.get('first_name','')} {md.get('last_name','')}".strip()
    drafted_ids.add(str(p.get("player_id")))
    user = user_by_id.get(str(p.get("picked_by")), {})
    team_name = user.get("metadata", {}).get("team_name") or user.get("display_name", "")
    pick_rows.append({
        "Pick": p.get("pick_no"),
        "Round": p.get("round"),
        "Slot": p.get("draft_slot"),
        "Player": player,
        "Pos": md.get("position"),
        "NFL": md.get("team"),
        "Picked By": team_name,
        "Roster ID": p.get("roster_id"),
        "Sleeper ID": p.get("player_id")
    })
draft_df = pd.DataFrame(pick_rows)

owned_ids = set()
for r in rosters:
    for pid in r.get("players") or []:
        owned_ids.add(str(pid))

rankings = normalize_rankings(load_rankings())
if not rankings.empty:
    rankings["drafted"] = rankings["sleeper_id"].astype(str).isin(drafted_ids)
    rankings["rostered"] = rankings["sleeper_id"].astype(str).isin(owned_ids)
    available = rankings[(~rankings["drafted"]) & (~rankings["rostered"])]
else:
    available = pd.DataFrame()

current_pick = league.get("metadata", {}).get("current_pick_no", draft.get("settings", {}).get("current_pick"))
on_clock_id = league.get("metadata", {}).get("on_the_clock_user_id")
on_clock_user = user_by_id.get(str(on_clock_id), {}) if on_clock_id else {}
on_clock_name = on_clock_user.get("metadata", {}).get("team_name") or on_clock_user.get("display_name", "Unknown")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Draft Status", draft.get("status", "unknown"))
c2.metric("Current Pick", current_pick or "?")
c3.metric("On Clock", on_clock_name)
c4.metric("Picks Made", len(picks))

if horo_user:
    st.success(f"Detected HORO1: roster {horo_roster_id}")
else:
    st.warning("HORO1 was not found in the users endpoint.")

tabs = st.tabs(["Draft Board", "Best Available", "HoRo Roster", "League Teams", "Trade Ideas", "Trending", "Raw Data"])

with tabs[0]:
    st.subheader("Live Draft Board")
    st.dataframe(draft_df, use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("Best Available")
    if available.empty:
        st.info("FantasyCalc ranking files were not found or could not be parsed.")
    else:
        show = available[["player", "pos", "team", "rank", "value", "source", "sleeper_id"]].head(75)
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.markdown("### By Position")
        for pos in ["QB", "RB", "WR", "TE"]:
            posdf = available[available["pos"].astype(str).str.upper() == pos].head(15)
            if not posdf.empty:
                st.markdown(f"**{pos}**")
                st.dataframe(posdf[["player", "team", "rank", "value", "source"]], use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("HoRo / HORO1 Roster")
    if horo_roster_id:
        rr = next((r for r in rosters if r.get("roster_id") == horo_roster_id), None)
        st.json(rr)
    else:
        st.info("HORO1 roster not detected.")

with tabs[3]:
    st.subheader("League Teams")
    team_rows = []
    for r in rosters:
        u = user_by_id.get(str(r.get("owner_id")), {})
        team_rows.append({
            "Roster": r.get("roster_id"),
            "Display": u.get("display_name"),
            "Team Name": u.get("metadata", {}).get("team_name", ""),
            "Players": len(r.get("players") or []),
            "Taxi": len(r.get("taxi") or []),
            "Reserve": len(r.get("reserve") or []),
            "FAAB Used": r.get("settings", {}).get("waiver_budget_used")
        })
    st.dataframe(pd.DataFrame(team_rows), use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("Trade Ideas Framework")
    st.write("Version 1 flags teams by roster size and pick inventory. More detailed player-value trade logic can be added next.")
    pick_df = pd.DataFrame(traded)
    if not pick_df.empty:
        st.markdown("### Future Pick Movement")
        st.dataframe(pick_df, use_container_width=True, hide_index=True)
    st.markdown("### Quick targets")
    st.write("Look for teams with surplus at your need positions and teams holding extra future picks. Use the League Teams + Best Available tabs together during the draft.")

with tabs[5]:
    st.subheader("Sleeper Trending")
    a = pd.DataFrame(trending_add)
    d = pd.DataFrame(trending_drop)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Adds")
        st.dataframe(a, use_container_width=True, hide_index=True)
    with col2:
        st.markdown("### Drops")
        st.dataframe(d, use_container_width=True, hide_index=True)

with tabs[6]:
    st.subheader("Data Status")
    st.write("Last refresh:", datetime.now(timezone.utc).isoformat())
    st.json({"league_id": LEAGUE_ID, "draft_id": DRAFT_ID, "horo_roster_id": horo_roster_id, "files_saved_to": str(DATA_DIR)})
