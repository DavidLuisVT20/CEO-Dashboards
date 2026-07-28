"""
04_explore_accounts.py
----------------------
Exploracion de cuentas con movimiento por pais (anio 2024, cerrado).

Para cada pais genera output/exploracion/<pais>_2024.md con:
  1. Top 30 cuentas de GASTO (codigo 5/6/7) por |suma balance|.
  2. Top 30 cuentas de INGRESO (codigo 4) por |suma balance|.
  3. Busqueda tematica por nombre_cuenta (siniestralidad, impuestos,
     comisiones, depreciacion/amortizacion).
  4. Sumario por serie (primer digito del codigo_cuenta).

Y un consolidado output/exploracion/RESUMEN_CRUZADO.md con una tabla
terminos-tematicos x paises.

Uso:
    python 04_explore_accounts.py
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds

HERE = Path(__file__).resolve().parent
DATASET_PATH = HERE / "data" / "raw" / "apuntes_contables_particionado"
OUT_DIR = HERE / "output" / "exploracion"
ANIO = 2024

# Terminos de busqueda tematica (ya normalizados: minuscula, sin acento)
TEMAS: dict[str, list[str]] = {
    "Siniestralidad": ["siniestr", "asistencia", "servicio medico", "servicio direct",
                        "costo direct", "prestacion", "reembolso"],
    "Impuestos": ["impuesto", "isr", "iva", "tax", "tributario", "fiscal"],
    "Comisiones": ["comision", "broker", "agente"],
    "Depreciacion/Amortizacion": ["depreciaci", "amortizaci"],
}

SERIE_LABELS = {
    "1": "1 Activos",
    "2": "2 Pasivos",
    "3": "3 Patrimonio",
    "4": "4 Ingresos",
    "5": "5 Costos",
    "6": "6 Gastos",
    "7": "7 Gastos",
    "8": "8 Off-balance",
    "9": "9 Otros",
}


# --------------------------------------------------------------- helpers ----

def _strip_accents(text: str) -> str:
    if not isinstance(text, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _norm(text: str) -> str:
    return _strip_accents(str(text)).lower().strip()


def _fmt_money(v) -> str:
    if pd.isna(v):
        return "_NaN_"
    return f"{v:,.0f}".replace(",", ".")


def _safe_filename(pais: str) -> str:
    return _strip_accents(pais).replace(" ", "_").replace("/", "_")


def _md_table(df: pd.DataFrame, cols: list[str], aligns: dict[str, str] | None = None) -> list[str]:
    aligns = aligns or {}
    lines = []
    header = "| " + " | ".join(cols) + " |"
    sep_cells = []
    for c in cols:
        a = aligns.get(c, "left")
        sep_cells.append("---:" if a == "right" else "---")
    sep = "|" + "|".join(sep_cells) + "|"
    lines.append(header)
    lines.append(sep)
    for _, row in df.iterrows():
        cells = [str(row[c]) for c in cols]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


# ------------------------------------------------------- agregaciones ----

def aggregate_accounts(dfp: pd.DataFrame) -> pd.DataFrame:
    """Agrupa por cuenta y devuelve metricas por cuenta para un pais-anio."""
    g = dfp.groupby(["codigo_cuenta", "nombre_cuenta", "tipo_cuenta"], dropna=False)
    agg = g.agg(
        suma_balance=("balance", "sum"),
        n_filas=("balance", "size"),
        n_meses=("mes", "nunique"),
    ).reset_index()
    agg["abs_balance"] = agg["suma_balance"].abs()
    return agg


def top_n_by_prefix(agg: pd.DataFrame, prefixes: tuple[str, ...], n: int = 30) -> pd.DataFrame:
    mask = agg["codigo_cuenta"].astype(str).str.startswith(prefixes)
    sub = agg.loc[mask].sort_values("abs_balance", ascending=False).head(n).copy()
    sub["suma_balance"] = sub["suma_balance"].map(_fmt_money)
    return sub[["codigo_cuenta", "nombre_cuenta", "tipo_cuenta",
               "suma_balance", "n_filas", "n_meses"]]


def thematic_search(agg: pd.DataFrame, terms: list[str]) -> pd.DataFrame:
    norm_names = agg["nombre_cuenta"].map(_norm)
    mask = pd.Series(False, index=agg.index)
    for t in terms:
        mask = mask | norm_names.str.contains(_norm(t), regex=False, na=False)
    sub = agg.loc[mask].sort_values("abs_balance", ascending=False).copy()
    return sub


def serie_summary(agg: pd.DataFrame) -> pd.DataFrame:
    tmp = agg.copy()
    tmp["serie"] = tmp["codigo_cuenta"].astype(str).str[0]
    g = tmp.groupby("serie").agg(
        suma_balance=("suma_balance", "sum"),
        n_cuentas=("codigo_cuenta", "nunique"),
    ).reset_index()
    g["serie_label"] = g["serie"].map(lambda s: SERIE_LABELS.get(s, f"{s} ?"))
    g = g.sort_values("serie")
    return g


# ----------------------------------------------------- reporte por pais ----

def build_country_report(pais: str, dfp: pd.DataFrame) -> tuple[str, dict]:
    """Devuelve (markdown, resumen_tematico) para un pais."""
    agg = aggregate_accounts(dfp)

    out: list[str] = []
    out.append(f"# Exploracion de cuentas — {pais} {ANIO}\n")
    out.append(f"**Filas (movimientos) en {ANIO}:** {len(dfp):,}  ")
    out.append(f"**Cuentas distintas con movimiento:** {agg['codigo_cuenta'].nunique():,}  ")
    divisas = sorted(dfp["divisa"].dropna().unique().tolist()) if "divisa" in dfp.columns else []
    out.append(f"**Divisa(s):** {', '.join(divisas)}  \n")

    # 1. Gastos
    out.append("\n## 1. Top 30 cuentas de GASTO (codigo 5/6/7) por |saldo|\n")
    gastos = top_n_by_prefix(agg, ("5", "6", "7"), 30)
    if gastos.empty:
        out.append("_Sin cuentas de gasto con movimiento._\n")
    else:
        out += _md_table(gastos,
                         ["codigo_cuenta", "nombre_cuenta", "tipo_cuenta",
                          "suma_balance", "n_filas", "n_meses"],
                         {"suma_balance": "right", "n_filas": "right", "n_meses": "right"})
    out.append("")

    # 2. Ingresos
    out.append("\n## 2. Top 30 cuentas de INGRESO (codigo 4) por |saldo|\n")
    ingresos = top_n_by_prefix(agg, ("4",), 30)
    if ingresos.empty:
        out.append("_Sin cuentas de ingreso con movimiento._\n")
    else:
        out += _md_table(ingresos,
                         ["codigo_cuenta", "nombre_cuenta", "tipo_cuenta",
                          "suma_balance", "n_filas", "n_meses"],
                         {"suma_balance": "right", "n_filas": "right", "n_meses": "right"})
    out.append("")

    # 3. Busqueda tematica
    out.append("\n## 3. Busqueda tematica por nombre de cuenta\n")
    resumen_tema: dict[str, dict] = {}
    for tema, terms in TEMAS.items():
        hits = thematic_search(agg, terms)
        total_bal = hits["suma_balance"].sum() if not hits.empty else 0.0
        resumen_tema[tema] = {"n_cuentas": int(hits["codigo_cuenta"].nunique()),
                              "suma_balance": float(total_bal)}
        out.append(f"\n### {tema}  (terminos: {', '.join(terms)})\n")
        if hits.empty:
            out.append("_Sin coincidencias._\n")
            continue
        disp = hits.copy()
        disp["suma_balance"] = disp["suma_balance"].map(_fmt_money)
        out += _md_table(disp,
                         ["codigo_cuenta", "nombre_cuenta", "tipo_cuenta",
                          "suma_balance", "n_filas", "n_meses"],
                         {"suma_balance": "right", "n_filas": "right", "n_meses": "right"})
        out.append("")

    # 4. Sumario por serie
    out.append("\n## 4. Sumario por serie de codigo (primer digito)\n")
    serie = serie_summary(agg)
    serie_disp = serie[["serie_label", "n_cuentas", "suma_balance"]].copy()
    serie_disp = serie_disp.rename(columns={"serie_label": "serie"})
    serie_disp["suma_balance"] = serie_disp["suma_balance"].map(_fmt_money)
    out += _md_table(serie_disp,
                     ["serie", "n_cuentas", "suma_balance"],
                     {"n_cuentas": "right", "suma_balance": "right"})
    out.append("")

    return "\n".join(out), resumen_tema


# ----------------------------------------------------------------- main ----

def main() -> None:
    if not DATASET_PATH.exists():
        print(f"[ERROR] No existe {DATASET_PATH}. Corre 01_fetch_parquet.py.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Leyendo dataset Hive desde {DATASET_PATH}")
    dataset = ds.dataset(str(DATASET_PATH), partitioning="hive")
    df = dataset.to_table().to_pandas()
    if "account_type" in df.columns and "tipo_cuenta" not in df.columns:
        df = df.rename(columns={"account_type": "tipo_cuenta"})
    print(f"[INFO] Filas totales: {len(df):,}")

    df24 = df[df["anio"] == ANIO].copy()
    print(f"[INFO] Filas {ANIO}: {len(df24):,}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    paises = sorted(df24["pais"].dropna().unique().tolist())
    print(f"[INFO] Paises en {ANIO}: {paises}")

    resumen_cruzado: dict[str, dict[str, dict]] = {}
    for pais in paises:
        dfp = df24[df24["pais"] == pais]
        md, resumen_tema = build_country_report(pais, dfp)
        fpath = OUT_DIR / f"{_safe_filename(pais)}_{ANIO}.md"
        fpath.write_text(md, encoding="utf-8")
        resumen_cruzado[pais] = resumen_tema
        print(f"[OK]   {fpath.name}  ({len(dfp):,} filas)")

    # ------------------------------------------- RESUMEN_CRUZADO.md ----
    lines: list[str] = []
    lines.append(f"# Resumen cruzado — terminos tematicos x pais ({ANIO})\n")
    lines.append("Cada celda: **# cuentas encontradas** / **suma de balance** (moneda local).\n")
    lines.append("> La suma esta en la moneda local de cada pais — no es comparable entre columnas.\n")

    header = "| Tema | " + " | ".join(paises) + " |"
    sep = "|---|" + "|".join(["---"] * len(paises)) + "|"
    lines.append(header)
    lines.append(sep)
    for tema in TEMAS:
        cells = []
        for pais in paises:
            info = resumen_cruzado[pais][tema]
            if info["n_cuentas"] == 0:
                cells.append("— / —")
            else:
                cells.append(f"{info['n_cuentas']} / {_fmt_money(info['suma_balance'])}")
        lines.append(f"| {tema} | " + " | ".join(cells) + " |")
    lines.append("")

    # Tabla auxiliar: serie dominante por pais
    lines.append("\n## Shape contable por pais — suma de balance por serie\n")
    lines.append("> Util para ver que paises tienen ingresos en serie 4, costos en 5, etc.\n")
    serie_keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
    h2 = "| Pais | " + " | ".join(SERIE_LABELS.get(k, k) for k in serie_keys) + " |"
    s2 = "|---|" + "|".join(["---:"] * len(serie_keys)) + "|"
    lines.append(h2)
    lines.append(s2)
    for pais in paises:
        dfp = df24[df24["pais"] == pais].copy()
        dfp["serie"] = dfp["codigo_cuenta"].astype(str).str[0]
        by_serie = dfp.groupby("serie")["balance"].sum()
        cells = [_fmt_money(by_serie.get(k, 0.0)) for k in serie_keys]
        lines.append(f"| {pais} | " + " | ".join(cells) + " |")
    lines.append("")

    resumen_path = OUT_DIR / "RESUMEN_CRUZADO.md"
    resumen_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK]   RESUMEN_CRUZADO.md")
    print()
    print(f"[DONE] {len(paises)} paises procesados en {OUT_DIR}")


if __name__ == "__main__":
    main()
