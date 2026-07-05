from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
import pandas as pd
from .sleeper import player_name, player_pos, player_team, player_age

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def normalize_name(value: Any) -> str:
    text = normalize_text(value).lower()
    keep = []
    for ch in text:
        if ch.isalnum() or ch.isspace():
            keep.append(ch)
    return " ".join("".join(keep).split())


def users_by_id(users: List[dict]) -> Dict[str, dict]:
    return {str(u.get("user_id")): u for u in users}


def rosters_by_id(rosters: List[dict]) -> Dict[int, dict]:
    return {int(r.get("roster_id")): r for r in rosters if r.get("roster_id") is not None}


def team_name_for_roster(roster: dict, user_map: Dict[str, dict]) -> str:
    user = user_map.get(str(roster.get("owner_id")), {}) or {}
    metadata = user.get("metadata") or {}
    return metadata.get("team_name") or user.get("display_name") or f"Roster {roster.get('roster_id')}"


def display_for_roster(roster: dict, user_map: Dict[str, dict]) -> str:
    user = user_map.get(str(roster.get("owner_id")), {}) or {}
    return user.get("display_name") or f"Roster {roster.get('roster_id')}"


def get_horo_roster(rosters: List[dict], user_map: Dict[str, dict], horo_display_name: str) -> Optional[dict]:
    target = horo_display_name.lower()
    for roster in rosters:
        user = user_map.get(str(roster.get("owner_id")), {}) or {}
        if str(user.get("display_name", "")).lower() == target:
            return roster
    return None


def rostered_ids(rosters: List[dict]) -> Set[str]:
    ids: Set[str] = set()
    for roster in rosters:
        for pid in roster.get("players") or []:
            if pid and str(pid) != "0":
                ids.add(str(pid))
    return ids


def drafted_ids(picks: List[dict]) -> Set[str]:
    return {str(p.get("player_id")) for p in picks if p.get("player_id")}


def rostered_names(rosters: List[dict], players: Dict[str, Any]) -> Set[str]:
    names: Set[str] = set()
    for pid in rostered_ids(rosters):
        name = normalize_name(player_name(pid, players))
        if name:
            names.add(name)
    return names


def drafted_names(picks: List[dict]) -> Set[str]:
    names: Set[str] = set()
    for pick in picks:
        meta = pick.get("metadata") or {}
        name = normalize_name(f"{meta.get('first_name','')} {meta.get('last_name','')}")
        if name:
            names.add(name)
    return names


def roster_dataframe(roster: dict, players: Dict[str, Any]) -> pd.DataFrame:
    starters = set(map(str, roster.get("starters") or []))
    taxi = set(map(str, roster.get("taxi") or []))
    reserve = set(map(str, roster.get("reserve") or []))
    rows = []
    for raw_pid in roster.get("players") or []:
        pid = str(raw_pid)
        if pid == "0":
            continue
        rows.append({
            "Player": player_name(pid, players),
            "Pos": player_pos(pid, players),
            "NFL": player_team(pid, players),
            "Age": player_age(pid, players),
            "Slot": "Starter" if pid in starters else "Taxi" if pid in taxi else "IR" if pid in reserve else "Bench",
            "Sleeper ID": pid,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["Slot", "Pos", "Player"], kind="stable")


def draft_board_dataframe(picks: List[dict], roster_map: Dict[int, dict], user_map: Dict[str, dict]) -> pd.DataFrame:
    rows = []
    for pick in sorted(picks, key=lambda p: p.get("pick_no", 0)):
        meta = pick.get("metadata") or {}
        roster = roster_map.get(pick.get("roster_id"), {}) or {}
        rows.append({
            "Pick": pick.get("pick_no"),
            "Round": pick.get("round"),
            "Slot": pick.get("draft_slot"),
            "Player": f"{meta.get('first_name','')} {meta.get('last_name','')}".strip(),
            "Pos": meta.get("position", ""),
            "NFL": meta.get("team", ""),
            "Selected By": team_name_for_roster(roster, user_map),
            "Display": display_for_roster(roster, user_map),
            "Sleeper ID": pick.get("player_id"),
        })
    return pd.DataFrame(rows)


def team_counts(roster: dict, players: Dict[str, Any]) -> Dict[str, int]:
    counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0}
    for pid in roster.get("players") or []:
        pos = player_pos(str(pid), players)
        if pos in counts:
            counts[pos] += 1
    return counts


def simple_team_needs(counts: Dict[str, int]) -> str:
    needs = []
    if counts.get("QB", 0) < 3:
        needs.append("QB")
    if counts.get("RB", 0) < 5:
        needs.append("RB")
    if counts.get("WR", 0) < 7:
        needs.append("WR")
    if counts.get("TE", 0) < 2:
        needs.append("TE")
    return ", ".join(needs) if needs else "Depth / value"


def team_surpluses(counts: Dict[str, int]) -> str:
    surplus = []
    if counts.get("QB", 0) >= 4:
        surplus.append("QB")
    if counts.get("RB", 0) >= 7:
        surplus.append("RB")
    if counts.get("WR", 0) >= 9:
        surplus.append("WR")
    if counts.get("TE", 0) >= 3:
        surplus.append("TE")
    return ", ".join(surplus) if surplus else "None obvious"


def league_teams_dataframe(rosters: List[dict], user_map: Dict[str, dict], players: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for roster in rosters:
        counts = team_counts(roster, players)
        rows.append({
            "Roster": roster.get("roster_id"),
            "Team": team_name_for_roster(roster, user_map),
            "Display": display_for_roster(roster, user_map),
            **counts,
            "Needs": simple_team_needs(counts),
            "Surplus": team_surpluses(counts),
            "FAAB Used": (roster.get("settings") or {}).get("waiver_budget_used"),
        })
    return pd.DataFrame(rows).sort_values("Roster", kind="stable")
