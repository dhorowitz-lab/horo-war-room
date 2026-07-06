from __future__ import annotations
from typing import Any, Dict
import requests
import streamlit as st

BASE = "https://api.sleeper.app/v1"
LEAGUE_ID = "1322264688641216512"
DRAFT_ID = "1322264688645390336"

@st.cache_data(ttl=60, show_spinner=False)
def get_json(url: str) -> Any:
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=60, show_spinner="Loading Sleeper league data...")
def load_bundle(league_id: str = LEAGUE_ID, draft_id: str = DRAFT_ID) -> Dict[str, Any]:
    return {
        "league": get_json(f"{BASE}/league/{league_id}"),
        "users": get_json(f"{BASE}/league/{league_id}/users"),
        "rosters": get_json(f"{BASE}/league/{league_id}/rosters"),
        "draft": get_json(f"{BASE}/draft/{draft_id}"),
        "picks": get_json(f"{BASE}/draft/{draft_id}/picks"),
        "traded_picks": get_json(f"{BASE}/league/{league_id}/traded_picks"),
        "draft_traded_picks": get_json(f"{BASE}/draft/{draft_id}/traded_picks"),
        "state": get_json(f"{BASE}/state/nfl"),
        "trending_add": get_json(f"{BASE}/players/nfl/trending/add?lookback_hours=24&limit=50"),
        "trending_drop": get_json(f"{BASE}/players/nfl/trending/drop?lookback_hours=24&limit=50"),
    }

@st.cache_data(ttl=3600, show_spinner="Loading Sleeper player database...")
def load_players() -> Dict[str, Any]:
    return get_json(f"{BASE}/players/nfl")
