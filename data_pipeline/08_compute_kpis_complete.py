"""
08_compute_kpis_complete.py
---------------------------
TAREA 2: corre el motor de formulas P&L sobre el dataset complete (38.8M filas),
anio >= 2022, en MONEDA LOCAL, en 3 niveles de agregacion.

Estrategia de rendimiento: pre-agregar en DuckDB a la granularidad minima que el
motor necesita (pais, company_id, anio, mes, codigo_cuenta, id_cuenta_analitica,
tipo_cuenta) -> sum(balance). Como sum es asociativa y los dominios solo filtran
por codigo/analitica/tipo, el resultado es identico al de correr sobre las 38.8M
filas, pero sobre una tabla mucho mas chica.

Salida: output/kpis_odoo_ml.csv
  columnas: nivel, pais, company_id, anio, mes, aga_code, concepto, valor
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

DATA_DIR = HERE / "data" / "raw" / "complete_apuntes_contables_bi_mts"
GLOB = str(DATA_DIR / "anio=*" / "*.parquet").replace("\\", "/")
FORMULAS_PNL = HERE / "formulas" / "P&L-2026.json"
OUT = HERE / "output" / "kpis_odoo_ml.csv"


def preaggregate() -> pd.DataFrame:
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='6GB'")
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA disable_progress_bar")
    os.makedirs(HERE / "data" / "duckdb_tmp", exist_ok=True)
    con.execute(f"PRAGMA temp_directory='{str(HERE / 'data' / 'duckdb_tmp').replace(chr(92), '/')}'")
    rel = f"read_parquet('{GLOB}', hive_partitioning=1)"
    print("[INFO] Pre-agregando en DuckDB (anio>=2022)...")
    df = con.execute(f"""
        SELECT pais, company_id, anio, mes,
               codigo_cuenta,
               id_cuenta_analitica,
               account_type AS tipo_cuenta,
               sum(balance) AS balance
        FROM {rel}
        WHERE anio >= 2022
        GROUP BY pais, company_id, anio, mes, codigo_cuenta, id_cuenta_analitica, account_type
    """).fetch_df()
    print(f"[INFO] Tabla compacta: {len(df):,} filas (de 38.8M transaccionales)")
    return df


def run_level(engine: FormulaEngine, df: pd.DataFrame, groupby: list[str],
              nivel: str, pais_map: dict | None) -> pd.DataFrame:
    print(f"[INFO] Nivel '{nivel}' groupby={groupby} ...")
    results, errors = engine.evaluate(df, groupby_cols=groupby)
    if errors:
        for k, v in errors.items():
            print(f"        ERROR {k}: {v}")
    rows = []
    for code in engine.topo_order:
        s = results.get(code)
        if s is None or s.empty:
            continue
        concepto = engine.get_concepto(code)
        for idx, val in s.items():
            rec = {"nivel": nivel, "aga_code": code, "concepto": concepto,
                   "valor": float(val) if pd.notna(val) else None}
            if groupby == ["company_id", "anio", "mes"]:
                cid, anio, mes = idx
                rec.update(company_id=int(cid), anio=int(anio), mes=int(mes),
                           pais=pais_map.get(int(cid), "?") if pais_map else "?")
            elif groupby == ["pais", "anio", "mes"]:
                pais, anio, mes = idx
                rec.update(pais=pais, company_id="", anio=int(anio), mes=int(mes))
            else:  # ["anio","mes"]
                anio, mes = idx
                rec.update(pais="GRUPO", company_id="", anio=int(anio), mes=int(mes))
            rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    if not DATA_DIR.exists():
        sys.exit(f"No existe {DATA_DIR}")
    df = preaggregate()
    pais_map = (df[["company_id", "pais"]].drop_duplicates()
                .set_index("company_id")["pais"].to_dict())

    engine = FormulaEngine(FORMULAS_PNL)
    print(f"[INFO] Motor: {len(engine.dag)} nodos evaluables.")

    parts = [
        run_level(engine, df, ["company_id", "anio", "mes"], "sociedad", pais_map),
        run_level(engine, df, ["pais", "anio", "mes"], "pais", None),
        run_level(engine, df, ["anio", "mes"], "grupo", None),
    ]
    out = pd.concat(parts, ignore_index=True)
    out = out[["nivel", "pais", "company_id", "anio", "mes", "aga_code", "concepto", "valor"]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"\n[OK] {OUT} -> {len(out):,} filas")
    print("[INFO] Conteo por nivel:")
    print(out["nivel"].value_counts().to_string())


if __name__ == "__main__":
    main()
