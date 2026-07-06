from __future__ import annotations
from typing import Any, Dict, List, Optional, Set
import pandas as pd

NFL_TEAMS = set("ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS".split())
POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF"]

def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text

def users_map(users: List[dict]) -> Dict[str, dict]:
    return {str(u.get("user_id")): u for u in users}

def rosters_map(rosters: List[dict]) -> Dict[int, dict]:
    return {int(r.get("roster_id")): r for r in rosters if r.get("roster_id") is not None}

def team_label_from_user(u: dict) -> str:
    meta = u.get("metadata") or {}
    return clean_text(meta.get("team_name")) or clean_text(u.get("display_name")) or "Unknown"

def team_label(roster: dict, users_by_id: Dict[str, dict]) -> str:
    u = users_by_id.get(str(roster.get("owner_id")), {})
    return team_label_from_user(u) or f"Roster {roster.get('roster_id')}"

def display_name(roster: dict, users_by_id: Dict[str, dict]) -> str:
    u = users_by_id.get(str(roster.get("owner_id")), {})
    return clean_text(u.get("display_name"))

def get_horo_roster(rosters: List[dict], users_by_id: Dict[str, dict], horo_display: str = "HORO1") -> Optional[dict]:
    for r in rosters:
        if display_name(r, users_by_id).lower() == horo_display.lower():
            return r
    return None

def player_record(pid: str, players: Dict[str, Any]) -> dict:
    return players.get(str(pid), {}) if pid else {}

def player_name(pid: str, players: Dict[str, Any]) -> str:
    pid = str(pid)
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
    return (first + " " + last).strip() or pid

def player_pos(pid: str, players: Dict[str, Any]) -> str:
    pid = str(pid)
    if pid in NFL_TEAMS:
        return "DEF"
    p = player_record(pid, players)
    return clean_text(p.get("position")) or clean_text((p.get("fantasy_positions") or [""])[0])

def player_team(pid: str, players: Dict[str, Any]) -> str:
    pid = str(pid)
    if pid in NFL_TEAMS:
        return pid
    return clean_text(player_record(pid, players).get("team"))

def player_age(pid: str, players: Dict[str, Any]) -> str:
    v = player_record(str(pid), players).get("age")
    return "" if v in [None, ""] else str(v)

def rostered_ids(rosters: List[dict]) -> Set[str]:
    ids: Set[str] = set()
    for r in rosters:
        for pid in r.get("players") or []:
            ids.add(str(pid))
    return ids

def drafted_ids(picks: List[dict]) -> Set[str]:
    return {str(p.get("player_id")) for p in picks if p.get("player_id")}

def drafted_names(picks: List[dict]) -> Set[str]:
    names = set()
    for p in picks:
        m = p.get("metadata") or {}
        name = f"{m.get('first_name','')} {m.get('last_name','')}".strip().lower()
        if name:
            names.add(name)
    return names

def rostered_names(rosters: List[dict], players: Dict[str, Any]) -> Set[str]:
    return {player_name(pid, players).lower() for pid in rostered_ids(rosters) if player_name(pid, players) != "Empty"}

def roster_df(roster: dict, players: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    starters = set(str(x) for x in (roster.get("starters") or []))
    taxi = set(str(x) for x in (roster.get("taxi") or []))
    reserve = set(str(x) for x in (roster.get("reserve") or []))
    for pid in roster.get("players") or []:
        spid = str(pid)
        rows.append({
            "Slot": "Starter" if spid in starters else "Taxi" if spid in taxi else "IR" if spid in reserve else "Bench",
            "Pos": player_pos(spid, players),
            "Player": player_name(spid, players),
            "NFL": player_team(spid, players),
            "Age": player_age(spid, players),
            "Sleeper ID": spid,
        })
    if not rows:
        return pd.DataFrame(columns=["Slot","Pos","Player","NFL","Age","Sleeper ID"])
    order = {"Starter": 0, "Bench": 1, "Taxi": 2, "IR": 3}
    df = pd.DataFrame(rows)
    df["_slot_order"] = df["Slot"].map(order).fillna(9)
    return df.sort_values(["_slot_order", "Pos", "Player"]).drop(columns="_slot_order")

def drafted_by_team_df(roster_id: int, picks: List[dict]) -> pd.DataFrame:
    rows = []
    for p in sorted(picks, key=lambda x: x.get("pick_no", 0)):
        if int(p.get("roster_id") or -1) != int(roster_id):
            continue
        m = p.get("metadata") or {}
        rows.append({
            "Pick": p.get("pick_no"),
            "Round": p.get("round"),
            "Slot": p.get("draft_slot"),
            "Player": f"{m.get('first_name','')} {m.get('last_name','')}".strip(),
            "Pos": m.get("position", ""),
            "NFL": m.get("team", ""),
            "Sleeper ID": p.get("player_id"),
        })
    return pd.DataFrame(rows)

def draft_board_df(picks: List[dict], rosters_by_id: Dict[int, dict], users_by_id: Dict[str, dict]) -> pd.DataFrame:
    rows = []
    for p in sorted(picks, key=lambda x: x.get("pick_no", 0)):
        m = p.get("metadata") or {}
        rid = int(p.get("roster_id") or 0)
        roster = rosters_by_id.get(rid, {})
        rows.append({
            "Pick": p.get("pick_no"),
            "Round": p.get("round"),
            "Slot": p.get("draft_slot"),
            "Player": f"{m.get('first_name','')} {m.get('last_name','')}".strip(),
            "Pos": m.get("position", ""),
            "NFL": m.get("team", ""),
            "Selected By": team_label(roster, users_by_id),
            "Display": display_name(roster, users_by_id),
            "Roster ID": rid,
        })
    return pd.DataFrame(rows)

def position_counts(roster: dict, players: Dict[str, Any]) -> Dict[str, int]:
    counts = {p: 0 for p in POSITIONS}
    for pid in roster.get("players") or []:
        pos = player_pos(str(pid), players)
        if pos in counts:
            counts[pos] += 1
    return counts

def team_needs_from_counts(c: Dict[str, int]) -> str:
    needs = []
    if c.get("QB", 0) < 3: needs.append("QB")
    if c.get("RB", 0) < 5: needs.append("RB")
    if c.get("WR", 0) < 6: needs.append("WR")
    if c.get("TE", 0) < 2: needs.append("TE")
    return ", ".join(needs) if needs else "Depth / BPA"

def team_surplus_from_counts(c: Dict[str, int]) -> str:
    surplus = []
    if c.get("QB", 0) >= 4: surplus.append("QB")
    if c.get("RB", 0) >= 6: surplus.append("RB")
    if c.get("WR", 0) >= 8: surplus.append("WR")
    if c.get("TE", 0) >= 3: surplus.append("TE")
    return ", ".join(surplus) if surplus else "None"

def league_teams_df(rosters: List[dict], users_by_id: Dict[str, dict], players: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for r in sorted(rosters, key=lambda x: int(x.get("roster_id") or 0)):
        c = position_counts(r, players)
        rows.append({
            "Roster ID": r.get("roster_id"),
            "Team": team_label(r, users_by_id),
            "Display": display_name(r, users_by_id),
            **c,
            "Needs": team_needs_from_counts(c),
            "Surplus": team_surplus_from_counts(c),
            "Players": len(r.get("players") or []),
            "FAAB Used": (r.get("settings") or {}).get("waiver_budget_used"),
        })
    return pd.DataFrame(rows)

def current_pick_owner_map(rosters: List[dict], traded_picks: List[dict], seasons=("2026", "2027"), rounds=range(1, 8)) -> Dict[tuple, int]:
    roster_ids = [int(r.get("roster_id")) for r in rosters]
    owner = {}
    for season in seasons:
        for original_roster_id in roster_ids:
            for rd in rounds:
                owner[(str(season), original_roster_id, int(rd))] = original_roster_id
    for t in traded_picks or []:
        try:
            key = (str(t.get("season")), int(t.get("roster_id")), int(t.get("round")))
            owner[key] = int(t.get("owner_id"))
        except Exception:
            continue
    return owner

def future_picks_df(team_roster_id: int, rosters: List[dict], traded_picks: List[dict], users_by_id: Dict[str, dict], seasons=("2026", "2027")) -> pd.DataFrame:
    rosters_by_id = rosters_map(rosters)
    ownermap = current_pick_owner_map(rosters, traded_picks, seasons=seasons)
    rows = []
    for (season, original_rid, rd), current_owner in sorted(ownermap.items()):
        if int(current_owner) != int(team_roster_id):
            continue
        original_team = team_label(rosters_by_id.get(original_rid, {"roster_id": original_rid}), users_by_id)
        rows.append({
            "Season": season,
            "Round": rd,
            "Original Team": original_team,
            "Original Roster ID": original_rid,
            "Pick Label": f"{season} R{rd}" + ("" if original_rid == team_roster_id else f" from {original_team}"),
        })
    return pd.DataFrame(rows)

def rb_trade_finder_df(rosters: List[dict], users_by_id: Dict[str, dict], players: Dict[str, Any], horo_display="HORO1") -> pd.DataFrame:
    rows = []
    for r in rosters:
        disp = display_name(r, users_by_id)
        if disp.lower() == horo_display.lower():
            continue
        c = position_counts(r, players)
        rb_surplus = max(0, c.get("RB", 0) - 5)
        wr_need = c.get("WR", 0) < 6
        fit_score = rb_surplus * 2 + (2 if wr_need else 0)
        if c.get("RB", 0) >= 5 or wr_need:
            rows.append({
                "Team": team_label(r, users_by_id),
                "Display": disp,
                "Roster ID": r.get("roster_id"),
                "RBs": c.get("RB", 0),
                "WRs": c.get("WR", 0),
                "TEs": c.get("TE", 0),
                "Needs": team_needs_from_counts(c),
                "Surplus": team_surplus_from_counts(c),
                "RB Trade Fit": fit_score,
                "Angle": "RB surplus + WR need" if rb_surplus and wr_need else "RB depth" if rb_surplus else "May need WR",
            })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["RB Trade Fit", "RBs"], ascending=False)
