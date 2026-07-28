"""
15_rubros_por_pais.py
---------------------
Saca 6 rubros del P&L por PAIS y ANIO (moneda local) desde el parquet ACTUALIZADO,
para mandarle a Ikatech y corroborar que tenemos la misma data.

Rubros (concepto <- AGA):
  Total Ingresos               <- AGA4
  Margen Bruto Operativo       <- AGA8
  Margen Neto Operativo & Venta<- AGA18
  Margen Neto de Contribucion  <- AGA24
  EBITDA                       <- AGA29
  Resultado Neto               <- AGA56

Alcance: TODAS las razones sociales (crudo, NO excluye Voccare/Ikatech) — chequeo de
paridad de data por pais. Anios 2019-2026; 2026 solo hasta MAYO (mes<=5). Moneda local.

Salidas:
  output/RUBROS_POR_PAIS.md
  output/rubros_por_pais.csv
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engine.formula_engine import FormulaEngine  # noqa: E402

GLOB = str(HERE / "data" / "raw" / "complete_apuntes_contables_bi_mts" / "anio=*" / "*.parquet").replace("\\", "/")
FORMULAS = HERE / "formulas" / "P&L-2026.json"
OUT_MD = HERE / "output" / "RUBROS_POR_PAIS.md"
OUT_CSV = HERE / "output" / "rubros_por_pais.csv"
OUT_XLSX = HERE / "output" / "rubros_por_pais.xlsx"

ANIOS = list(range(2019, 2027))
RUBROS = [
    ("AGA4", "Total Ingresos", "TOTAL INGRESOS"),
    ("AGA8", "Margen Bruto Operativo", "MARGEN BRUTO OPERATIVO"),
    ("AGA18", "Margen Neto Operativo & Venta", "MARGEN NETO OPERATIVO & VENTAS"),
    ("AGA24", "Margen Neto de Contribución", "MARGEN NETO DE CONTRIBUCION"),
    ("AGA29", "EBITDA", "EBITDA"),
    ("AGA56", "Resultado Neto", "RESULTADO NETO"),
]
DIVISA_ML = {
    "Argentina": "ARS", "Bolivia": "BOB", "Chile": "CLP", "Colombia": "COP", "Costa Rica": "CRC",
    "Dominican Republic": "DOP", "Ecuador": "USD", "Egypt": "EGP", "El Salvador": "USD",
    "Guatemala": "GTQ", "Honduras": "HNL", "Mexico": "MXN", "Nicaragua": "NIO", "Paraguay": "PYG",
    "Peru": "PEN", "Spain": "EUR", "United States": "USD", "Uruguay": "UYU",
    "Panama": "PAB",
}


def _fm(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='6GB'"); con.execute("PRAGMA threads=4")
    con.execute("PRAGMA disable_progress_bar")
    os.makedirs(HERE / "data" / "duckdb_tmp", exist_ok=True)
    con.execute(f"PRAGMA temp_directory='{str(HERE / 'data' / 'duckdb_tmp').replace(chr(92), '/')}'")

    print("[INFO] Pre-agregando por SOCIEDAD (2019-2026, 2026<=mayo)...")
    df = con.execute(f"""
        SELECT pais, company_id, company_name, anio, codigo_cuenta, id_cuenta_analitica,
               account_type AS tipo_cuenta, sum(balance) AS balance
        FROM read_parquet('{GLOB}', hive_partitioning=1)
        WHERE (anio BETWEEN 2019 AND 2025) OR (anio = 2026 AND mes <= 5)
        GROUP BY pais, company_id, company_name, anio, codigo_cuenta, id_cuenta_analitica, account_type
    """).fetch_df()
    print(f"[INFO] Tabla compacta: {len(df):,} filas")

    # co47 Panama viene con pais NULL en el parquet -> etiquetar.
    df["pais"] = df["pais"].fillna("Panama")

    # mapas por sociedad
    dd = df.drop_duplicates("company_id")
    name_map = dict(zip(dd["company_id"], dd["company_name"]))
    pais_map = dict(zip(dd["company_id"], dd["pais"]))

    def es_multipais(nombre) -> bool:
        n = str(nombre).lower()
        return ("voccare" in n) or ("ikatech" in n)

    engine = FormulaEngine(FORMULAS)
    print("[INFO] Evaluando motor por (company_id, anio)...")
    results, errors = engine.evaluate(df, groupby_cols=["company_id", "anio"])
    if errors:
        for k, v in errors.items():
            print(f"   ERROR {k}: {v}")

    # armar tabla larga a nivel SOCIEDAD
    long_rows = []
    for aga, concepto, _ in RUBROS:
        s = results.get(aga)
        if s is None:
            continue
        for (cid, anio), val in s.items():
            cid = int(cid)
            pais = pais_map.get(cid, "?")
            long_rows.append({
                "pais": pais, "sociedad": name_map.get(cid, "?"), "company_id": cid,
                "clase": "MULTIPAIS" if es_multipais(name_map.get(cid)) else "TERRITORIAL",
                "divisa": DIVISA_ML.get(pais, "ML"), "anio": int(anio), "aga_code": aga,
                "rubro": concepto, "valor_ml": (None if pd.isna(val) else round(float(val), 2)),
            })
    long_df = pd.DataFrame(long_rows)
    long_df = long_df[["pais", "sociedad", "company_id", "clase", "divisa",
                       "anio", "aga_code", "rubro", "valor_ml"]]
    long_df = long_df.sort_values(["pais", "sociedad", "aga_code", "anio"])
    long_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    anios_pres = sorted(long_df["anio"].unique())
    # orden estable de sociedades por (pais, sociedad)
    soc_order = long_df[["pais", "sociedad", "company_id", "clase", "divisa"]].drop_duplicates()
    soc_order = soc_order.sort_values(["pais", "sociedad"])

    # ---- Excel: hoja larga + una hoja ancha por rubro (fila = sociedad) ----
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xw:
        long_df.to_excel(xw, sheet_name="Detalle (largo)", index=False)
        for aga, concepto, upper in RUBROS:
            sub = long_df[long_df["aga_code"] == aga]
            wide = sub.pivot_table(index=["pais", "sociedad", "clase", "divisa"],
                                   columns="anio", values="valor_ml", aggfunc="sum").reset_index()
            sheet = concepto[:31].replace("&", "y").replace("/", "-")
            wide.to_excel(xw, sheet_name=sheet, index=False)
    print(f"[OK] {OUT_XLSX}")

    # ---- MD: por rubro, fila = sociedad ----
    out = ["# Rubros del P&L por SOCIEDAD y año — moneda local (paridad vs Ikatech)\n"]
    out.append("> Motor (AGA del diccionario) sobre el parquet ACTUALIZADO. Moneda LOCAL "
               "(`balance`, sin conversión). Granularidad **por RAZÓN SOCIAL** (columna `clase` "
               "marca TERRITORIAL vs MULTIPAIS = Voccare/Ikatech, para que NO se sumen al país). "
               "Años 2019-2026; **2026 solo hasta mayo**.\n")
    out.append("Mapeo rubro → nodo: " + " · ".join(f"{c} = `{a}`" for a, c, _ in RUBROS) + "\n")

    for aga, concepto, upper in RUBROS:
        sub = long_df[long_df["aga_code"] == aga]
        out.append(f"\n## {concepto}  ({upper})\n")
        out.append("| País | Sociedad | Clase | Divisa | " + " | ".join(str(a) for a in anios_pres) + " |")
        out.append("|---|---|---|---|" + "|".join(["---:"] * len(anios_pres)) + "|")
        for _, so in soc_order.iterrows():
            row = [so["pais"], str(so["sociedad"])[:40], so["clase"], so["divisa"]]
            for a in anios_pres:
                cell = sub[(sub["company_id"] == so["company_id"]) & (sub["anio"] == a)]
                row.append(_fm(cell["valor_ml"].iloc[0]) if not cell.empty else "—")
            out.append("| " + " | ".join(row) + " |")
        out.append("")

    OUT_MD.write_text("\n".join(out), encoding="utf-8")
    print(f"[OK] {OUT_MD}")
    print(f"[OK] {OUT_CSV} ({len(long_df):,} filas)")
    print(f"[INFO] Sociedades: {long_df['company_id'].nunique()} "
          f"(TERRITORIAL={long_df[long_df['clase']=='TERRITORIAL']['company_id'].nunique()}, "
          f"MULTIPAIS={long_df[long_df['clase']=='MULTIPAIS']['company_id'].nunique()}) | Anios: {anios_pres}")


if __name__ == "__main__":
    main()
