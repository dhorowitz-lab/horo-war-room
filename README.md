# HoRo Dynasty War Room — Free Shareable Web App

This version is designed for **Streamlit Community Cloud**, which has a free tier and gives you a shareable link.

## Files
- `app.py` — the web app
- `requirements.txt` — dependencies
- `fantasycalc_dynasty_rankings.csv` — your overall dynasty rankings, if included
- `fantasycalc_dynasty_rookie_rankings.csv` — your rookie rankings, if included

## Free deployment steps

1. Create a free GitHub account if you do not have one.
2. Create a new repository named `horo-war-room`.
3. Upload all files from this folder into that repository.
4. Go to https://share.streamlit.io or https://streamlit.io/cloud.
5. Sign in with GitHub.
6. Click **New app**.
7. Select your `horo-war-room` repository.
8. Set the main file path to:

```text
app.py
```

9. Click **Deploy**.
10. Streamlit gives you a public URL you can share with your partner.

## What your partner does

They just open the Streamlit URL in their browser. No install needed.

## Updating data

The app pulls Sleeper data live from the public Sleeper API whenever you click **Update Sleeper Data** or refresh the app.

## Notes

This is free and shareable, but anyone with the link can view it unless you configure Streamlit access controls.
