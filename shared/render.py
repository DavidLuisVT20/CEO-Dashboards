"""
Shared dashboard renderer · Addiuva BI — Showroom edition
Reusable Streamlit wrapper that embeds a React + D3 dashboard as an HTML component.

Design decision: zero build step. The JSX file lives untouched; at runtime we
strip ES-module syntax (imports / exports) and hand the rest to @babel/standalone
inside an iframe. Good for demos & stakeholder reviews, not for production.

Extracted verbatim from the original single-page Finanzas app.py so that every
dashboard page (Finanzas, Operaciones, ...) shares one transpilation pipeline.
"""

from __future__ import annotations

import re
from pathlib import Path

import streamlit as st


# ---------- JSX -> browser adapter ----------
def adapt_jsx_for_browser(jsx: str) -> str:
    """
    The dashboards ship as ES modules (imports at top, default export at bottom).
    In-browser Babel doesn't resolve modules, so we:
      1. Strip all `import ...;` statements (React & d3 arrive as globals via CDN)
      2. Drop `export default` prefix (we call App() manually below)
    Everything else stays byte-for-byte identical to the source.
    """
    # Remove all import statements (single- or multi-line).
    jsx = re.sub(
        r"^\s*import\s+.+?from\s+['\"].+?['\"];?\s*$",
        "",
        jsx,
        flags=re.MULTILINE,
    )
    # Remove `export default` keyword (keeps the function/const declaration).
    jsx = re.sub(r"\bexport\s+default\s+", "", jsx)
    return jsx.strip()


# ---------- HTML shell ----------
# We assemble via concatenation (not f-strings) because the JSX contains literal
# curly braces by the thousand and escaping each one would be brutal. The shell
# is split around the <title> tag so each page can supply its own document title
# without touching the transpilation pipeline below.
_HTML_HEAD_PRE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>"""

_HTML_HEAD_POST = """</title>

  <!-- React 18 (UMD) -->
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>

  <!-- D3 v7 -->
  <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>

  <!-- Babel Standalone (in-browser JSX transpile) -->
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>

  <style>
    html, body {
      margin: 0;
      padding: 0;
      min-height: 100vh;
      background: #050214;
      overflow-x: hidden;
    }
    #root { min-height: 100vh; }

    /* Subtle loading state while Babel transpiles (~1-2s first paint) */
    .addiuva-loader {
      position: fixed; inset: 0;
      display: flex; align-items: center; justify-content: center;
      font-family: system-ui, sans-serif;
      color: rgba(245, 243, 255, 0.55);
      font-size: 12px;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      background:
        radial-gradient(ellipse at center, rgba(139,70,205,0.15) 0%, transparent 60%),
        #050214;
      z-index: -1;
    }
  </style>
</head>
<body>
  <div class="addiuva-loader">Cargando dashboard…</div>
  <div id="root"></div>

  <script type="text/babel" data-presets="env,react">
    const { useEffect, useMemo, useRef, useState } = React;

"""

_HTML_TAIL = """

    ReactDOM.createRoot(document.getElementById('root')).render(<App />);
  </script>
</body>
</html>
"""


def render_dashboard(jsx_path: str, page_title: str, page_icon: str) -> None:
    """
    Render a React + D3 dashboard inside a Streamlit page.

    Must be the first thing a page executes: it calls st.set_page_config().

    Args:
        jsx_path:   absolute path to the .jsx source file.
        page_title: browser tab / page config title.
        page_icon:  emoji or icon for the browser tab.
    """
    # set_page_config must run before any other Streamlit call on the page.
    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Strip Streamlit's default chrome so the dashboard owns the full viewport.
    # The sidebar is left intact on purpose so native multipage nav stays usable.
    st.markdown(
        """
        <style>
          #MainMenu, footer, header { visibility: hidden; }
          .stApp { background: #050214; }
          .block-container {
              padding: 0 !important;
              max-width: 100% !important;
          }
          iframe { border: 0; display: block; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    raw_jsx = Path(jsx_path).read_text(encoding="utf-8")
    clean_jsx = adapt_jsx_for_browser(raw_jsx)

    dashboard_html = (
        _HTML_HEAD_PRE + page_title + _HTML_HEAD_POST + clean_jsx + _HTML_TAIL
    )

    # Height is fixed by Streamlit's iframe; internal scroll takes care of overflow
    # on narrower viewports. 1500px covers the full grid at desktop+ widths.
    st.components.v1.html(dashboard_html, height=1500, scrolling=True)
