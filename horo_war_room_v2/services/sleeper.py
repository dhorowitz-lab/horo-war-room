from __future__ import annotations

from typing import Any, Dict, List
import requests
import streamlit as st

BASE_URL = "https://api.sleeper.app/v1"
NFL_TEAMS = {
    "ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB",
    "HOU","IND","JAX","KC","LAC","LAR","LV","MIA","MIN","NE","NO","NYG","NYJ",
    "PHI","PIT","SEA","SF","TB","TEN","WAS"
}

@st.cache_data(ttl=60, show_spinner=False)
def get_json(url: str) -> Any:
    response = requests.get(url, timeout=25)
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=60, show_spinner=False)
def load_league_bundle(league_id: str, draft_id: str) -> Dict[str, Any]:
    return {
        "league": get_json(f"{BASE_URL}/league/{league_id}"),
        "users": get_json(f"{BASE_URL}/league/{league_id}/users"),
        "rosters": get_json(f"{BASE_URL}/league/{league_id}/rosters"),
        "draft": get_json(f"{BASE_URL}/draft/{draft_id}"),
        "picks": get_json(f"{BASE_URL}/draft/{draft_id}/picks"),
        "traded_picks": get_json(f"{BASE_URL}/league/{league_id}/traded_picks"),
        "state": get_json(f"{BASE_URL}/state/nfl"),
        "trending_add": get_json(f"{BASE_URL}/players/nfl/trending/add?lookback_hours=24&limit=50"),
        "trending_drop": get_json(f"{BASE_URL}/players/nfl/trending/drop?lookback_hours=24&limit=50"),
    }

@st.cache_data(ttl=3600, show_spinner=False)
def load_players() -> Dict[str, Any]:
    return get_json(f"{BASE_URL}/players/nfl")

def clear_cache() -> None:
    st.cache_data.clear()

def is_dst(pid: str) -> bool:
    return str(pid) in NFL_TEAMS

def player_name(pid: str, players: Dict[str, Any]) -> str:
    pid = str(pid or "")
    if not pid or pid == "0":
        return "Empty"
    if is_dst(pid):
        return f"{pid} DST"
    p = players.get(pid, {}) or {}
    name = p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}".strip()
    return name or pid

def player_pos(pid: str, players: Dict[str, Any]) -> str:
    pid = str(pid or "")
    if is_dst(pid):
        return "DEF"
    return (players.get(pid, {}) or {}).get("position") or ""

def player_team(pid: str, players: Dict[str, Any]) -> str:
    pid = str(pid or "")
    if is_dst(pid):
        return pid
    return (players.get(pid, {}) or {}).get("team") or ""

def player_age(pid: str, players: Dict[str, Any]) -> Any:
    return (players.get(str(pid), {}) or {}).get("age")
