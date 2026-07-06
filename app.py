from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd
import streamlit as st

from services.sleeper import LEAGUE_ID, DRAFT_ID, load_bundle, load_players
from services.league import (
    users_map, rosters_map, team_label, display_name, get_horo_roster, roster_df,
    draft_board_df, league_teams_df, future_picks_df, drafted_by_team_df, rb_trade_finder_df,
    position_counts, team_needs_from_counts, team_surplus_from_counts, player_name, player_pos, player_team
)
from services.rankings import load_rankings, best_available_df

HORO_DISPLAY_NAME = "HORO1"

st.set_page_config(page_title="HoRo War Room v3", page_icon="🏈", layout="wide")
st.markdown("""
<style>
.block-container { padding-top: 1.1rem; }
.big-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 0; }
.small-muted { color: #8a94a6; font-size: 0.9rem; }
.card { border: 1px solid #263244; border-radius: 16px; padding: 1rem; background: rgba(30,41,59,.35); }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("🏈 HoRo War Room")
    st.caption("v3 league intelligence")
    if st.button("🔄 Refresh live Sleeper data", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.caption("League")
    st.code(LEAGUE_ID)
    st.caption("Draft")
    st.code(DRAFT_ID)
    st.caption("Built for HORO1")

try:
    bundle = load_bundle()
    players = load_players()
except Exception as e:
    st.error(f"Could not load Sleeper data: {e}")
    st.stop()

rankings = load_rankings()
users_by_id = users_map(bundle["users"])
rosters_by_id = rosters_map(bundle["rosters"])
horo = get_horo_roster(bundle["rosters"], users_by_id, HORO_DISPLAY_NAME)
league = bundle["league"]
draft = bundle["draft"]
picks = bundle["picks"]
traded_picks = bundle["traded_picks"]

st.markdown('<p class="big-title">HoRo Dynasty War Room</p>', unsafe_allow_html=True)
st.caption(f"Live Sleeper refresh in app: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Draft Status", draft.get("status", "unknown"))
c2.metric("Current Pick", (league.get("metadata") or {}).get("current_pick_no", "—"))
on_clock_id = (league.get("metadata") or {}).get("on_the_clock_user_id")
c3.metric("On Clock", users_by_id.get(str(on_clock_id), {}).get("display_name", "—"))
c4.metric("Picks Made", len(picks))

tabs = st.tabs(["🏠 Dashboard", "🏈 Draft Room", "⭐ Best Available", "👤 HORO1", "👥 League Rosters", "🤝 Trade Center", "📈 Trending", "⚙️ Diagnostics"])

with tabs[0]:
    st.subheader("League Snapshot")
    a, b = st.columns([2, 1])
    with a:
        teams = league_teams_df(bundle["rosters"], users_by_id, players)
        st.dataframe(teams, width="stretch", hide_index=True)
    with b:
        if horo:
            counts = position_counts(horo, players)
            st.markdown("### HORO1")
            st.write(f"**Roster ID:** {horo.get('roster_id')}")
            st.write(f"**Needs:** {team_needs_from_counts(counts)}")
            st.write(f"**Surplus:** {team_surplus_from_counts(counts)}")
            st.json(counts)
        else:
            st.error("HORO1 not found in Sleeper users.")

with tabs[1]:
    st.subheader("Live Draft Board")
    board = draft_board_df(picks, rosters_by_id, users_by_id)
    st.dataframe(board, width="stretch", hide_index=True)

with tabs[2]:
    st.subheader("Best Available")
    st.caption("Uses FantasyCalc files when present, then removes drafted and rostered players by Sleeper ID and normalized player name.")
    if rankings.empty:
        st.warning("No rankings loaded. Add FantasyCalc CSVs to the repo, or use the Draft Room/League tabs for live Sleeper data.")
    else:
        pos_filter = st.selectbox("Position filter", ["ALL", "QB", "RB", "WR", "TE"], index=0)
        pos = None if pos_filter == "ALL" else pos_filter
        ba = best_available_df(rankings, bundle["rosters"], picks, players, position=pos, limit=150)
        st.dataframe(ba.head(75), width="stretch", hide_index=True)
        st.caption(f"Rankings loaded: {len(rankings)} | Showing: {len(ba.head(75))}")

with tabs[3]:
    st.subheader("HORO1 Front Office")
    if not horo:
        st.error("Could not find HORO1 in league users.")
    else:
        st.markdown("### Current Roster")
        st.dataframe(roster_df(horo, players), width="stretch", hide_index=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Future Draft Picks")
            picks_df = future_picks_df(int(horo.get("roster_id")), bundle["rosters"], traded_picks, users_by_id)
            st.dataframe(picks_df, width="stretch", hide_index=True)
        with col2:
            st.markdown("### Rookie Draft Picks Made")
            drafted_df = drafted_by_team_df(int(horo.get("roster_id")), picks)
            if drafted_df.empty:
                st.info("No draft picks made by HORO1 roster in current draft data.")
            else:
                st.dataframe(drafted_df, width="stretch", hide_index=True)

with tabs[4]:
    st.subheader("League Rosters + Draft Picks")
    teams = league_teams_df(bundle["rosters"], users_by_id, players)
    labels = [f"{row['Team']} ({row['Display']}) — Roster {row['Roster ID']}" for _, row in teams.iterrows()]
    selected = st.selectbox("Choose team", labels)
    selected_rid = int(selected.split("Roster ")[-1])
    selected_roster = rosters_by_id[selected_rid]
    st.markdown(f"### {team_label(selected_roster, users_by_id)}")
    counts = position_counts(selected_roster, players)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("QB", counts.get("QB", 0)); m2.metric("RB", counts.get("RB", 0)); m3.metric("WR", counts.get("WR", 0)); m4.metric("TE", counts.get("TE", 0))
    st.write(f"**Needs:** {team_needs_from_counts(counts)}  |  **Surplus:** {team_surplus_from_counts(counts)}")
    rtab1, rtab2, rtab3 = st.tabs(["Roster", "Future Picks", "Draft Picks Made"])
    with rtab1:
        st.dataframe(roster_df(selected_roster, players), width="stretch", hide_index=True)
    with rtab2:
        st.dataframe(future_picks_df(selected_rid, bundle["rosters"], traded_picks, users_by_id), width="stretch", hide_index=True)
    with rtab3:
        df = drafted_by_team_df(selected_rid, picks)
        if df.empty:
            st.info("No current draft picks shown for this roster.")
        else:
            st.dataframe(df, width="stretch", hide_index=True)

with tabs[5]:
    st.subheader("Trade Center")
    st.markdown("### RB Trade Finder for HORO1")
    st.caption("Finds teams with RB depth and/or WR needs. HORO1 is excluded from targets.")
    trade = rb_trade_finder_df(bundle["rosters"], users_by_id, players, HORO_DISPLAY_NAME)
    st.dataframe(trade, width="stretch", hide_index=True)
    st.markdown("### Suggested Use")
    st.write("Start with teams at the top of the list. Offer WR depth or picks for RB depth, but avoid moving core assets unless the RB is a true upgrade.")

with tabs[6]:
    st.subheader("Sleeper Trending")
    def trending_df(items):
        rows=[]
        for item in items:
            pid=str(item.get("player_id"))
            rows.append({"Player": player_name(pid, players), "Pos": player_pos(pid, players), "NFL": player_team(pid, players), "Count": item.get("count"), "Sleeper ID": pid})
        return pd.DataFrame(rows)
    a, b = st.columns(2)
    with a:
        st.markdown("### Adds")
        st.dataframe(trending_df(bundle["trending_add"]), width="stretch", hide_index=True)
    with b:
        st.markdown("### Drops")
        st.dataframe(trending_df(bundle["trending_drop"]), width="stretch", hide_index=True)

with tabs[7]:
    st.subheader("Diagnostics")
    st.json({
        "league_id": LEAGUE_ID,
        "draft_id": DRAFT_ID,
        "users_loaded": len(bundle["users"]),
        "rosters_loaded": len(bundle["rosters"]),
        "picks_loaded": len(picks),
        "traded_picks_loaded": len(traded_picks),
        "rankings_loaded": len(rankings),
        "horo_found": bool(horo),
        "horo_roster_id": horo.get("roster_id") if horo else None,
        "horo_display": display_name(horo, users_by_id) if horo else None,
    })
