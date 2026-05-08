# Free Deployment Guide (Best Option: Streamlit Community Cloud)

## Why Streamlit over Lovable for this project
- This app is already a Python + Streamlit dashboard.
- Lovable focuses on React/TypeScript generation, not native Python app hosting.
- Streamlit Community Cloud is purpose-built for this exact stack and has a free tier.

References:
- [Streamlit Community Cloud docs](https://docs.streamlit.io/deploy/streamlit-community-cloud)
- [Deploy your app (official steps)](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)
- [Lovable Python FAQ](https://lovable.dev/faq/capabilities/tech-stack/lovable-python)

## 10-minute deployment checklist
1. Push this folder to a GitHub repository.
2. Confirm these files are committed:
   - `dashboard.py`
   - `requirements.txt`
   - `processed_data/*` (all required CSV/GeoJSON files)
3. Go to [share.streamlit.io](https://share.streamlit.io/) and sign in with GitHub.
4. Click `Create app`.
5. Select your repo, branch, and set the main file path to `dashboard.py`.
6. Open `Advanced settings` and select Python `3.11`.
7. Click `Deploy`.

## Notes for free hosting behavior
- Apps can sleep after inactivity and wake on next visit.
- Dependency changes in `requirements.txt` trigger a rebuild automatically.

## If deployment fails
1. Open app logs in Streamlit Cloud and check the first error.
2. Ensure `processed_data/` exists in the repo (not only local machine).
3. Ensure the Streamlit app settings use main file path `dashboard.py`, not `build_digital_desert_model.py`.
4. Ensure the Streamlit app settings use Python `3.11`.
5. Re-run your ETL notebook and commit regenerated files if any are missing.
