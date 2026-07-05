from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd
import streamlit as st

from services.sleeper import clear_cache, load_league_bundle, load_players, player_name, player_pos, player_team
from services.league import (
    drafted_ids,
    drafted_names,
    draft_board_dataframe,
    get_horo_roster,
    league_teams_dataframe,
    roster_dataframe,
    rostered_ids,
    rostered_names,
    rosters_by_id,
    users_by_id,
)
from services.rankings import best_available_dataframe, load_rankings
from services.trade import rb_trade_targets, trade_fit_dataframe

DEFAULT_LEAGUE_ID = "1322264688641216512"
DEFAULT_DRAFT_ID = "1322264688645390336"
DEFAULT_HORO_DISPLAY = "HORO1"

st.set_page_config(page_title="HoRo War Room", page_icon="🏈", layout="wide")
st.markdown(
    """
<style>
.block-container {padding-top: 1rem;}
.big-title {font-size: 2.25rem; font-weight: 850; margin-bottom: 0;}
.small-muted {color: #9ca3af; font-size: 0.92rem;}
.good {color: #86efac; font-weight: 700;}
.warn {color: #fde68a; font-weight: 700;}
</style>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("🏈 HoRo War Room")
    st.caption("Live Sleeper-based league intelligence")
    league_id = st.text_input("Sleeper League ID", DEFAULT_LEAGUE_ID)
    draft_id = st.text_input("Sleeper Draft ID", DEFAULT_DRAFT_ID)
    horo_display = st.text_input("Your Sleeper Display Name", DEFAULT_HORO_DISPLAY)
    if st.button("🔄 Refresh Sleeper Data", width="stretch"):
        clear_cache()
        st.rerun()
    st.divider()
    st.caption("v2: Sleeper is the source of truth. Rankings are only used after unavailable players are removed.")

try:
    bundle = load_league_bundle(league_id, draft_id)
    players = load_players()
except Exception as exc:
    st.error(f"Could not load Sleeper data: {exc}")
    st.stop()

users = users_by_id(bundle["users"])
rosters = rosters_by_id(bundle["rosters"])
horo = get_horo_roster(bundle["rosters"], users, horo_display)
picks = bundle["picks"]
league = bundle["league"]
draft = bundle["draft"]
rankings = load_rankings()

unavailable_ids = rostered_ids(bundle["rosters"]) | drafted_ids(picks)
unavailable_names = rostered_names(bundle["rosters"], players) | drafted_names(picks)

st.markdown('<p class="big-title">HoRo Dynasty War Room</p>', unsafe_allow_html=True)
st.caption(f"Refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Draft Status", draft.get("status", "unknown"))
c2.metric("Current Pick", (league.get("metadata") or {}).get("current_pick_no", "—"))
on_clock_id = (league.get("metadata") or {}).get("on_the_clock_user_id")
c3.metric("On Clock", (users.get(str(on_clock_id), {}) or {}).get("display_name", "—"))
c4.metric("Picks Made", len(picks))
c5.metric("Ranked Players", len(rankings))

if not horo:
    st.warning(f"Could not find your roster for display name '{horo_display}'. Check the sidebar value.")

tabs = st.tabs([
    "🏈 Draft Board",
    "⭐ Best Available",
    "👤 My Team",
    "👥 League Teams",
    "🤝 RB Trade Finder",
    "📈 Trending",
    "🧪 Diagnostics",
])

with tabs[0]:
    st.subheader("Live Draft Board")
    board = draft_board_dataframe(picks, rosters, users)
    st.dataframe(board, width="stretch", hide_index=True)

with tabs[1]:
    st.subheader("Best Available")
    st.caption("This removes drafted and rostered players using Sleeper IDs and normalized player names.")
    ba = best_available_dataframe(rankings, players, unavailable_ids, unavailable_names)
    if ba.empty:
        st.warning("No available ranked players found. Check Diagnostics for ranking import and filters.")
    else:
        positions = sorted([p for p in ba["Pos"].dropna().unique() if p])
        selected = st.multiselect("Filter by position", positions, default=[])
        view = ba if not selected else ba[ba["Pos"].isin(selected)]
        st.dataframe(view.head(75), width="stretch", hide_index=True)
        rb_view = ba[ba["Pos"].str.upper() == "RB"].head(15)
        if not rb_view.empty:
            st.markdown("#### Top Available RBs")
            st.dataframe(rb_view, width="stretch", hide_index=True)

with tabs[2]:
    st.subheader(f"{horo_display} Roster")
    if horo:
        st.write(f"Roster ID: **{horo.get('roster_id')}** | Owner ID: `{horo.get('owner_id')}`")
        st.dataframe(roster_dataframe(horo, players), width="stretch", hide_index=True)

with tabs[3]:
    st.subheader("League Teams")
    teams = league_teams_dataframe(bundle["rosters"], users, players)
    st.dataframe(teams, width="stretch", hide_index=True)

with tabs[4]:
    st.subheader("RB Trade Finder")
    st.caption("Find teams with RB surplus and possible WR need. This excludes your own roster by display name.")
    fits = trade_fit_dataframe(bundle["rosters"], users, players, horo_display)
    st.markdown("#### Best team trade fits")
    st.dataframe(fits, width="stretch", hide_index=True)
    st.markdown("#### Individual RBs to scout")
    targets = rb_trade_targets(bundle["rosters"], users, players, horo_display)
    st.dataframe(targets, width="stretch", hide_index=True)
    st.info("Use this as a scouting list, not a final valuation. Next step is adding FantasyCalc value to estimate fair offers.")

with tabs[5]:
    st.subheader("Sleeper Trending")
    def trending_df(items):
        rows = []
        for item in items:
            pid = str(item.get("player_id"))
            rows.append({
                "Player": player_name(pid, players),
                "Pos": player_pos(pid, players),
                "NFL": player_team(pid, players),
                "Count": item.get("count"),
                "Sleeper ID": pid,
            })
        return pd.DataFrame(rows)
    a, b = st.columns(2)
    with a:
        st.markdown("#### Adds")
        st.dataframe(trending_df(bundle["trending_add"]), width="stretch", hide_index=True)
    with b:
        st.markdown("#### Drops")
        st.dataframe(trending_df(bundle["trending_drop"]), width="stretch", hide_index=True)

with tabs[6]:
    st.subheader("Diagnostics")
    st.json({
        "league_id": league_id,
        "draft_id": draft_id,
        "horo_display": horo_display,
        "horo_roster_id": horo.get("roster_id") if horo else None,
        "users_loaded": len(bundle["users"]),
        "rosters_loaded": len(bundle["rosters"]),
        "picks_loaded": len(picks),
        "rankings_loaded_after_cleaning": len(rankings),
        "unavailable_ids": len(unavailable_ids),
        "unavailable_names": len(unavailable_names),
    })
    st.markdown("#### First 25 cleaned ranking rows")
    st.dataframe(rankings.head(25), width="stretch", hide_index=True)
    st.markdown("#### Validation checks")
    checks = []
    checks.append({"Check": "HORO roster found", "Result": bool(horo)})
    if horo:
        checks.append({"Check": "HORO is excluded from RB trade finder", "Result": horo_display not in set(fits.get("Display", []))})
    checks.append({"Check": "Draft picks loaded", "Result": len(picks) > 0})
    checks.append({"Check": "Rankings loaded", "Result": len(rankings) > 0})
    st.dataframe(pd.DataFrame(checks), width="stretch", hide_index=True)
