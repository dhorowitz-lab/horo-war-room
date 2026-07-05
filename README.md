# HoRo War Room - Master Matching Fix

This version fixes the Best Available tab by treating Sleeper as the source of truth.

## What changed

- FantasyCalc files are read with delimiter sniffing, so semicolon CSV files work.
- Draft pick assets such as `2026 Pick 1.01` are filtered out.
- Rostered and drafted players are removed by both Sleeper ID and normalized player name.
- A diagnostics panel is included inside the Best Available tab and Data tab.

## Install

Replace the files in your GitHub repo with these files, then commit and push.

Repository folder on Dave's Mac:

```text
/Users/davehorowitz/Documents/GitHub/horo-war-room
```

Streamlit settings:

```text
Repository: dhorowitz-lab/horo-war-room
Branch: main
Main file path: app.py
```
