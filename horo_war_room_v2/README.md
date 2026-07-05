# HoRo War Room v2

This version uses Sleeper as the source of truth for:

- league users and team names
- rosters
- draft board
- drafted players
- rostered players
- trending adds/drops

FantasyCalc CSV files are optional ranking inputs. The app removes unavailable players by both Sleeper ID and normalized player name, and filters out draft-pick assets.

## Files to keep in the repo

- app.py
- requirements.txt
- services/
- .streamlit/
- fantasycalc_dynasty_rankings.csv (optional)
- fantasycalc_dynasty_rookie_rankings.csv (optional)

## Deploy

Streamlit Cloud settings:

- Repository: dhorowitz-lab/horo-war-room
- Branch: main
- Main file path: app.py

## Validation

Open the Diagnostics tab after deployment. It should show:

- HORO roster found = True
- HORO is excluded from RB trade finder = True
- Draft picks loaded = True
- Rankings loaded = True, if CSVs are present
