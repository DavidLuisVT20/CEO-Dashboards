"""
10_kpis_territorial.py
----------------------
TAREA 1 + 2: clasifica razones sociales (territorial vs multipais v0.1) y corre
el motor sobre el rollup TERRITORIAL (excluyendo Voccare e Ikatech), ML, 2022+.

Regla v0.1 (PROVISIONAL, pendiente de confirmar con devs de Odoo):
  MULTIPAIS si company_name contiene (lower, sin acentos) 'voccare' o 'ikatech';
  TERRITORIAL en caso contrario.

Salidas:
  output/clasificacion_razones_v0_1.csv
  output/kpis_territorial_ml.csv  (niveles: pais, sociedad)
"""
from __future__ import annotations

import os
import sys
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engine.formula_engine import FormulaEngine  # noqa: E402

GLOB = str(HERE / "data" / "raw" / "complete_apuntes_contables_bi_mts" / "anio=*" / "*.parquet").replace("\\", "/")
FORMULAS_PNL = HERE / "formulas" / "P&L-2026.json"
OUT_CLASIF = HERE / "output" / "clasificacion_razones_v0_1.csv"
OUT_KPIS = HERE / "output" / "kpis_territorial_ml.csv"


def _norm(s) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def es_multipais(nombre: str) -> bool:
    n = _norm(nombre)
    return ("voccare" in n) or ("ikatech" in n)


def _con():
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='6GB'"); con.execute("PRAGMA threads=4")
    con.execute("PRAGMA disable_progress_bar")
    os.makedirs(HERE / "data" / "duckdb_tmp", exist_ok=True)
    con.execute(f"PRAGMA temp_directory='{str(HERE / 'data' / 'duckdb_tmp').replace(chr(92), '/')}'")
    return con


def run_level(engine, df, groupby, nivel, pais_map):
    results, errors = engine.evaluate(df, groupby_cols=groupby)
    if errors:
        for k, v in errors.items():
            print(f"   ERROR {k}: {v}")
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
                           pais=pais_map.get(int(cid), "?"))
            else:
                pais, anio, mes = idx
                rec.update(pais=pais, company_id="", anio=int(anio), mes=int(mes))
            rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    con = _con()
    rel = f"read_parquet('{GLOB}', hive_partitioning=1)"

    # ---- TAREA 1: clasificacion ----
    soc = con.execute(f"""
        SELECT company_id, any_value(company_name) company_name, any_value(pais) pais,
               count(*) filas
        FROM {rel} GROUP BY company_id ORDER BY company_id
    """).fetch_df()
    soc["clase"] = soc["company_name"].map(lambda n: "MULTIPAIS" if es_multipais(n) else "TERRITORIAL")
    OUT_CLASIF.parent.mkdir(parents=True, exist_ok=True)
    soc[["company_id", "company_name", "pais", "clase"]].to_csv(OUT_CLASIF, index=False, encoding="utf-8")
    print(f"[OK] {OUT_CLASIF}")
    print(f"[INFO] Razones sociales: {len(soc)} total | "
          f"TERRITORIAL={int((soc['clase']=='TERRITORIAL').sum())} | "
          f"MULTIPAIS={int((soc['clase']=='MULTIPAIS').sum())}")
    print("\n[INFO] MULTIPAIS detectadas (v0.1):")
    for _, r in soc[soc["clase"] == "MULTIPAIS"].iterrows():
        print(f"   co{r['company_id']:<4} {r['company_name']}  (pais col={r['pais']})")
    print("\n[INFO] Conteo por pais y clase:")
    print(soc.groupby(["pais", "clase"]).size().unstack(fill_value=0).to_string())

    multipais_ids = soc.loc[soc["clase"] == "MULTIPAIS", "company_id"].tolist()
    excl = ",".join(str(int(c)) for c in multipais_ids) or "-1"

    # ---- TAREA 2: motor territorial ----
    print(f"\n[INFO] Pre-agregando TERRITORIAL (excluye company_id in [{excl}]), anio>=2022...")
    # FIX fan-out analitico: el parquet repite cada linea contable (aml_id) una vez
    # por combinacion de distribucion/etiqueta, con el balance COMPLETO en cada copia.
    # Sumar crudo infla toda cifra por el factor de fan-out (var. por sociedad, 7x-65x).
    # Cada aml_id tiene UNA sola analitica y UN solo balance (verificado: 0/139k con >1),
    # asi que colapsar a una fila por aml_id (DISTINCT) es exacto y preserva la analitica
    # que usan AGA25 y los centros de costo. No se prorratea: no hay split que repartir.
    df = con.execute(f"""
        SELECT pais, company_id, anio, mes, codigo_cuenta, id_cuenta_analitica,
               account_type AS tipo_cuenta, sum(balance) AS balance
        FROM (
            SELECT DISTINCT aml_id, pais, company_id, anio, mes, codigo_cuenta,
                   id_cuenta_analitica, account_type, balance
            FROM {rel}
            WHERE anio >= 2022 AND company_id NOT IN ({excl})
        )
        GROUP BY pais, company_id, anio, mes, codigo_cuenta, id_cuenta_analitica, account_type
    """).fetch_df()
    print(f"[INFO] Tabla compacta territorial: {len(df):,} filas")
    pais_map = (df[["company_id", "pais"]].drop_duplicates()
                .set_index("company_id")["pais"].to_dict())

    engine = FormulaEngine(FORMULAS_PNL)
    out = pd.concat([
        run_level(engine, df, ["pais", "anio", "mes"], "pais", None),
        run_level(engine, df, ["company_id", "anio", "mes"], "sociedad", pais_map),
    ], ignore_index=True)
    out = out[["nivel", "pais", "company_id", "anio", "mes", "aga_code", "concepto", "valor"]]
    out.to_csv(OUT_KPIS, index=False, encoding="utf-8")
    print(f"[OK] {OUT_KPIS} -> {len(out):,} filas")

    # ---- SANITY Mexico territorial 2024 ----
    pais_lvl = out[out["nivel"] == "pais"]
    mx = pais_lvl[(pais_lvl["pais"] == "Mexico") & (pais_lvl["anio"] == 2024)]
    ing = mx[mx["aga_code"] == "AGA4"]["valor"].sum()
    ebitda = mx[mx["aga_code"] == "AGA29"]["valor"].sum()
    print("\n=== SANITY Mexico territorial 2024 (suma 12 meses, MXN) ===")
    print(f"   AGA4  Total Ingresos: {ing:,.0f} MXN  (esperado ~2.390M)")
    print(f"   AGA29 EBITDA        : {ebitda:,.0f} MXN")

    # ---- BANDERA: ingresos negativos territoriales ----
    a4 = pais_lvl[pais_lvl["aga_code"] == "AGA4"]
    neg = a4[a4["valor"] < 0].sort_values("valor")
    print(f"\n=== BANDERA: pais-mes con Total Ingresos NEGATIVO (territorial): {len(neg)} ===")
    for _, r in neg.iterrows():
        print(f"   {r['pais']:<18} {int(r['anio'])}-{int(r['mes']):02d}  {r['valor']:,.0f}")


if __name__ == "__main__":
    main()
