# Finanzas Dashboard · Addiuva BI (Showroom)

Interactive React + D3 financial dashboard wrapped for free deployment on
**Streamlit Community Cloud**. Intended for demos, stakeholder reviews, and
pre-production validation — not for handling live financial data.

---

## Architecture

```
streamlit_app/
├── app.py              # Streamlit shell. Reads dashboard.jsx, strips ES-module
│                         syntax, embeds as an HTML component inside an iframe.
├── dashboard.jsx       # The React+D3 source (identical to the production
│                         visual — editable, canonical file).
├── requirements.txt    # Just `streamlit`. No build tooling.
└── README.md           # You are here.
```

No bundler, no npm, no webpack. JSX is transpiled in-browser by
`@babel/standalone` (~1–2 s first paint). Not production-grade, deliberately —
this is the "showroom path". The production path uses the same `dashboard.jsx`
via the Power BI Custom Visuals SDK (`pbiviz`), which is the real deploy target.

---

## Run locally

```bash
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
```

App opens at `http://localhost:8501`.

---

## Deploy free (Streamlit Community Cloud)

1. **Push to GitHub.** Make a public repo with these three files at the root:
   ```
   app.py
   dashboard.jsx
   requirements.txt
   ```

2. **Go to [share.streamlit.io](https://share.streamlit.io)** and sign in with
   GitHub.

3. **Click "New app"** → pick the repo → set `app.py` as the entry point →
   deploy.

4. Takes ~2 min. You get a public URL like
   `https://addiuva-finanzas.streamlit.app`.

**Tier limits (free):** 1 GB RAM per app, public-only, sleeps after ~7 days of
inactivity and wakes on request. Fine for showroom / stakeholder access.

---

## Editing the dashboard

All logic lives in `dashboard.jsx`. The file is a regular ES-module React
component — `app.py` strips the `import` / `export default` lines at runtime so
the same file works both:

- In the production Power BI visual (via `pbiviz` bundler, which respects the
  module system), and
- In this Streamlit showroom (where it runs through `@babel/standalone` in the
  browser).

This means **changes you make in `dashboard.jsx` propagate to both targets
without duplication**.

---

## What's NOT in this deployment

The Streamlit showroom version is frozen mock data (the 9 KPIs and 2 chart
series from the Feb 2026 image). It doesn't connect to:

- Odoo / IFC reconciliation pipeline
- Redshift `fact_kpi_actuals` table
- Power BI `dataView` contract

For the production path, `visual.ts` + `FinancialAdapterExtended` handle all of
the above — see the main BI repo for that.

---

## Troubleshooting

**Dashboard doesn't render, blank screen.**
Open the browser devtools console. If you see `Babel is not defined`, the CDN
scripts were blocked. Try a different network or pin the versions in
`app.py`'s `HTML_HEAD`.

**Cards look cramped / misaligned.**
Streamlit's iframe fixes its height at 1500 px. If you need more, bump the
`height=1500` argument in `app.py`'s final line. `scrolling=True` is already on.

**"ReferenceError: process is not defined" or similar.**
The JSX is pulling in a build-tool-only global. Grep `dashboard.jsx` for
`process.env` and replace with a literal default.

---

## Migration to the real Power BI visual

When ready to move off Streamlit into production:

1. `dashboard.jsx` → `src/visuals/FinanzasDashboard/FinanzasDashboardGrid.tsx`
   (add back the import statements and `export default`)
2. Wire into `FinanzasDashboardVisual` (extends `BaseVisual`) — already written
   in the main chat thread.
3. `pbiviz package` → `.pbiviz` file → upload to Power BI Service.

Same atoms, same grid, same tokens. Only the outer shell changes.
