import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

# -----------------------------
# HoRo War Room configuration
# -----------------------------
LEAGUE_ID = "1322264688641216512"
DRAFT_ID = "1322264688645390336"
HORO_DISPLAY_NAME = "HORO1"
BASE = "https://api.sleeper.app/v1"
NFL_TEAMS = {
    "ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB",
    "HOU","IND","JAX","KC","LAC","LAR","LV","MIA","MIN","NE","NO","NYG",
    "NYJ","PHI","PIT","SEA","SF","TB","TEN","WAS"
}
BAD_TEXT = {"", "nan", "none", "null", "nat"}
FANTASYCALC_FILES = [
    "fantasycalc_dynasty_rankings.csv",
    "fantasycalc_dynasty_rookie_rankings.csv",
]

st.set_page_config(page_title="HoRo War Room", page_icon="🏈", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem;}
    .small-muted {color: #8a94a6; font-size: 0.9rem;}
    .big-title {font-size: 2.1rem; font-weight: 800; margin-bottom: 0;}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Safe text / matching helpers
# -----------------------------
def clean_text(value: Any) -> str:
    """Return a safe string. Handles NaN/None/floats without crashing."""
    try:
        if value is None or pd.isna(value):
            return ""
    except Exception:
        if value is None:
            return ""
    text = str(value).strip()
    if text.lower() in BAD_TEXT:
        return ""
    return text


def norm_name(value: Any) -> str:
    """Normalize player names so Sleeper/FantasyCalc name matching is stable."""
    text = clean_text(value).lower()
    text = text.replace("'", "").replace("’", "").replace(".", "")
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", text)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def is_valid_player_row(name: Any, pos: Any, sleeper_id: Any) -> bool:
    """Filter out FantasyCalc draft-pick assets and blank rows."""
    name_s = clean_text(name)
    pos_s = clean_text(pos).upper()
    sid_s = clean_text(sleeper_id).upper()
    if not name_s and not sid_s:
        return False
    if pos_s in {"PICK", "DP", "FP"}:
        return False
    if name_s.lower().startswith(("2026 pick", "2027 pick", "2028 pick", "2029 pick")):
        return False
    if re.match(r"^\d{4}\s+(1st|2nd|3rd|4th|5th|6th|7th)$", name_s.lower()):
        return False
    if sid_s.startswith("DP_") or sid_s.startswith("FP_"):
        return False
    return True

# -----------------------------
# Sleeper API
# -----------------------------
@st.cache_data(ttl=60, show_spinner=False)
def get_json(url: str) -> Any:
    response = requests.get(url, timeout=25)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=3600, show_spinner=False)
def get_players() -> Dict[str, Any]:
    return get_json(f"{BASE}/players/nfl")


@st.cache_data(ttl=60, show_spinner=False)
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

# -----------------------------
# FantasyCalc rankings -> master board
# -----------------------------
def read_rankings_file(path: str) -> pd.DataFrame:
    """Read FantasyCalc files even when they are semicolon-delimited or comma-delimited."""
    try:
        # sep=None with python engine sniffs delimiter correctly for comma/semicolon/tab.
        df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
        if len(df.columns) == 1 and ";" in str(df.columns[0]):
            df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
        return df
    except Exception:
        # Fallback: try standard semicolon explicitly.
        return pd.read_csv(path, sep=";", encoding="utf-8-sig")


@st.cache_data(ttl=300, show_spinner=False)
def load_rankings() -> pd.DataFrame:
    frames = []
    for path in FANTASYCALC_FILES:
        try:
            raw = read_rankings_file(path)
            raw["_source"] = path
            frames.append(raw)
        except Exception as e:
            # Keep the app running; show diagnostics on the Data tab.
            continue

    if not frames:
        return pd.DataFrame()

    raw = pd.concat(frames, ignore_index=True)
    cols = {clean_text(c).lower().strip(): c for c in raw.columns}

    def pick(*names: str) -> Optional[str]:
        for name in names:
            if name.lower() in cols:
                return cols[name.lower()]
        return None

    name_col = pick("player", "name", "full_name", "player name")
    pos_col = pick("position", "pos")
    team_col = pick("team", "nfl team")
    rank_col = pick("overallrank", "overall rank", "rank", "overall", "dynasty rank")
    val_col = pick("value", "trade value", "fantasycalc value")
    sleeper_col = pick("sleeperid", "sleeper id", "sleeper_id", "sleeper player id", "player_id")

    out = pd.DataFrame()
    out["name"] = raw[name_col].map(clean_text) if name_col else ""
    out["pos"] = raw[pos_col].map(clean_text) if pos_col else ""
    out["team"] = raw[team_col].map(clean_text) if team_col else ""
    out["rank"] = pd.to_numeric(raw[rank_col], errors="coerce") if rank_col else range(1, len(raw) + 1)
    out["value"] = pd.to_numeric(raw[val_col], errors="coerce") if val_col else pd.NA
    out["sleeper_id"] = raw[sleeper_col].map(clean_text) if sleeper_col else ""
    out["source"] = raw["_source"].map(clean_text)
    out["norm_name"] = out["name"].map(norm_name)

    out = out.dropna(subset=["rank"])
    out = out[out.apply(lambda r: is_valid_player_row(r["name"], r["pos"], r["sleeper_id"]), axis=1)]
    # Deduplicate same player appearing in both overall and rookie files. Keep best rank/value source.
    out = out.sort_values(["rank", "source"])
    out = out.drop_duplicates(subset=["sleeper_id", "norm_name"], keep="first")
    return out.reset_index(drop=True)

# -----------------------------
# Player helpers
# -----------------------------
def player_record(pid: str, players: Dict[str, Any]) -> Dict[str, Any]:
    return players.get(str(pid), {}) if pid else {}


def player_name(pid: str, players: Dict[str, Any]) -> str:
    pid = clean_text(pid)
    if not pid or pid == "0":
        return "Empty"
    if pid in NFL_TEAMS:
        return f"{pid} DST"
    p = player_record(pid, players)
    full = clean_text(p.get("full_name"))
    if full:
        return full
    first = clean_text(p.get("first_name"))
    last = clean_text(p.get("last_name"))
    return clean_text(f"{first} {last}") or pid


def player_pos(pid: str, players: Dict[str, Any]) -> str:
    pid = clean_text(pid)
    if pid in NFL_TEAMS:
        return "DEF"
    return clean_text(player_record(pid, players).get("position"))


def player_team(pid: str, players: Dict[str, Any]) -> str:
    pid = clean_text(pid)
    if pid in NFL_TEAMS:
        return pid
    return clean_text(player_record(pid, players).get("team"))


def users_map(users: List[dict]) -> Dict[str, dict]:
    return {u.get("user_id"): u for u in users}


def rosters_map(rosters: List[dict]) -> Dict[int, dict]:
    return {r.get("roster_id"): r for r in rosters}


def team_label(roster: dict, users_by_id: Dict[str, dict]) -> str:
    u = users_by_id.get(roster.get("owner_id"), {})
    team = (u.get("metadata") or {}).get("team_name")
    return clean_text(team) or clean_text(u.get("display_name")) or f"Roster {roster.get('roster_id')}"


def get_horo_roster(rosters: List[dict], users_by_id: Dict[str, dict]) -> Optional[dict]:
    for roster in rosters:
        u = users_by_id.get(roster.get("owner_id"), {})
        if clean_text(u.get("display_name")).lower() == HORO_DISPLAY_NAME.lower():
            return roster
    return None


def drafted_sets(picks: List[dict]) -> Tuple[set, set]:
    ids = set()
    names = set()
    for pick in picks:
        pid = clean_text(pick.get("player_id"))
        if pid:
            ids.add(pid)
        meta = pick.get("metadata") or {}
        name = clean_text(f"{meta.get('first_name','')} {meta.get('last_name','')}")
        n = norm_name(name)
        if n:
            names.add(n)
    return ids, names


def rostered_sets(rosters: List[dict], players: Dict[str, Any]) -> Tuple[set, set]:
    ids = set()
    names = set()
    for roster in rosters:
        for pid in roster.get("players") or []:
            pid_s = clean_text(pid)
            if pid_s:
                ids.add(pid_s)
                n = norm_name(player_name(pid_s, players))
                if n:
                    names.add(n)
    return ids, names

# -----------------------------
# Dataframe builders
# -----------------------------
def draft_board_df(picks: List[dict], rosters_by_id: Dict[int, dict], users_by_id: Dict[str, dict]) -> pd.DataFrame:
    rows = []
    for pick in sorted(picks, key=lambda x: x.get("pick_no", 0)):
        meta = pick.get("metadata") or {}
        roster = rosters_by_id.get(pick.get("roster_id"), {})
        rows.append({
            "Pick": pick.get("pick_no"),
            "Round": pick.get("round"),
            "Slot": pick.get("draft_slot"),
            "Player": clean_text(f"{meta.get('first_name','')} {meta.get('last_name','')}"),
            "Pos": clean_text(meta.get("position")),
            "NFL": clean_text(meta.get("team")),
            "Selected By": team_label(roster, users_by_id),
            "Sleeper ID": clean_text(pick.get("player_id")),
        })
    return pd.DataFrame(rows)


def roster_df(roster: dict, players: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    starters = {clean_text(x) for x in roster.get("starters") or []}
    taxi = {clean_text(x) for x in roster.get("taxi") or []}
    reserve = {clean_text(x) for x in roster.get("reserve") or []}
    for pid in roster.get("players") or []:
        pid_s = clean_text(pid)
        rows.append({
            "Player": player_name(pid_s, players),
            "Pos": player_pos(pid_s, players),
            "NFL": player_team(pid_s, players),
            "Slot": "Starter" if pid_s in starters else "Taxi" if pid_s in taxi else "IR" if pid_s in reserve else "Bench",
            "Sleeper ID": pid_s,
        })
    if not rows:
        return pd.DataFrame(columns=["Player", "Pos", "NFL", "Slot", "Sleeper ID"])
    return pd.DataFrame(rows).sort_values(["Slot", "Pos", "Player"])


def best_available_df(rankings: pd.DataFrame, rosters: List[dict], picks: List[dict], players: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, int]]:
    if rankings.empty:
        return pd.DataFrame(), {"rankings_loaded": 0}

    rostered_id, rostered_name = rostered_sets(rosters, players)
    drafted_id, drafted_name = drafted_sets(picks)
    unavailable_ids = rostered_id | drafted_id
    unavailable_names = rostered_name | drafted_name

    df = rankings.copy()
    before = len(df)
    df["sleeper_id"] = df["sleeper_id"].map(clean_text)
    df["norm_name"] = df["name"].map(norm_name)

    has_id = df["sleeper_id"].astype(bool)
    has_name = df["norm_name"].astype(bool)

    by_id = has_id & df["sleeper_id"].isin(unavailable_ids)
    by_name = has_name & df["norm_name"].isin(unavailable_names)
    df = df[~(by_id | by_name)].copy()

    # Fill display metadata from Sleeper when FantasyCalc metadata is blank.
    def display_name(row: pd.Series) -> str:
        name = clean_text(row.get("name"))
        if name:
            return name
        return player_name(clean_text(row.get("sleeper_id")), players)

    def display_pos(row: pd.Series) -> str:
        pos = clean_text(row.get("pos"))
        return pos or player_pos(clean_text(row.get("sleeper_id")), players)

    def display_team(row: pd.Series) -> str:
        team = clean_text(row.get("team"))
        return team or player_team(clean_text(row.get("sleeper_id")), players)

    df["Player"] = df.apply(display_name, axis=1)
    df["Pos"] = df.apply(display_pos, axis=1)
    df["NFL"] = df.apply(display_team, axis=1)
    df["Sleeper ID"] = df["sleeper_id"]
    out = df.rename(columns={"rank": "Rank", "value": "Value", "source": "Source"})
    out = out[["Rank", "Player", "Pos", "NFL", "Value", "Source", "Sleeper ID"]]
    out = out.sort_values(["Rank", "Value"], ascending=[True, False]).head(150)

    diagnostics = {
        "rankings_loaded": before,
        "removed_by_sleeper_id": int(by_id.sum()),
        "removed_by_name": int((by_name & ~by_id).sum()),
        "remaining": len(df),
        "rostered_ids": len(rostered_id),
        "rostered_names": len(rostered_name),
        "drafted_ids": len(drafted_id),
        "drafted_names": len(drafted_name),
    }
    return out, diagnostics


def team_needs(roster: dict, players: Dict[str, Any]) -> str:
    counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0}
    for pid in roster.get("players") or []:
        pos = player_pos(clean_text(pid), players)
        if pos in counts:
            counts[pos] += 1
    needs = []
    if counts["QB"] < 3:
        needs.append("QB")
    if counts["RB"] < 5:
        needs.append("RB")
    if counts["WR"] < 6:
        needs.append("WR")
    if counts["TE"] < 2:
        needs.append("TE")
    return ", ".join(needs) if needs else "Depth / value"


def league_teams_df(rosters: List[dict], users_by_id: Dict[str, dict], players: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for roster in rosters:
        counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0}
        for pid in roster.get("players") or []:
            pos = player_pos(clean_text(pid), players)
            if pos in counts:
                counts[pos] += 1
        user = users_by_id.get(roster.get("owner_id"), {})
        rows.append({
            "Roster": roster.get("roster_id"),
            "Team": team_label(roster, users_by_id),
            "Display": clean_text(user.get("display_name")),
            **counts,
            "Needs": team_needs(roster, players),
            "FAAB Used": (roster.get("settings") or {}).get("waiver_budget_used"),
        })
    return pd.DataFrame(rows).sort_values("Roster")


def trending_df(items: List[dict], players: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in items:
        pid = clean_text(item.get("player_id"))
        rows.append({
            "Player": player_name(pid, players),
            "Pos": player_pos(pid, players),
            "NFL": player_team(pid, players),
            "Count": item.get("count"),
            "Sleeper ID": pid,
        })
    return pd.DataFrame(rows)

# -----------------------------
# UI
# -----------------------------
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
    st.caption(f"Built for {HORO_DISPLAY_NAME}")

try:
    bundle = load_sleeper_bundle()
    players = get_players()
except Exception as exc:
    st.error(f"Could not load Sleeper data: {exc}")
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

c1, c2, c3, c4 = st.columns(4)
c1.metric("Draft Status", draft.get("status", "unknown"))
c2.metric("Current Pick", (league.get("metadata") or {}).get("current_pick_no", "—"))
on_clock_id = (league.get("metadata") or {}).get("on_the_clock_user_id")
on_clock = clean_text(users_by_id.get(on_clock_id, {}).get("display_name")) or "—"
c3.metric("On Clock", on_clock)
c4.metric("Picks Made", len(picks))

tabs = st.tabs(["🏈 Draft Board", "⭐ Best Available", "👤 HORO1", "👥 League Teams", "🤝 Trade Ideas", "📈 Trending", "⚙️ Data"])

with tabs[0]:
    st.subheader("Live Draft Board")
    board = draft_board_df(picks, rosters_by_id, users_by_id)
    st.dataframe(board, width="stretch", hide_index=True)

with tabs[1]:
    st.subheader("Best Available")
    st.caption("Built from FantasyCalc rankings, then filtered using live Sleeper rostered and drafted players by Sleeper ID and normalized player name.")
    ba, diag = best_available_df(rankings, bundle["rosters"], picks, players)
    if ba.empty:
        st.warning("No available ranked players found. Check Data tab diagnostics and FantasyCalc CSV files.")
    else:
        pos_options = sorted([p for p in ba["Pos"].dropna().unique() if clean_text(p)])
        selected_pos = st.multiselect("Filter position", pos_options, default=[])
        show = ba if not selected_pos else ba[ba["Pos"].isin(selected_pos)]
        st.dataframe(show.head(75), width="stretch", hide_index=True)
        st.info("Draft recommendation for HORO1: prioritize the top remaining WR/RB value unless an elite SuperFlex QB falls.")
    with st.expander("Best Available diagnostics"):
        st.json(diag)
        st.write("Top rows in raw rankings after import:")
        st.dataframe(rankings.head(20), width="stretch", hide_index=True)

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
        st.write(f"**HORO1 needs:** {team_needs(horo, players)}")
    trade_rows = []
    for _, row in teams.iterrows():
        if row["Display"] == HORO_DISPLAY_NAME:
            continue
        fit = []
        if row["QB"] >= 3:
            fit.append("QB surplus")
        if row["RB"] >= 6:
            fit.append("RB surplus")
        if row["WR"] >= 7:
            fit.append("WR surplus")
        if row["TE"] >= 3:
            fit.append("TE surplus")
        if fit:
            trade_rows.append({"Team": row["Team"], "Display": row["Display"], "Potential Angle": ", ".join(fit), "Their Needs": row["Needs"]})
    st.dataframe(pd.DataFrame(trade_rows), width="stretch", hide_index=True)
    st.markdown("""
**Suggested approach:** target teams with a surplus at the position you need and offer depth/picks rather than core assets. For HORO1, avoid moving foundational QBs or Trey McBride unless the return is overwhelming.
""")

with tabs[5]:
    st.subheader("Sleeper Trending")
    a, b = st.columns(2)
    with a:
        st.write("Trending Adds")
        st.dataframe(trending_df(bundle["trending_add"], players), width="stretch", hide_index=True)
    with b:
        st.write("Trending Drops")
        st.dataframe(trending_df(bundle["trending_drop"], players), width="stretch", hide_index=True)

with tabs[6]:
    st.subheader("Data Status")
    _, ba_diag = best_available_df(rankings, bundle["rosters"], picks, players)
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
        "best_available_diagnostics": ba_diag,
    })
