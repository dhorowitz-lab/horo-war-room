from __future__ import annotations
from typing import Any, Dict, List
import pandas as pd

from .league import (
    display_for_roster,
    simple_team_needs,
    team_counts,
    team_name_for_roster,
    team_surpluses,
)
from .sleeper import player_name, player_pos, player_team, player_age


def top_players_by_position(roster: dict, players: Dict[str, Any], position: str, limit: int = 8) -> str:
    names = []
    for pid in roster.get("players") or []:
        pid = str(pid)
        if player_pos(pid, players) == position:
            team = player_team(pid, players)
            age = player_age(pid, players)
            extra = f" ({team})" if team else ""
            if age:
                extra += f" age {age}"
            names.append(f"{player_name(pid, players)}{extra}")
    return "; ".join(names[:limit]) if names else "—"


def trade_fit_dataframe(rosters: List[dict], user_map: Dict[str, dict], players: Dict[str, Any], horo_display_name: str) -> pd.DataFrame:
    rows = []
    for roster in rosters:
        display = display_for_roster(roster, user_map)
        if display.lower() == horo_display_name.lower():
            continue
        counts = team_counts(roster, players)
        needs = simple_team_needs(counts)
        surplus = team_surpluses(counts)
        rb_surplus_score = max(0, counts.get("RB", 0) - 5)
        wr_need_score = 2 if "WR" in needs else 0
        fit_score = rb_surplus_score * 2 + wr_need_score
        if fit_score <= 0:
            angle = "Lower priority"
        elif fit_score >= 5:
            angle = "Strong RB-for-WR fit"
        else:
            angle = "Possible RB-for-WR fit"
        rows.append({
            "Team": team_name_for_roster(roster, user_map),
            "Display": display,
            "RB": counts.get("RB", 0),
            "WR": counts.get("WR", 0),
            "QB": counts.get("QB", 0),
            "TE": counts.get("TE", 0),
            "Needs": needs,
            "Surplus": surplus,
            "Trade Fit Score": fit_score,
            "Angle": angle,
            "RBs to Scout": top_players_by_position(roster, players, "RB", 7),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["Trade Fit Score", "RB"], ascending=[False, False], kind="stable")


def rb_trade_targets(rosters: List[dict], user_map: Dict[str, dict], players: Dict[str, Any], horo_display_name: str) -> pd.DataFrame:
    rows = []
    for roster in rosters:
        display = display_for_roster(roster, user_map)
        if display.lower() == horo_display_name.lower():
            continue
        counts = team_counts(roster, players)
        needs = simple_team_needs(counts)
        for pid in roster.get("players") or []:
            pid = str(pid)
            if player_pos(pid, players) != "RB":
                continue
            rows.append({
                "Target RB": player_name(pid, players),
                "NFL": player_team(pid, players),
                "Age": player_age(pid, players),
                "Team": team_name_for_roster(roster, user_map),
                "Display": display,
                "Their RB Count": counts.get("RB", 0),
                "Their WR Count": counts.get("WR", 0),
                "Their Needs": needs,
                "Fit Note": "Best fit" if counts.get("RB", 0) >= 7 and "WR" in needs else "Scout price",
                "Sleeper ID": pid,
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["Their RB Count", "Fit Note", "Target RB"], ascending=[False, True, True], kind="stable")
