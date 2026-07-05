from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set
import pandas as pd

from .league import normalize_name, normalize_text
from .sleeper import player_name, player_pos, player_team

PICK_POSITIONS = {"PICK", "PICKS", "DRAFT PICK", "DRAFT PICKS"}
PICK_MARKERS = ("pick", "2026 ", "2027 ", "2028 ", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th")


def _read_csv_flexible(path: Path) -> pd.DataFrame:
    # FantasyCalc exports can be comma, semicolon, or tab delimited depending on source/download.
    attempts = [",", ";", "\t"]
    best = pd.DataFrame()
    for sep in attempts:
        try:
            df = pd.read_csv(path, sep=sep)
            if len(df.columns) > len(best.columns):
                best = df
        except Exception:
            continue
    return best


def _column_lookup(df: pd.DataFrame) -> Dict[str, str]:
    return {str(c).lower().strip(): c for c in df.columns}


def _pick_col(cols: Dict[str, str], *names: str) -> str | None:
    for name in names:
        if name in cols:
            return cols[name]
    return None


def load_rankings(paths: List[str] | None = None) -> pd.DataFrame:
    if paths is None:
        paths = ["fantasycalc_dynasty_rankings.csv", "fantasycalc_dynasty_rookie_rankings.csv"]
    frames = []
    for path_text in paths:
        path = Path(path_text)
        if not path.exists():
            continue
        df = _read_csv_flexible(path)
        if df.empty:
            continue
        df["_source"] = path.name
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["rank", "name", "pos", "team", "value", "sleeper_id", "source"])

    raw = pd.concat(frames, ignore_index=True)
    cols = _column_lookup(raw)
    name_col = _pick_col(cols, "player", "name", "full_name", "full name", "player name")
    pos_col = _pick_col(cols, "position", "pos")
    team_col = _pick_col(cols, "team", "nfl team", "nfl")
    rank_col = _pick_col(cols, "rank", "overall rank", "overall", "dynasty rank")
    value_col = _pick_col(cols, "value", "trade value", "fantasycalc value")
    sleeper_col = _pick_col(cols, "sleeper id", "sleeper_id", "sleeper player id", "player_id", "sleeperid")

    out = pd.DataFrame()
    out["name"] = raw[name_col].map(normalize_text) if name_col else ""
    out["pos"] = raw[pos_col].map(normalize_text) if pos_col else ""
    out["team"] = raw[team_col].map(normalize_text) if team_col else ""
    out["rank"] = pd.to_numeric(raw[rank_col], errors="coerce") if rank_col else range(1, len(raw) + 1)
    out["value"] = pd.to_numeric(raw[value_col], errors="coerce") if value_col else pd.NA
    out["sleeper_id"] = raw[sleeper_col].map(normalize_text) if sleeper_col else ""
    out["source"] = raw["_source"]

    out["name_key"] = out["name"].map(normalize_name)
    out["pos_upper"] = out["pos"].str.upper()

    # Remove FantasyCalc draft pick assets and blank junk rows.
    is_blank = (out["name_key"] == "") & (out["sleeper_id"] == "")
    is_pick_pos = out["pos_upper"].isin(PICK_POSITIONS)
    is_pick_id = out["sleeper_id"].str.upper().str.startswith(("DP_", "FP_"), na=False)
    is_pick_name = out["name"].str.lower().str.contains(r"\b(202[6-9]|203[0-9])\b.*\bpick\b|\bpick\s+\d|\b[1-7](st|nd|rd|th)\b", regex=True, na=False)

    out = out[~(is_blank | is_pick_pos | is_pick_id | is_pick_name)].copy()
    out = out.dropna(subset=["rank"]).sort_values(["rank", "source"], kind="stable")
    out = out.drop_duplicates(subset=["name_key", "sleeper_id"], keep="first")
    return out[["rank", "name", "pos", "team", "value", "sleeper_id", "source", "name_key"]]


def best_available_dataframe(
    rankings: pd.DataFrame,
    players: Dict[str, Any],
    unavailable_ids: Set[str],
    unavailable_names: Set[str],
) -> pd.DataFrame:
    if rankings.empty:
        return pd.DataFrame()
    df = rankings.copy()
    df["valid_sleeper_id"] = df["sleeper_id"].map(lambda x: bool(normalize_text(x)))
    df["id_unavailable"] = df.apply(lambda row: row["valid_sleeper_id"] and str(row["sleeper_id"]) in unavailable_ids, axis=1)
    df["name_unavailable"] = df["name_key"].isin(unavailable_names)
    df = df[~(df["id_unavailable"] | df["name_unavailable"])].copy()

    def fill_player(row: pd.Series) -> str:
        name = normalize_text(row.get("name"))
        if name:
            return name
        return player_name(str(row.get("sleeper_id", "")), players)

    def fill_pos(row: pd.Series) -> str:
        pos = normalize_text(row.get("pos"))
        if pos:
            return pos
        return player_pos(str(row.get("sleeper_id", "")), players)

    def fill_team(row: pd.Series) -> str:
        team = normalize_text(row.get("team"))
        if team:
            return team
        return player_team(str(row.get("sleeper_id", "")), players)

    df["Player"] = df.apply(fill_player, axis=1)
    df["Pos"] = df.apply(fill_pos, axis=1)
    df["NFL"] = df.apply(fill_team, axis=1)
    df["Rank"] = df["rank"]
    df["Value"] = df["value"]
    df["Source"] = df["source"]
    df["Sleeper ID"] = df["sleeper_id"]

    # Final sanity guard: no empties and no pick assets.
    df = df[df["Player"].map(normalize_text) != ""].copy()
    df = df[~df["Pos"].str.upper().isin(PICK_POSITIONS)].copy()
    return df[["Rank", "Player", "Pos", "NFL", "Value", "Source", "Sleeper ID"]].head(150)
