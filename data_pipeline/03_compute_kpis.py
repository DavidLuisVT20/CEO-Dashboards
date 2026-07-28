"""
03_compute_kpis.py
------------------
Pipeline que lee el dataset particionado de apuntes contables, corre el motor
de formulas (engine/formula_engine.py) y produce:

  - output/kpis_long.csv: tabla larga con cada KPI por (pais, anio, mes).
  - output/kpis_summary.md: resumen legible de KPIs clave para 2024.

Uso:
    python 03_compute_kpis.py

Sin parametros: lee data/raw/apuntes_contables_particionado/ tal cual la
sesion anterior la bajo. Si no esta, corre antes 01_fetch_parquet.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds

# Permitir import relativo al script
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine.formula_engine import FormulaEngine  # noqa: E402

DATASET_PATH = HERE / "data" / "raw" / "apuntes_contables_particionado"
FORMULAS_PNL = HERE / "formulas" / "P&L-2026.json"
OUTPUT_DIR = HERE / "output"
KPIS_LONG = OUTPUT_DIR / "kpis_long.csv"
KPIS_SUMMARY = OUTPUT_DIR / "kpis_summary.md"

# KPIs clave para el resumen (Mexico 2024 y consolidado)
KPIS_CLAVE = [
    ("AGA4",  "Total Ingresos"),
    ("AGA5",  "Costo directo de operacion (Siniestralidad)"),
    ("AGA8",  "Margen Bruto Operativo"),
    ("AGA25", "Gastos Generales de Admon y Ventas (GAV)"),
    ("AGA29", "EBITDA"),
    ("AGA56", "Resultado Neto"),
    ("AGA54", "Impuestos"),
    ("ETR",   "Effective Tax Rate (AGA54 / (AGA56 + AGA54))"),
]


# --------------------------------------------------------------------- Carga --

def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"[ERROR] No existe el dataset particionado en {path}", file=sys.stderr)
        print("        Corre primero 01_fetch_parquet.py.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Leyendo dataset Hive desde {path}")
    dataset = ds.dataset(str(path), partitioning="hive")
    df = dataset.to_table().to_pandas()
    # account_type viene en el parquet con ese nombre; el motor usa la
    # convencion 'tipo_cuenta' del brief permanente. Renombrar si toca.
    if "account_type" in df.columns and "tipo_cuenta" not in df.columns:
        df = df.rename(columns={"account_type": "tipo_cuenta"})
    print(f"[INFO] Filas: {len(df):,}  Columnas: {df.shape[1]}")
    return df


# ---------------------------------------------------------------- Evaluacion --

def run_engine(
    df: pd.DataFrame,
    engine: FormulaEngine,
    groupby_cols: list[str],
) -> tuple[dict[str, pd.Series], dict[str, str]]:
    print(f"[INFO] Evaluando motor con groupby={groupby_cols}")
    results, errors = engine.evaluate(df, groupby_cols=groupby_cols)
    print(f"[INFO]   {len(results)} nodos calculados, {len(errors)} con error.")
    if errors:
        for k, v in errors.items():
            print(f"        ERROR  {k}: {v}")
    return results, errors


def compute_etr(results: dict[str, pd.Series]) -> pd.Series | None:
    """ETR = AGA54 / (AGA56 + AGA54), NaN ante denominador 0."""
    if "AGA54" not in results or "AGA56" not in results:
        return None
    tax = results["AGA54"]
    net = results["AGA56"]
    denom = net + tax
    etr = tax / denom
    return etr.replace([float("inf"), float("-inf")], pd.NA)


# ----------------------------------------------------------- Salida en long --

def build_long_df(
    engine: FormulaEngine,
    results_pam: dict[str, pd.Series],   # por (pais, anio, mes)
    results_pa: dict[str, pd.Series],    # por (pais, anio)
    results_a: dict[str, pd.Series],     # por (anio)
    etr_pam: pd.Series | None,
    etr_pa: pd.Series | None,
    etr_a: pd.Series | None,
) -> pd.DataFrame:
    rows: list[dict] = []

    def _push_series(code: str, concepto: str, nivel, s: pd.Series, level: str) -> None:
        if s is None or s.empty:
            return
        for idx, val in s.items():
            if level == "pam":
                pais, anio, mes = idx
                rows.append({
                    "aga_code": code, "concepto": concepto, "nivel": nivel,
                    "pais": pais, "anio": int(anio), "mes": int(mes),
                    "valor": float(val) if pd.notna(val) else None,
                })
            elif level == "pa":
                pais, anio = idx
                rows.append({
                    "aga_code": code, "concepto": concepto, "nivel": nivel,
                    "pais": pais, "anio": int(anio), "mes": "TOTAL_ANUAL",
                    "valor": float(val) if pd.notna(val) else None,
                })
            elif level == "a":
                anio = idx if not isinstance(idx, tuple) else idx[0]
                rows.append({
                    "aga_code": code, "concepto": concepto, "nivel": nivel,
                    "pais": "CONSOLIDADO", "anio": int(anio), "mes": "TOTAL_ANUAL",
                    "valor": float(val) if pd.notna(val) else None,
                })

    # Nodos del arbol de formulas
    for code in engine.topo_order:
        concepto = engine.get_concepto(code)
        nivel = engine.get_nivel(code)
        _push_series(code, concepto, nivel, results_pam.get(code), "pam")
        _push_series(code, concepto, nivel, results_pa.get(code), "pa")
        _push_series(code, concepto, nivel, results_a.get(code), "a")

    # ETR (metrica derivada, fuera del JSON)
    _push_series("ETR", "Effective Tax Rate", 3, etr_pam, "pam")
    _push_series("ETR", "Effective Tax Rate", 3, etr_pa, "pa")
    _push_series("ETR", "Effective Tax Rate", 3, etr_a, "a")

    return pd.DataFrame(rows, columns=["aga_code", "concepto", "nivel",
                                       "pais", "anio", "mes", "valor"])


# --------------------------------------------------------- Resumen markdown --

def _fmt_money(v) -> str:
    if pd.isna(v):
        return "_NaN_"
    return f"{v:,.0f}".replace(",", ".")


def _fmt_pct(v) -> str:
    if pd.isna(v):
        return "_NaN_"
    return f"{v * 100:.2f}%"


def build_summary_md(
    results_pa: dict[str, pd.Series],
    results_a: dict[str, pd.Series],
    etr_pa: pd.Series | None,
    etr_a: pd.Series | None,
    df: pd.DataFrame,
) -> str:
    out: list[str] = []
    out.append("# Resumen de KPIs — Motor de Formulas P&L\n")
    out.append(f"**Filas totales en dataset:** {len(df):,}  \n")
    out.append(f"**Anios cubiertos:** {sorted(df['anio'].unique().tolist())}  \n")
    out.append(f"**Paises:** {sorted(df['pais'].dropna().unique().tolist())}  \n")
    out.append("\n---\n")

    out.append("## KPIs clave 2024 por pais (TOTAL ANUAL, moneda local)\n")
    out.append("> Los KPIs estan en la moneda local de cada pais — NO consolidados a USD.\n")

    paises = sorted(df.loc[df["anio"] == 2024, "pais"].dropna().unique().tolist())
    header = "| KPI | Concepto | " + " | ".join(paises) + " |"
    sep = "|---|---|" + "|".join(["---:"] * len(paises)) + "|"
    out.append(header)
    out.append(sep)

    for code, label in KPIS_CLAVE:
        cells = []
        if code == "ETR":
            src = etr_pa
        else:
            src = results_pa.get(code)
        for p in paises:
            v = None
            try:
                v = src.loc[(p, 2024)] if src is not None else None
            except KeyError:
                v = None
            cells.append(_fmt_pct(v) if code == "ETR" else _fmt_money(v))
        out.append(f"| {code} | {label} | " + " | ".join(cells) + " |")

    out.append("\n## KPIs clave 2024 — consolidado (suma de todos los paises, EN MONEDA LOCAL)\n")
    out.append("> Cuidado: la suma de paises en moneda local NO es economicamente significativa "
               "(cada pais usa su propia divisa). Esta seccion es de diagnostico, no de reporte.\n")

    out.append("| KPI | Concepto | Valor 2024 (no comparable) |")
    out.append("|---|---|---:|")
    for code, label in KPIS_CLAVE:
        if code == "ETR":
            src = etr_a
        else:
            src = results_a.get(code)
        v = None
        try:
            v = src.loc[2024] if src is not None else None
        except KeyError:
            v = None
        cell = _fmt_pct(v) if code == "ETR" else _fmt_money(v)
        out.append(f"| {code} | {label} | {cell} |")

    out.append("\n## Tendencia por anio — consolidado (moneda local, no comparable entre paises)\n")
    out.append("| KPI | " + " | ".join(str(y) for y in sorted(df['anio'].unique())) + " |")
    out.append("|---|" + "|".join(["---:"] * len(sorted(df['anio'].unique()))) + "|")
    for code, label in KPIS_CLAVE:
        if code == "ETR":
            src = etr_a
        else:
            src = results_a.get(code)
        cells = []
        for y in sorted(df["anio"].unique()):
            v = None
            try:
                v = src.loc[y] if src is not None else None
            except KeyError:
                v = None
            cells.append(_fmt_pct(v) if code == "ETR" else _fmt_money(v))
        out.append(f"| {code} | " + " | ".join(cells) + " |")

    out.append("\n---\n")
    out.append("## PENDIENTES\n")
    out.append("- **Eficiencia Fiscal**: pendiente tabla de tasas estatutarias por pais/anio. "
               "Hoy reportamos ETR (effective tax rate) calculada del propio P&L.")
    out.append("- **Balance General**: pendiente que Ikatech agregue `equity_unaffected` a "
               "`tipo_cuenta`. Sin este `account_type`, A74 (Resultado del Ejercicio "
               "Financiero/Acumulado) no se calcula y el Balance no cuadra.")
    out.append("- **Consolidacion USD**: pendiente cobertura completa de `tasa_cambio` (la columna "
               "esta presente pero con NaNs y sin auditar). Hoy todos los KPIs estan en moneda "
               "local y NO son sumables entre paises.")
    out.append("- **Historico pre-2022**: pendiente que Ikatech suba las particiones "
               "`anio=2015` a `anio=2021`. Actualmente solo hay 2022-2026.")
    out.append("")

    return "\n".join(out)


# -------------------------------------------------------------------- main --

def main() -> None:
    df = load_dataset(DATASET_PATH)

    print(f"[INFO] Paises: {sorted(df['pais'].dropna().unique().tolist())}")
    print(f"[INFO] Rango fechas: {df['fecha'].min()} -> {df['fecha'].max()}")
    print(f"[INFO] Anios: {sorted(df['anio'].unique().tolist())}")
    print()

    engine = FormulaEngine(FORMULAS_PNL)
    print(f"[INFO] Motor cargado: {len(engine.dag)} nodos evaluables del P&L.")
    print()

    results_pam, err_pam = run_engine(df, engine, ["pais", "anio", "mes"])
    results_pa, err_pa = run_engine(df, engine, ["pais", "anio"])
    results_a, err_a = run_engine(df, engine, ["anio"])

    etr_pam = compute_etr(results_pam)
    etr_pa = compute_etr(results_pa)
    etr_a = compute_etr(results_a)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[INFO] Construyendo CSV long...")
    long_df = build_long_df(engine, results_pam, results_pa, results_a,
                            etr_pam, etr_pa, etr_a)
    long_df.to_csv(KPIS_LONG, index=False, encoding="utf-8")
    print(f"[OK]   kpis_long.csv -> {len(long_df):,} filas")

    print("[INFO] Construyendo resumen .md...")
    md = build_summary_md(results_pa, results_a, etr_pa, etr_a, df)
    KPIS_SUMMARY.write_text(md, encoding="utf-8")
    print(f"[OK]   kpis_summary.md -> {len(md):,} bytes")
    print()

    # ----------------------------------------- TAREA 4: sanity & warnings --
    print("=" * 70)
    print("VALIDACION DE SANIDAD — Mexico 2024 (slice mas conocido)")
    print("=" * 70)
    mx_2024 = {}
    for code, label in KPIS_CLAVE:
        if code == "ETR":
            src = etr_pa
        else:
            src = results_pa.get(code)
        try:
            v = src.loc[("Mexico", 2024)] if src is not None else float("nan")
        except KeyError:
            v = float("nan")
        mx_2024[code] = v
        if code == "ETR":
            print(f"  {code:<6} {label:<55} {_fmt_pct(v)}")
        else:
            print(f"  {code:<6} {label:<55} {_fmt_money(v)} MXN")

    print()
    print("Heuristicas de cordura:")
    warnings: list[str] = []
    if pd.notna(mx_2024["AGA4"]) and mx_2024["AGA4"] <= 0:
        warnings.append("AGA4 (Total Ingresos) Mexico 2024 NO ES POSITIVO. Revisar signo de Ingresos Brutos.")
    if pd.notna(mx_2024["AGA5"]) and mx_2024["AGA5"] < 0:
        warnings.append("AGA5 (Costo) Mexico 2024 NEGATIVO. Costos deberian ser >= 0.")
    if (pd.notna(mx_2024["AGA29"]) and pd.notna(mx_2024["AGA4"]) and mx_2024["AGA4"] != 0):
        margen_ebitda = mx_2024["AGA29"] / mx_2024["AGA4"]
        if abs(margen_ebitda) > 1.0:
            warnings.append(
                f"Margen EBITDA Mexico 2024 = {margen_ebitda * 100:.1f}% — fuera de rango plausible (-100% .. 100%)."
            )
    if (pd.notna(mx_2024["ETR"]) and (mx_2024["ETR"] < -0.5 or mx_2024["ETR"] > 1.0)):
        warnings.append(f"ETR Mexico 2024 = {mx_2024['ETR'] * 100:.2f}% — fuera de rango plausible.")

    if warnings:
        print("  WARNINGS:")
        for w in warnings:
            print(f"    !  {w}")
    else:
        print("  Sin warnings — los numeros estan en rangos plausibles a primera vista.")
    print()

    # Errores que aparecieron en cualquier nivel
    all_errors = {}
    for label_lvl, errs in [("pam", err_pam), ("pa", err_pa), ("a", err_a)]:
        for k, v in errs.items():
            all_errors.setdefault(k, []).append(f"[{label_lvl}] {v}")
    if all_errors:
        print("=" * 70)
        print("ERRORES POR NODO (consolidado de los 3 niveles)")
        print("=" * 70)
        for k, lst in all_errors.items():
            print(f"  {k}:")
            for line in lst:
                print(f"     {line}")
    else:
        print("[OK] Ningun nodo dio error en ninguno de los 3 niveles de agregacion.")


if __name__ == "__main__":
    main()
