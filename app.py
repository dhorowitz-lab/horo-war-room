import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

LEAGUE_ID = "1322264688641216512"
DRAFT_ID = "1322264688645390336"
HORO_DISPLAY_NAME = "HORO1"
BASE = "https://api.sleeper.app/v1"

st.set_page_config(page_title="HoRo War Room", page_icon="🏈", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.2rem;}
.metric-card {border: 1px solid #2b3240; border-radius: 14px; padding: 14px; background: #0f1724;}
.small-muted {color: #8a94a6; font-size: 0.9rem;}
.big-title {font-size: 2.1rem; font-weight: 800; margin-bottom: 0;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=60)
def get_json(url: str) -> Any:
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600)
def get_players() -> Dict[str, Any]:
    return get_json(f"{BASE}/players/nfl")

@st.cache_data(ttl=60)
def load_sleeper_bundle() -> Dict[str, Any]:
    return {
        "league": get_json(f"{BASE}/league/{LEAGUE_ID}"),
        "users": get_json(f"{BASE}/league/{LEAGUE_ID}/users"),
        "rosters": get_json(f"{BASE}/league/{LEAGUE_ID}/rosters"),
        "draft": get_json(f"{BASE}/draft/{DRAFT_ID}"),
        "picks": get_json(f"{BASE}/draft/{DRAFT_ID}/picks"),
        "traded_picks": get_json(f"{BASE}/league/{LEAGUE_ID}/traded_picks"),
        "state": get_json(f"{BASE}/state/nfl"),
        "trending_add": get_json(f"{BASE}/players/nfl/trending/add?lookback_hours=24&limit=50"),
        "trending_drop": get_json(f"{BASE}/players/nfl/trending/drop?lookback_hours=24&limit=50"),
    }

@st.cache_data(ttl=300)
def load_rankings() -> pd.DataFrame:
    paths = ["fantasycalc_dynasty_rankings.csv", "fantasycalc_dynasty_rookie_rankings.csv"]
    frames = []
    for path in paths:
        try:
            df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
            df["_source"] = path
            frames.append(df)
        except Exception:
            pass
    if not frames:
        return pd.DataFrame()
    raw = pd.concat(frames, ignore_index=True)
    cols = {c.lower().strip(): c for c in raw.columns}
    def pick(*names):
        for n in names:
            if n in cols: return cols[n]
        return None
    name_col = pick("player", "name", "full_name", "player name")
    pos_col = pick("position", "pos")
    team_col = pick("team", "nfl team")
    rank_col = pick("rank", "overall rank", "overall", "dynasty rank")
    val_col = pick("value", "trade value", "fantasycalc value")
    sleeper_col = pick("sleeper id", "sleeper_id", "sleeper player id", "player_id")
    out = pd.DataFrame()
    out["name"] = raw[name_col].astype(str) if name_col else ""
    out["pos"] = raw[pos_col].astype(str) if pos_col else ""
    out["team"] = raw[team_col].astype(str) if team_col else ""
    out["rank"] = pd.to_numeric(raw[rank_col], errors="coerce") if rank_col else range(1, len(raw)+1)
    out["value"] = pd.to_numeric(raw[val_col], errors="coerce") if val_col else None
    out["sleeper_id"] = raw[sleeper_col].astype(str) if sleeper_col else ""
    out["source"] = raw["_source"]

    # Clean fields robustly. FantasyCalc exports may include blank rows and draft-pick assets.
    for col in ["name", "pos", "team", "sleeper_id"]:
        out[col] = out[col].astype(str).str.strip().str.strip('"')

    out = out.dropna(subset=["rank"]).sort_values(["rank", "source"])

    invalid = ["", "nan", "none", "null"]
    valid_name = ~out["name"].str.lower().isin(invalid)
    valid_id = ~out["sleeper_id"].str.lower().isin(invalid)
    out = out[valid_name | valid_id]

    # Remove FantasyCalc draft-pick assets from Best Available player pool.
    out = out[out["pos"].str.upper() != "PICK"]
    out = out[~out["name"].str.lower().str.contains(r"^20\d{2}\s+(pick|1st|2nd|3rd|4th|5th|6th|7th)", regex=True, na=False)]
    out = out[~out["sleeper_id"].str.upper().str.startswith(("DP_", "FP_"))]

    out = out.drop_duplicates(subset=["sleeper_id", "name"], keep="first")
    return out

def player_name(pid: str, players: Dict[str, Any]) -> str:
    if not pid or pid == "0": return "Empty"
    if pid in ["ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB","HOU","IND","JAX","KC","LAC","LAR","LV","MIA","MIN","NE","NO","NYG","NYJ","PHI","PIT","SEA","SF","TB","TEN","WAS"]:
        return f"{pid} DST"
    p = players.get(str(pid), {})
    return p.get("full_name") or p.get("first_name", "") + " " + p.get("last_name", "") or str(pid)

def player_pos(pid: str, players: Dict[str, Any]) -> str:
    if pid in ["ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB","HOU","IND","JAX","KC","LAC","LAR","LV","MIA","MIN","NE","NO","NYG","NYJ","PHI","PIT","SEA","SF","TB","TEN","WAS"]:
        return "DEF"
    return players.get(str(pid), {}).get("position", "")

def player_team(pid: str, players: Dict[str, Any]) -> str:
    if pid in ["ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB","HOU","IND","JAX","KC","LAC","LAR","LV","MIA","MIN","NE","NO","NYG","NYJ","PHI","PIT","SEA","SF","TB","TEN","WAS"]:
        return pid
    return players.get(str(pid), {}).get("team", "")

def users_map(users: List[dict]) -> Dict[str, dict]:
    return {u.get("user_id"): u for u in users}

def rosters_map(rosters: List[dict]) -> Dict[int, dict]:
    return {r.get("roster_id"): r for r in rosters}

def team_label(roster: dict, users_by_id: Dict[str, dict]) -> str:
    u = users_by_id.get(roster.get("owner_id"), {})
    team = (u.get("metadata") or {}).get("team_name")
    return team or u.get("display_name") or f"Roster {roster.get('roster_id')}"

def get_horo_roster(rosters: List[dict], users_by_id: Dict[str, dict]) -> Optional[dict]:
    for r in rosters:
        u = users_by_id.get(r.get("owner_id"), {})
        if u.get("display_name", "").lower() == HORO_DISPLAY_NAME.lower():
            return r
    return None

def drafted_ids(picks: List[dict]) -> set:
    return {str(p.get("player_id")) for p in picks if p.get("player_id")}

def rostered_ids(rosters: List[dict]) -> set:
    ids = set()
    for r in rosters:
        for pid in r.get("players") or []:
            ids.add(str(pid))
    return ids

def draft_board_df(picks: List[dict], rosters_by_id: Dict[int, dict], users_by_id: Dict[str, dict]) -> pd.DataFrame:
    rows = []
    for p in sorted(picks, key=lambda x: x.get("pick_no", 0)):
        meta = p.get("metadata") or {}
        roster = rosters_by_id.get(p.get("roster_id"), {})
        rows.append({
            "Pick": p.get("pick_no"),
            "Round": p.get("round"),
            "Slot": p.get("draft_slot"),
            "Player": f"{meta.get('first_name','')} {meta.get('last_name','')}".strip(),
            "Pos": meta.get("position", ""),
            "NFL": meta.get("team", ""),
            "Selected By": team_label(roster, users_by_id),
            "Sleeper ID": p.get("player_id"),
        })
    return pd.DataFrame(rows)

def roster_df(roster: dict, players: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    starters = set(roster.get("starters") or [])
    taxi = set(roster.get("taxi") or [])
    reserve = set(roster.get("reserve") or [])
    for pid in roster.get("players") or []:
        rows.append({
            "Player": player_name(str(pid), players),
            "Pos": player_pos(str(pid), players),
            "NFL": player_team(str(pid), players),
            "Slot": "Starter" if pid in starters else "Taxi" if pid in taxi else "IR" if pid in reserve else "Bench",
            "Sleeper ID": pid,
        })
    return pd.DataFrame(rows).sort_values(["Slot", "Pos", "Player"])

def best_available_df(rankings: pd.DataFrame, rosters: List[dict], picks: List[dict], players: Dict[str, Any]) -> pd.DataFrame:
    if rankings.empty:
        return pd.DataFrame()
    unavailable = rostered_ids(rosters) | drafted_ids(picks)
    drafted_names = set()
    for p in picks:
        meta = p.get("metadata") or {}
        nm = f"{meta.get('first_name','')} {meta.get('last_name','')}".strip().lower()
        if nm:
            drafted_names.add(nm)

    df = rankings.copy()
    df["sleeper_id"] = df["sleeper_id"].astype(str).str.strip()
    df["name"] = df["name"].astype(str).str.strip()
    df["pos"] = df["pos"].astype(str).str.strip()

    invalid = ["", "nan", "none", "null"]
    valid_id = ~df["sleeper_id"].str.lower().isin(invalid)

    # Remove already-drafted/rostered players by Sleeper ID when present.
    df = df[~(valid_id & df["sleeper_id"].isin(unavailable))]
    # Also remove drafted players by name because some ranking rows have missing Sleeper IDs.
    df = df[~df["name"].str.lower().isin(drafted_names)]
    # Never show FantasyCalc pick assets in this player-only board.
    df = df[df["pos"].str.upper() != "PICK"]
    df = df[~df["sleeper_id"].str.upper().str.startswith(("DP_", "FP_"))]
    df = df[~df["name"].str.lower().str.contains(r"^20\d{2}\s+(pick|1st|2nd|3rd|4th|5th|6th|7th)", regex=True, na=False)]

    # fill missing metadata from Sleeper by ID
    def clean_text(value: Any) -> str:
        if value is None or pd.isna(value):
            return ""
        text = str(value).strip()
        if text.lower() in ["", "nan", "none", "null"]:
            return ""
        return text

    def fill_name(row):
        name = clean_text(row.get("name", ""))
        if name:
            return name
        return player_name(clean_text(row.get("sleeper_id", "")), players)

    def fill_pos(row):
        pos = clean_text(row.get("pos", ""))
        return pos or player_pos(clean_text(row.get("sleeper_id", "")), players)

    def fill_team(row):
        team = clean_text(row.get("team", ""))
        return team or player_team(clean_text(row.get("sleeper_id", "")), players)

    df["Player"] = df.apply(fill_name, axis=1)
    df["Pos"] = df.apply(fill_pos, axis=1)
    df["NFL"] = df.apply(fill_team, axis=1)
    out = df.rename(columns={"rank": "Rank", "value": "Value", "source": "Source", "sleeper_id": "Sleeper ID"})
    return out[["Rank", "Player", "Pos", "NFL", "Value", "Source", "Sleeper ID"]].head(100)

def team_needs(roster: dict, players: Dict[str, Any]) -> str:
    counts = {"QB":0,"RB":0,"WR":0,"TE":0}
    for pid in roster.get("players") or []:
        pos = player_pos(str(pid), players)
        if pos in counts: counts[pos] += 1
    needs = []
    if counts["QB"] < 3: needs.append("QB")
    if counts["RB"] < 5: needs.append("RB")
    if counts["WR"] < 6: needs.append("WR")
    if counts["TE"] < 2: needs.append("TE")
    return ", ".join(needs) if needs else "Depth / value"

def league_teams_df(rosters: List[dict], users_by_id: Dict[str, dict], players: Dict[str, Any]) -> pd.DataFrame:
    rows=[]
    for r in rosters:
        counts = {"QB":0,"RB":0,"WR":0,"TE":0}
        for pid in r.get("players") or []:
            pos = player_pos(str(pid), players)
            if pos in counts: counts[pos]+=1
        u = users_by_id.get(r.get("owner_id"), {})
        rows.append({"Roster": r.get("roster_id"), "Team": team_label(r, users_by_id), "Display": u.get("display_name"), **counts, "Needs": team_needs(r, players), "FAAB Used": (r.get("settings") or {}).get("waiver_budget_used")})
    return pd.DataFrame(rows).sort_values("Roster")

def trending_df(items: List[dict], players: Dict[str, Any]) -> pd.DataFrame:
    rows=[]
    for item in items:
        pid=str(item.get("player_id"))
        rows.append({"Player": player_name(pid, players), "Pos": player_pos(pid, players), "NFL": player_team(pid, players), "Count": item.get("count"), "Sleeper ID": pid})
    return pd.DataFrame(rows)

with st.sidebar:
    st.title("🏈 HoRo War Room")
    st.caption("St. Jude Heroes Dynasty")
    if st.button("🔄 Refresh Sleeper Data", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.write("League ID")
    st.code(LEAGUE_ID)
    st.write("Draft ID")
    st.code(DRAFT_ID)
    st.caption("Built for HORO1")

try:
    bundle = load_sleeper_bundle()
    players = get_players()
except Exception as e:
    st.error(f"Could not load Sleeper data: {e}")
    st.stop()

rankings = load_rankings()
users_by_id = users_map(bundle["users"])
rosters_by_id = rosters_map(bundle["rosters"])
horo = get_horo_roster(bundle["rosters"], users_by_id)
league = bundle["league"]
draft = bundle["draft"]
picks = bundle["picks"]

st.markdown('<p class="big-title">HoRo Dynasty War Room</p>', unsafe_allow_html=True)
st.caption(f"Last refreshed in app: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

c1,c2,c3,c4 = st.columns(4)
c1.metric("Draft Status", draft.get("status", "unknown"))
c2.metric("Current Pick", (league.get("metadata") or {}).get("current_pick_no", "—"))
on_clock_id = (league.get("metadata") or {}).get("on_the_clock_user_id")
on_clock = users_by_id.get(on_clock_id, {}).get("display_name", "—")
c3.metric("On Clock", on_clock)
c4.metric("Picks Made", len(picks))

tabs = st.tabs(["🏈 Draft Board", "⭐ Best Available", "👤 HORO1", "👥 League Teams", "🤝 Trade Ideas", "📈 Trending", "⚙️ Data"])

with tabs[0]:
    st.subheader("Live Draft Board")
    board = draft_board_df(picks, rosters_by_id, users_by_id)
    st.dataframe(board, width="stretch", hide_index=True)

with tabs[1]:
    st.subheader("Best Available")
    ba = best_available_df(rankings, bundle["rosters"], picks, players)
    if ba.empty:
        st.warning("No rankings loaded. Make sure FantasyCalc CSV files are in this repo.")
    else:
        pos = st.multiselect("Filter position", sorted([p for p in ba["Pos"].dropna().unique() if p]), default=[])
        show = ba if not pos else ba[ba["Pos"].isin(pos)]
        st.dataframe(show.head(50), width="stretch", hide_index=True)
        st.info("Draft recommendation for HORO1: prioritize the top remaining WR/RB value unless an elite SuperFlex QB falls.")

with tabs[2]:
    st.subheader("HORO1 Roster")
    if not horo:
        st.error("Could not find HORO1 in league users. Check display name spelling.")
    else:
        st.write(f"Roster ID: {horo.get('roster_id')} | Owner ID: {horo.get('owner_id')}")
        st.dataframe(roster_df(horo, players), width="stretch", hide_index=True)

with tabs[3]:
    st.subheader("All League Teams")
    teams = league_teams_df(bundle["rosters"], users_by_id, players)
    st.dataframe(teams, width="stretch", hide_index=True)

with tabs[4]:
    st.subheader("Trade Ideas")
    st.write("These are rule-based starting points from roster construction. Use them to start conversations, not as final offers.")
    teams = league_teams_df(bundle["rosters"], users_by_id, players)
    if horo:
        horo_needs = team_needs(horo, players)
        st.write(f"**HORO1 needs:** {horo_needs}")
    trade_rows=[]
    for _, row in teams.iterrows():
        if row["Display"] == HORO_DISPLAY_NAME: continue
        fit=[]
        if row["QB"] >= 3: fit.append("QB surplus")
        if row["RB"] >= 6: fit.append("RB surplus")
        if row["WR"] >= 7: fit.append("WR surplus")
        if row["TE"] >= 3: fit.append("TE surplus")
        if fit:
            trade_rows.append({"Team": row["Team"], "Display": row["Display"], "Potential Angle": ", ".join(fit), "Their Needs": row["Needs"]})
    st.dataframe(pd.DataFrame(trade_rows), width="stretch", hide_index=True)
    st.markdown("""
**Suggested approach:** target teams with a surplus at the position you need and offer depth/picks rather than core assets. For HORO1, avoid moving foundational QBs or Trey McBride unless the return is overwhelming.
""")

with tabs[5]:
    st.subheader("Sleeper Trending")
    a,b = st.columns(2)
    with a:
        st.write("Trending Adds")
        st.dataframe(trending_df(bundle["trending_add"], players), width="stretch", hide_index=True)
    with b:
        st.write("Trending Drops")
        st.dataframe(trending_df(bundle["trending_drop"], players), width="stretch", hide_index=True)

with tabs[6]:
    st.subheader("Data Status")
    st.json({
        "league_id": LEAGUE_ID,
        "draft_id": DRAFT_ID,
        "league_status": league.get("status"),
        "season": league.get("season"),
        "draft_status": draft.get("status"),
        "picks_loaded": len(picks),
        "rosters_loaded": len(bundle["rosters"]),
        "users_loaded": len(bundle["users"]),
        "rankings_loaded": len(rankings),
    })
