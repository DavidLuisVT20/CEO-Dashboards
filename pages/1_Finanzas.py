"""Finanzas dashboard page · Addiuva BI."""

import sys
from pathlib import Path

# Make the project root importable so `shared` resolves regardless of the cwd
# Streamlit is launched from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from shared.render import render_dashboard

render_dashboard(
    jsx_path=str(_PROJECT_ROOT / "assets" / "finanzas.jsx"),
    page_title="Finanzas · Addiuva BI",
    page_icon="💎",
    # Real data lives in a LOCAL, gitignored JSON. Absent in production (Streamlit
    # Cloud) -> no injection -> finanzas.jsx uses its built-in mock.
    inject_global="__FINANZAS_DATA__",
    inject_json_path=str(_PROJECT_ROOT / "data_pipeline" / "output" / "finanzas_payload.json"),
)
