from __future__ import annotations
from typing import Any, Dict, List, Set
from pathlib import Path
import pandas as pd
from .league import clean_text, drafted_ids, drafted_names, rostered_ids, rostered_names, player_name, player_pos, player_team


def _read_csv_smart(path: str) -> pd.DataFrame:
    # FantasyCalc exports have varied across our files. Try Python sniffing first, then common separators.
    for kwargs in [dict(sep=None, engine="python"), dict(sep=","), dict(sep=";"), dict(sep="\t")]:
        try:
            df = pd.read_csv(path, **kwargs)
            if len(df.columns) > 1:
                return df
        except Exception:
            continue
    return pd.DataFrame()

def load_rankings(paths: List[str] | None = None) -> pd.DataFrame:
    paths = paths or ["fantasycalc_dynasty_rankings.csv", "fantasycalc_dynasty_rookie_rankings.csv"]
    frames = []
    for path in paths:
        if not Path(path).exists():
            continue
        df = _read_csv_smart(path)
        if not df.empty:
            df["_source"] = Path(path).name
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["name", "pos", "team", "rank", "value", "sleeper_id", "source"])
    raw = pd.concat(frames, ignore_index=True)
    cols = {clean_text(c).lower(): c for c in raw.columns}
    def pick(*names: str):
        for n in names:
            if n in cols:
                return cols[n]
        return None
    name_col = pick("player", "name", "full_name", "player name", "player_name")
    pos_col = pick("position", "pos")
    team_col = pick("team", "nfl team", "nfl_team")
    rank_col = pick("rank", "overall rank", "overall", "dynasty rank", "rookie rank")
    val_col = pick("value", "trade value", "fantasycalc value", "fc value")
    sleeper_col = pick("sleeper id", "sleeper_id", "sleeper player id", "player_id", "sleeper")
    out = pd.DataFrame()
    out["name"] = raw[name_col].map(clean_text) if name_col else ""
    out["pos"] = raw[pos_col].map(clean_text) if pos_col else ""
    out["team"] = raw[team_col].map(clean_text) if team_col else ""
    out["rank"] = pd.to_numeric(raw[rank_col], errors="coerce") if rank_col else range(1, len(raw) + 1)
    out["value"] = pd.to_numeric(raw[val_col], errors="coerce") if val_col else pd.NA
    out["sleeper_id"] = raw[sleeper_col].map(clean_text) if sleeper_col else ""
    out["source"] = raw["_source"]
    out = out.dropna(subset=["rank"])
    # Remove draft-pick assets and blank rows.
    bad_pos = {"PICK", "DP", "FP", "DRAFT PICK"}
    out = out[~out["pos"].str.upper().isin(bad_pos)]
    out = out[~out["name"].str.lower().str.contains(r"(^|\b)(pick|round|rookie pick|future pick)(\b|$)", regex=True, na=False)]
    out = out[~out["sleeper_id"].str.upper().str.startswith(("DP_", "FP_"), na=False)]
    out = out[(out["name"] != "") | (out["sleeper_id"] != "")]
    out = out.sort_values(["rank", "source"]).drop_duplicates(subset=["name", "sleeper_id"], keep="first")
    return out.reset_index(drop=True)

def best_available_df(rankings: pd.DataFrame, rosters: List[dict], picks: List[dict], players: Dict[str, Any], position: str | None = None, limit: int = 100) -> pd.DataFrame:
    if rankings.empty:
        return pd.DataFrame()
    unavailable_ids: Set[str] = rostered_ids(rosters) | drafted_ids(picks)
    unavailable_names: Set[str] = rostered_names(rosters, players) | drafted_names(picks)
    df = rankings.copy()
    df["_name_l"] = df["name"].map(lambda x: clean_text(x).lower())
    df["_sid"] = df["sleeper_id"].map(clean_text)
    valid_sid = df["_sid"] != ""
    df = df[~(valid_sid & df["_sid"].isin(unavailable_ids))]
    df = df[~df["_name_l"].isin(unavailable_names)]
    if position:
        df = df[df["pos"].str.upper() == position.upper()]
    def display_name(row):
        return clean_text(row.get("name")) or player_name(clean_text(row.get("sleeper_id")), players)
    def display_pos(row):
        return clean_text(row.get("pos")) or player_pos(clean_text(row.get("sleeper_id")), players)
    def display_team(row):
        return clean_text(row.get("team")) or player_team(clean_text(row.get("sleeper_id")), players)
    df["Player"] = df.apply(display_name, axis=1)
    df["Pos"] = df.apply(display_pos, axis=1)
    df["NFL"] = df.apply(display_team, axis=1)
    out = df.rename(columns={"rank":"Rank", "value":"Value", "source":"Source", "sleeper_id":"Sleeper ID"})
    cols = ["Rank", "Player", "Pos", "NFL", "Value", "Source", "Sleeper ID"]
    return out[cols].head(limit).reset_index(drop=True)
