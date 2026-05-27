# Legacy Streamlit Frontend

This directory contains the previous Streamlit frontend implementation. It is retained for reference and comparison while the active frontend lives in `frontend/` as a Vite React app.

Contents:

- `app.py`, `app/`, `pages/` - original Streamlit application.
- `requirements.txt` - Python dependencies for the legacy app.
- `docs/` - Streamlit-specific docs that are no longer active deployment guidance.
- `deploy/` - old platform configs for the Streamlit deployment.

Run only when intentionally working with the legacy UI:

```bash
cd frontend/legacy-streamlit
pip install -r requirements.txt
streamlit run app.py
```
