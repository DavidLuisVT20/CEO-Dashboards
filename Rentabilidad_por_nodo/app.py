"""
Tablero de Servicios — Addiuva
================================
Participación de servicios por estatus, nodo, país, cuenta y coordinador.
Dos perspectivas:
  • Apertura  → fecha en que se aperturó el servicio
                (Servicios_ene2025_abr2026.xlsx, hoja de creación)
  • Gestión   → fecha en que se gestionó el servicio, ya desglosado por
                coordinador de cabina (Nodo_gestion_x_agente.xlsx)

El coordinador (quien gestionó el servicio) solo existe en la perspectiva de
Gestión. Si más adelante llega "apertura por agente", se agrega igual.

Despliegue: `streamlit run app.py` (local) o Streamlit Community Cloud.
"""

from __future__ import annotations
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --------------------------------------------------------------------------- #
# Configuración base
# --------------------------------------------------------------------------- #
DATA_FILE_APERTURA = "Servicios_ene2025_abr2026.xlsx"   # apertura (hoja de creación)
SHEET_APERTURA = "Servicios por nodo creacion"
DATA_FILE_GESTION = "Nodo_gestion_x_agente.xlsx"        # gestión, ya con coordinador
SHEET_GESTION = 0                                       # única hoja del archivo de gestión

# Cuentas de prueba a excluir (editable). Atrapa IKATECH / PRUEBA / NO APERTURAR.
TEST_ACCOUNT_PATTERN = re.compile(r"(?i)prueba|ikatech|no apertur")

STATUS_ORDER = [
    "Concluido",
    "En proceso",
    "Cancelado al momento",
    "Cancelado posterior",
]
STATUS_COLORS = {
    "Concluido": "#34d399",            # emerald  — resuelto OK
    "En proceso": "#38bdf8",           # sky      — abierto
    "Cancelado al momento": "#fbbf24", # amber    — cancelado de entrada
    "Cancelado posterior": "#fb7185",  # rose     — cancelado después
}

# Paleta Addiuva (morado profundo)
INK = "#140a24"
SURFACE = "#241640"
BORDER = "#3a2a5c"
TXT = "#f4eefb"
TXT_DIM = "#b9a9d6"
TXT_MUTE = "#8b7aa8"
ACCENT = "#c084fc"
ACCENT2 = "#e879f9"
NODE_SEQ = ["#c084fc", "#7c5cff", "#22d3ee", "#f472b6", "#a78bfa", "#5eead4"]

MESES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
         7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}

# Dimensiones desagregables. Jerarquía real Nodo → País → Cuenta; el
# coordinador es transversal y solo existe en la perspectiva de Gestión.
DIMENSIONS = {
    "NODO": "Nodo",
    "SOA": "País",
    "CUENTA": "Cuenta",
    "AGENTE": "Coordinador de cabina",  # solo Gestión
}


def mes_label(ts: pd.Timestamp) -> str:
    return f"{MESES[ts.month]} {ts.year}"


# --------------------------------------------------------------------------- #
# Carga y limpieza
# --------------------------------------------------------------------------- #
def _clean(df):
    """Excluye cuentas de prueba y deriva la columna MES."""
    df = df[~df["CUENTA"].astype(str).str.contains(TEST_ACCOUNT_PATTERN)].copy()
    df["MES"] = df["PERIODO"].dt.to_period("M").dt.to_timestamp()
    return df


@st.cache_data(show_spinner=False)
def load_data(path_apertura, path_gestion):
    """Carga apertura (archivo original) y gestión (archivo con coordinador).

    Los dos archivos usan encabezados distintos, así que se normalizan a un
    esquema común: NODO, SOA, IDCUENTA, CUENTA, ESTATUS, SERVICIOS, PERIODO
    (+ COORDINADOR, NOMBRE, AGENTE, COORD_CODE en gestión).
    """
    # Apertura — hoja de creación del archivo original
    ap = pd.read_excel(path_apertura, sheet_name=SHEET_APERTURA)
    ap["PERIODO"] = pd.to_datetime(ap["PERIODO DE APERTURA"])
    ap = _clean(ap.drop(columns=["PERIODO DE APERTURA"]))

    # Gestión — archivo por agente, con encabezados distintos a normalizar
    ge = pd.read_excel(path_gestion, sheet_name=SHEET_GESTION).rename(columns={
        "ID CUENTA": "IDCUENTA", "STATUS": "ESTATUS",
        "# SERVICIOS": "SERVICIOS", "PERIODO GESTION": "PERIODO"})
    ge["PERIODO"] = pd.to_datetime(ge["PERIODO"])
    ge = _clean(ge)

    # Etiqueta del agente: nombre; si no hay nombre, el código; si no, "(Sin asignar)"
    nombre = ge["NOMBRE"].astype("string").str.strip()
    code = ge["COORDINADOR"].astype("string").str.strip()
    ge["AGENTE"] = nombre.where(nombre.notna() & (nombre != ""), code)
    ge["AGENTE"] = ge["AGENTE"].where(ge["AGENTE"].notna() & (ge["AGENTE"] != ""),
                                      "(Sin asignar)")
    ge["COORD_CODE"] = code.fillna("—").replace("", "—")

    return {"Apertura": ap, "Gestión": ge}


def dimension_maps(perspectives) -> dict:
    """Membresía jerárquica para filtros en cascada (de ambas hojas combinadas)."""
    combo = pd.concat(perspectives.values(), ignore_index=True)
    return {
        "nodos": sorted(combo["NODO"].dropna().unique()),
        "nodo_paises": combo.groupby("NODO")["SOA"].agg(lambda s: sorted(set(s))).to_dict(),
        "pais_cuentas": combo.groupby("SOA")["CUENTA"].agg(lambda s: sorted(set(s))).to_dict(),
        "meses": sorted(combo["MES"].unique()),
    }


def apply_filters(df, date_range, nodos, paises, cuentas, estatus):
    out = df
    if date_range:
        lo, hi = date_range
        out = out[(out["MES"] >= lo) & (out["MES"] <= hi)]
    if nodos:
        out = out[out["NODO"].isin(nodos)]
    if paises:
        out = out[out["SOA"].isin(paises)]
    if cuentas:
        out = out[out["CUENTA"].isin(cuentas)]
    if estatus:
        out = out[out["ESTATUS"].isin(estatus)]
    return out


# --------------------------------------------------------------------------- #
# Estética compartida de gráficos
# --------------------------------------------------------------------------- #
def _style(fig, height=320, legend=True):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TXT_DIM, family="Inter, Segoe UI, sans-serif", size=12),
        margin=dict(l=8, r=8, t=12, b=8),
        height=height,
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, x=0, font=dict(size=11)),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=BORDER, font_size=12),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    return fig


def fig_status_donut(df):
    g = (df.groupby("ESTATUS")["SERVICIOS"].sum()
           .reindex(STATUS_ORDER).fillna(0))
    g = g[g > 0]
    total = g.sum()
    # Etiqueta solo rebanadas >= 1% (evita ruido del "En proceso" ~0%)
    lbls = [f"{v/total*100:.1f}%" if v / total >= 0.01 else "" for v in g.values]
    fig = go.Figure(go.Pie(
        labels=g.index, values=g.values, hole=0.62, sort=False,
        marker=dict(colors=[STATUS_COLORS[s] for s in g.index],
                    line=dict(color=INK, width=2)),
        text=lbls, textinfo="text", textfont=dict(size=13, color="#0b0717"),
        hovertemplate="%{label}<br>%{value:,.0f} servicios<br>%{percent}<extra></extra>",
    ))
    fig.add_annotation(text=f"<b>{total:,.0f}</b><br><span style='font-size:11px'>servicios</span>",
                       showarrow=False, font=dict(size=20, color=TXT))
    return _style(fig, height=300)


def fig_trend(df):
    g = (df.groupby(["MES", "ESTATUS"])["SERVICIOS"].sum().reset_index())
    fig = go.Figure()
    for s in STATUS_ORDER:
        sub = g[g["ESTATUS"] == s]
        if sub["SERVICIOS"].sum() == 0:
            continue
        fig.add_bar(x=sub["MES"], y=sub["SERVICIOS"], name=s,
                    marker_color=STATUS_COLORS[s],
                    hovertemplate="%{x|%b %Y}<br>" + s + ": %{y:,.0f}<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.25)
    months = sorted(df["MES"].unique())
    fig.update_xaxes(tickmode="array", tickvals=months,
                     ticktext=[f"{MESES[pd.Timestamp(m).month]}<br>{pd.Timestamp(m).year}"
                               for m in months])
    return _style(fig, height=300)


def fig_participation(df, dim_col, top=None, horizontal=True):
    """Barra de participación genérica por cualquier dimensión."""
    g = df.groupby(dim_col)["SERVICIOS"].sum().sort_values(ascending=False)
    if top:
        g = g.head(top)
    total = df["SERVICIOS"].sum() or 1
    pct = g / total * 100
    g = g[::-1]; pct = pct[::-1]
    fig = go.Figure(go.Bar(
        x=g.values, y=g.index, orientation="h",
        marker=dict(color=g.values, colorscale=[[0, "#5b3aa0"], [1, ACCENT2]]),
        text=[f"{p:.1f}%" for p in pct], textposition="outside",
        textfont=dict(color=TXT_DIM, size=11),
        hovertemplate="%{y}<br>%{x:,.0f} servicios<extra></extra>",
        cliponaxis=False,
    ))
    fig.update_xaxes(showgrid=False, showticklabels=False)
    return _style(fig, height=max(220, 26 * len(g) + 60), legend=False)


def fig_status_by_dim(df, dim_col):
    """Barra 100% apilada: mezcla de estatus dentro de cada miembro de la dimensión."""
    g = df.groupby([dim_col, "ESTATUS"])["SERVICIOS"].sum().reset_index()
    tot = g.groupby(dim_col)["SERVICIOS"].transform("sum")
    g["pct"] = g["SERVICIOS"] / tot * 100
    order = (df.groupby(dim_col)["SERVICIOS"].sum().sort_values().index.tolist())
    fig = go.Figure()
    for s in STATUS_ORDER:
        sub = g[g["ESTATUS"] == s].set_index(dim_col).reindex(order)
        if sub["SERVICIOS"].fillna(0).sum() == 0:
            continue
        fig.add_bar(y=order, x=sub["pct"], orientation="h", name=s,
                    marker_color=STATUS_COLORS[s],
                    customdata=sub["SERVICIOS"],
                    hovertemplate="%{y} — " + s + "<br>%{x:.1f}%  (%{customdata:,.0f})<extra></extra>")
    fig.update_layout(barmode="stack")
    fig.update_xaxes(ticksuffix="%", range=[0, 100])
    return _style(fig, height=max(220, 30 * len(order) + 70))


def fig_treemap(df):
    g = (df.groupby(["NODO", "SOA"])["SERVICIOS"].sum().reset_index())
    g = g[g["SERVICIOS"] > 0]
    fig = px.treemap(g, path=[px.Constant("Total"), "NODO", "SOA"],
                     values="SERVICIOS", color="NODO",
                     color_discrete_sequence=NODE_SEQ)
    fig.update_traces(
        marker=dict(line=dict(color=INK, width=2)),
        textinfo="label+value+percent parent",
        textfont=dict(size=12, color="#0b0717"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} servicios<br>%{percentParent} del padre<extra></extra>",
        root_color="rgba(0,0,0,0)",
    )
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=4, r=4, t=4, b=4), height=420,
                      font=dict(color=TXT_DIM))
    return fig


def fig_coordinador(df, top=15):
    """Top-N coordinadores por servicios gestionados. Nombre visible, código en tooltip."""
    g = (df.groupby("AGENTE")
           .agg(serv=("SERVICIOS", "sum"),
                code=("COORD_CODE",
                      lambda s: "/".join(sorted({x for x in s if x != "—"})[:3]) or "—"))
           .reset_index()
           .sort_values("serv", ascending=False).head(top))
    total = df["SERVICIOS"].sum() or 1
    g["pct"] = g["serv"] / total * 100
    g = g[::-1]
    fig = go.Figure(go.Bar(
        x=g["serv"], y=g["AGENTE"], orientation="h",
        marker=dict(color=g["serv"], colorscale=[[0, "#0e4f63"], [1, "#22d3ee"]]),
        text=[f"{p:.1f}%" for p in g["pct"]], textposition="outside",
        textfont=dict(color=TXT_DIM, size=11),
        customdata=g[["code"]].values,
        hovertemplate="%{y}<br>Código: %{customdata[0]}<br>%{x:,.0f} servicios<extra></extra>",
        cliponaxis=False,
    ))
    fig.update_xaxes(showgrid=False, showticklabels=False)
    return _style(fig, height=max(240, 26 * len(g) + 60), legend=False)


# --------------------------------------------------------------------------- #
# UI helpers
# --------------------------------------------------------------------------- #
def kpi_cards(df):
    total = int(df["SERVICIOS"].sum())
    cuentas = df["CUENTA"].nunique()
    paises = df["SOA"].nunique()
    by_status = df.groupby("ESTATUS")["SERVICIOS"].sum()
    den = by_status.sum() or 1
    pct_conc = by_status.get("Concluido", 0) / den * 100
    pct_canc = (by_status.get("Cancelado al momento", 0)
                + by_status.get("Cancelado posterior", 0)) / den * 100

    cards = [
        ("Servicios totales", f"{total:,}", ACCENT),
        ("Cuentas activas", f"{cuentas:,}", "#22d3ee"),
        ("Países", f"{paises}", "#a78bfa"),
        ("% Concluido", f"{pct_conc:.1f}%", STATUS_COLORS["Concluido"]),
        ("% Cancelado", f"{pct_canc:.1f}%", STATUS_COLORS["Cancelado posterior"]),
    ]
    cols = st.columns(len(cards))
    for col, (label, value, color) in zip(cols, cards):
        col.markdown(
            f"""<div class="kpi"><div class="kpi-bar" style="background:{color}"></div>
            <div class="kpi-val">{value}</div>
            <div class="kpi-lbl">{label}</div></div>""",
            unsafe_allow_html=True)


def section(title, subtitle=""):
    sub = f"<span class='sec-sub'>{subtitle}</span>" if subtitle else ""
    st.markdown(f"<div class='sec'><span class='sec-ttl'>{title}</span>{sub}</div>",
                unsafe_allow_html=True)


def render_perspective(df, datecol_label, definition, top_n, key, show_coord=False):
    st.markdown(
        f"<div class='persp'>Periodo medido por <b>{datecol_label}</b> — {definition}</div>",
        unsafe_allow_html=True)

    if df.empty:
        st.info("No hay servicios para los filtros seleccionados. Ajusta el rango o limpia filtros.")
        return

    kpi_cards(df)
    st.write("")

    c1, c2 = st.columns([1, 1.4])
    with c1:
        section("Participación por estatus")
        st.plotly_chart(fig_status_donut(df), width="stretch",
                        config={"displayModeBar": False})
    with c2:
        section("Evolución mensual", "servicios por mes y estatus")
        st.plotly_chart(fig_trend(df), width="stretch",
                        config={"displayModeBar": False})

    c3, c4 = st.columns([1, 1])
    with c3:
        section("Participación por nodo")
        st.plotly_chart(fig_participation(df, "NODO"), width="stretch",
                        config={"displayModeBar": False})
    with c4:
        section("Mezcla de estatus por nodo", "% dentro de cada nodo")
        st.plotly_chart(fig_status_by_dim(df, "NODO"), width="stretch",
                        config={"displayModeBar": False})

    section("Participación por país", "Nodo › País — tamaño = servicios")
    st.plotly_chart(fig_treemap(df), width="stretch",
                    config={"displayModeBar": False})

    section(f"Top {top_n} cuentas", "por volumen de servicios (respeta filtros)")
    st.plotly_chart(fig_participation(df, "CUENTA", top=top_n),
                    width="stretch", config={"displayModeBar": False})

    if show_coord and "AGENTE" in df.columns:
        section(f"Top {top_n} coordinadores de cabina",
                "por servicios gestionados · nombre visible, código en tooltip")
        st.plotly_chart(fig_coordinador(df, top=top_n), width="stretch",
                        config={"displayModeBar": False})
        st.caption('Atribución: quien gestionó el servicio. Sin nombre mapeado se '
                   'muestra por código; sin código → "(Sin asignar)".')

    with st.expander("Ver tabla de detalle (agregado filtrado)"):
        tbl = (df.groupby(["NODO", "SOA", "CUENTA", "ESTATUS"])["SERVICIOS"]
                 .sum().reset_index().sort_values("SERVICIOS", ascending=False))
        st.dataframe(tbl, width="stretch", hide_index=True, key=f"tbl_{key}")
        st.download_button("Descargar CSV", tbl.to_csv(index=False).encode("utf-8"),
                           "servicios_filtrado.csv", "text/csv", key=f"dl_{key}")


# --------------------------------------------------------------------------- #
# CSS
# --------------------------------------------------------------------------- #
CSS = """
<style>
.stApp { background: radial-gradient(1200px 600px at 80% -10%, #2a1650 0%, #140a24 55%); }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 2.2rem; max-width: 1300px; }
section[data-testid="stSidebar"] { background: #1b0f30; border-right: 1px solid #2f1f4d; }

.app-title { font-size: 30px; font-weight: 800; color: #f4eefb; letter-spacing: -.02em; margin: 0; }
.app-title .dot { color: #c084fc; }
.app-sub { color: #b9a9d6; font-size: 14px; margin: 2px 0 0; }

.persp { background: #241640; border: 1px solid #3a2a5c; border-left: 3px solid #c084fc;
         border-radius: 10px; padding: 9px 14px; color: #c9bce3; font-size: 13px; margin: 6px 0 16px; }

.kpi { position: relative; background: #241640; border: 1px solid #3a2a5c; border-radius: 14px;
       padding: 16px 16px 14px; overflow: hidden; }
.kpi-bar { position: absolute; top: 0; left: 0; width: 100%; height: 3px; }
.kpi-val { font-size: 26px; font-weight: 800; color: #f4eefb; letter-spacing: -.02em; line-height: 1.1; }
.kpi-lbl { font-size: 12px; color: #8b7aa8; margin-top: 4px; text-transform: uppercase; letter-spacing: .04em; }

.sec { display: flex; align-items: baseline; gap: 10px; margin: 8px 0 2px; }
.sec-ttl { font-size: 15px; font-weight: 700; color: #ede4fb; }
.sec-sub { font-size: 12px; color: #8b7aa8; }

div[data-testid="stExpander"] { border: 1px solid #3a2a5c; border-radius: 12px; background: #1f1338; }
</style>
"""


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    st.set_page_config(page_title="Servicios · Addiuva", page_icon="🟣",
                       layout="wide", initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)

    # Datos (dos archivos: apertura + gestión-con-coordinador)
    base = Path(__file__).parent
    p_ap, p_ge = base / DATA_FILE_APERTURA, base / DATA_FILE_GESTION
    missing = [f for f, p in [(DATA_FILE_APERTURA, p_ap), (DATA_FILE_GESTION, p_ge)]
               if not p.exists()]
    if missing:
        st.warning("Faltan archivos junto a app.py: " + ", ".join(missing) + ". Súbelos:")
        up_ap = st.file_uploader(f"Apertura — {DATA_FILE_APERTURA}", type=["xlsx"], key="up_ap")
        up_ge = st.file_uploader(f"Gestión — {DATA_FILE_GESTION}", type=["xlsx"], key="up_ge")
        if not (up_ap and up_ge):
            st.stop()
        perspectives = load_data(up_ap, up_ge)
    else:
        perspectives = load_data(str(p_ap), str(p_ge))
    dims = dimension_maps(perspectives)

    # Header
    st.markdown("<div class='app-title'>Servicios <span class='dot'>·</span> Addiuva</div>"
                "<div class='app-sub'>Participación por estatus, nodo, país, cuenta y coordinador · Ene 2025 – Abr 2026</div>",
                unsafe_allow_html=True)
    st.write("")

    # ---------------- Sidebar (filtros compartidos) ---------------- #
    with st.sidebar:
        st.markdown("### Filtros")
        meses = dims["meses"]
        date_range = st.select_slider(
            "Periodo", options=meses, value=(meses[0], meses[-1]),
            format_func=mes_label)

        sel_nodos = st.multiselect("Nodo", dims["nodos"], help="Vacío = todos")

        paises_av = sorted({p for n in (sel_nodos or dims["nodos"])
                            for p in dims["nodo_paises"].get(n, [])})
        sel_paises = st.multiselect("País", paises_av, help="Vacío = todos")

        cuentas_av = sorted({c for p in (sel_paises or paises_av)
                             for c in dims["pais_cuentas"].get(p, [])})
        sel_cuentas = st.multiselect("Cuenta", cuentas_av, help="Vacío = todas")

        sel_estatus = st.multiselect("Estatus", list(STATUS_ORDER), help="Vacío = todos")

        # Gestión pre-filtrada → alimenta las opciones de coordinador (en cascada)
        g_pre = apply_filters(perspectives["Gestión"], date_range,
                              sel_nodos, sel_paises, sel_cuentas, sel_estatus)
        coord_opts = (g_pre.groupby("AGENTE")["SERVICIOS"].sum()
                      .sort_values(ascending=False).index.tolist())
        sel_coord = st.multiselect("Coordinador de cabina", coord_opts,
                                   help="Solo afecta la pestaña Gestión · vacío = todos")

        top_n = st.slider("Top N (cuentas y coordinadores)", 5, 30, 15)

        st.caption("Cuentas de prueba (IKATECH / PRUEBA / NO APERTURAR) excluidas. "
                   "El coordinador solo aplica a Gestión.")

    apertura_df = apply_filters(perspectives["Apertura"], date_range,
                                sel_nodos, sel_paises, sel_cuentas, sel_estatus)
    gestion_df = g_pre[g_pre["AGENTE"].isin(sel_coord)] if sel_coord else g_pre

    # ---------------- Tabs (perspectivas) ---------------- #
    tab_ap, tab_ge = st.tabs(["📂  Apertura", "🛠️  Gestión"])

    with tab_ap:
        render_perspective(apertura_df, "fecha de apertura",
                           "cuándo se aperturó el servicio", top_n, key="ap")

    with tab_ge:
        render_perspective(gestion_df, "fecha de gestión",
                           "cuándo se gestionó/atendió el servicio", top_n,
                           key="ge", show_coord=True)


if __name__ == "__main__":
    main()
