"""
Addiuva · Business Intelligence — multipage entry point.

This is the Main file path for the Streamlit Community Cloud deploy. Streamlit
auto-discovers the dashboards under pages/ and renders native sidebar navigation.
"""

import streamlit as st

st.set_page_config(
    page_title="Addiuva · Business Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Addiuva dark palette — kept lightweight (no chrome stripping) so the landing
# stays readable while the dashboard pages own the full viewport themselves.
st.markdown(
    """
    <style>
      .stApp { background: #050214; }
      .block-container { max-width: 880px; }
      h1, h2, h3, p, li { color: rgba(245, 243, 255, 0.92); }
      .addiuva-hero {
          font-size: 13px;
          letter-spacing: 0.28em;
          text-transform: uppercase;
          color: rgba(139, 70, 205, 0.95);
          margin-bottom: 0.4rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="addiuva-hero">Addiuva Enterprises</div>', unsafe_allow_html=True)
st.title("Addiuva · Business Intelligence")

st.markdown(
    """
    Centro de tableros corporativos. Esta aplicación reúne los dashboards
    ejecutivos de **Addiuva** bajo una sola URL, con navegación nativa.

    **Tableros disponibles:**

    - 💎 **Finanzas** — desempeño financiero, ingresos y rentabilidad.
    - ⚙️ **Operaciones** — métricas operativas y de servicio.
    """
)

st.info("Usa el menú lateral para navegar entre los tableros.", icon="🧭")
