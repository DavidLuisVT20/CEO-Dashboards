"""
08_build_finanzas_payload.py
----------------------------
Construye el payload del tablero de Finanzas (modo VALIDACION LOCAL).

- ML: reutiliza output/kpis_territorial_ml.csv (pais + sociedad, ya sin Voc/Ika).
- USD: re-corre el motor convirtiendo CADA LINEA por su tasa_cambio ANTES de agregar
       (balance_usd = balance * tasa_cambio). Mas fiel que convertir el agregado.
       Lineas con tasa_cambio NULL no se pueden convertir -> se excluyen del USD.
- 3 niveles: sociedad (company_id), pais (suma territoriales), consolidado (USD).
- Badges por (pais, mes): reconciliado (4 paises) y preliminar (ultimos 2 meses con data).

Salida: output/finanzas_payload.json   (GITIGNORED — data real, repo publico)
"""
from __future__ import annotations

import datetime as dt
import json
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
KPIS_ML = HERE / "output" / "kpis_territorial_ml.csv"
CLASIF = HERE / "output" / "clasificacion_razones_v0_1.csv"
FORMULAS = HERE / "formulas" / "P&L-2026.json"
OUT = HERE / "output" / "finanzas_payload.json"

# KPIs que muestra el tablero (9, en orden de tarjeta)
KPI_ORDER = ["AGA29", "AGA4", "AGA5", "AGA8", "AGA18", "AGA24", "AGA25", "AGA46", "AGA56"]
KPI_TITLES = {
    "AGA29": "EBITDA", "AGA4": "Total Ingresos", "AGA5": "Siniestralidad",
    "AGA8": "Margen Bruto Operativo", "AGA18": "Margen Neto Op. & Venta",
    "AGA24": "Margen Neto de Contribución", "AGA25": "Gastos Generales (GAV)",
    "AGA46": "EBIT", "AGA56": "Resultado Neto",
}

RECONCILED = {"El Salvador", "Nicaragua", "United States", "Ecuador"}

# parquet pais -> codigo del slicer (COUNTRIES de finanzas.jsx)
PAIS_CODE = {
    "Argentina": "ar", "Bolivia": "bo", "Chile": "cl", "Colombia": "co",
    "Costa Rica": "cr", "Dominican Republic": "do", "Ecuador": "ec", "Egypt": "eg",
    "El Salvador": "sv", "Guatemala": "gt", "Honduras": "hn", "Mexico": "mx",
    "Nicaragua": "ni", "Paraguay": "py", "Peru": "pe", "Spain": "es",
    "United States": "us", "Uruguay": "uy",
}
PAIS_LABEL = {
    "Argentina": "Argentina", "Bolivia": "Bolivia", "Chile": "Chile", "Colombia": "Colombia",
    "Costa Rica": "Costa Rica", "Dominican Republic": "República Dominicana", "Ecuador": "Ecuador",
    "Egypt": "Egipto", "El Salvador": "El Salvador", "Guatemala": "Guatemala", "Honduras": "Honduras",
    "Mexico": "México", "Nicaragua": "Nicaragua", "Paraguay": "Paraguay", "Peru": "Perú",
    "Spain": "España", "United States": "Estados Unidos", "Uruguay": "Uruguay",
}
# divisa ML por pais (de la columna divisa del parquet)
DIVISA_ML = {
    "Argentina": "ARS", "Bolivia": "BOB", "Chile": "CLP", "Colombia": "COP", "Costa Rica": "CRC",
    "Dominican Republic": "DOP", "Ecuador": "USD", "Egypt": "EGP", "El Salvador": "USD",
    "Guatemala": "GTQ", "Honduras": "HNL", "Mexico": "MXN", "Nicaragua": "NIO", "Paraguay": "PYG",
    "Peru": "PEN", "Spain": "EUR", "United States": "USD", "Uruguay": "UYU",
}


def _con():
    c = duckdb.connect()
    c.execute("PRAGMA memory_limit='6GB'"); c.execute("PRAGMA threads=4")
    c.execute("PRAGMA disable_progress_bar")
    os.makedirs(HERE / "data" / "duckdb_tmp", exist_ok=True)
    c.execute(f"PRAGMA temp_directory='{str(HERE / 'data' / 'duckdb_tmp').replace(chr(92), '/')}'")
    return c


def run_engine_level(engine, df, groupby, pais_map):
    results, _ = engine.evaluate(df, groupby_cols=groupby)
    rows = []
    for code in KPI_ORDER:
        s = results.get(code)
        if s is None:
            continue
        for idx, val in s.items():
            if groupby == ["company_id", "anio", "mes"]:
                cid, anio, mes = idx
                rows.append((int(cid), pais_map.get(int(cid), "?"), int(anio), int(mes), code,
                             float(val) if pd.notna(val) else None))
            else:
                pais, anio, mes = idx
                rows.append((None, pais, int(anio), int(mes), code,
                             float(val) if pd.notna(val) else None))
    return pd.DataFrame(rows, columns=["company_id", "pais", "anio", "mes", "aga", "valor"])


def usd_kpis(con, engine):
    """Pre-agrega convirtiendo cada linea a USD (balance*tasa_cambio) y corre el motor."""
    # balance_usd: si hay tasa_cambio, balance*tasa; si la divisa YA es USD (paises
    # dolarizados con tasa_cambio NULL: Ecuador, El Salvador, EEUU), balance tal cual;
    # si no es USD y no hay tasa, NULL (no convertible -> excluida del USD por sum()).
    df = con.execute(f"""
        SELECT pais, company_id, anio, mes, codigo_cuenta, id_cuenta_analitica,
               account_type AS tipo_cuenta,
               sum(CASE WHEN tasa_cambio IS NOT NULL THEN balance * tasa_cambio
                        WHEN divisa = 'USD' THEN balance
                        ELSE NULL END) AS balance
        FROM read_parquet('{GLOB}', hive_partitioning=1)
        WHERE anio >= 2022
          AND lower(company_name) NOT LIKE '%voccare%' AND lower(company_name) NOT LIKE '%ikatech%'
        GROUP BY pais, company_id, anio, mes, codigo_cuenta, id_cuenta_analitica, account_type
    """).fetch_df()
    pais_map = (df[["company_id", "pais"]].drop_duplicates().set_index("company_id")["pais"].to_dict())
    soc = run_engine_level(engine, df, ["company_id", "anio", "mes"], pais_map)
    pa = run_engine_level(engine, df, ["pais", "anio", "mes"], None)
    return soc, pa


def main() -> None:
    con = _con()
    engine = FormulaEngine(FORMULAS)

    # ---- ML (reusa CSV) ----
    ml = pd.read_csv(KPIS_ML)
    ml = ml[ml["aga_code"].isin(KPI_ORDER) & (ml["anio"] >= 2022)]
    ml_soc = ml[ml["nivel"] == "sociedad"][["company_id", "pais", "anio", "mes", "aga_code", "valor"]].rename(columns={"aga_code": "aga"})
    ml_pa = ml[ml["nivel"] == "pais"][["pais", "anio", "mes", "aga_code", "valor"]].rename(columns={"aga_code": "aga"})

    # ---- USD (re-corre motor convertido a nivel linea) ----
    print("[INFO] Calculando KPIs en USD (conversion por linea)...")
    usd_soc, usd_pa = usd_kpis(con, engine)

    # ---- clasificacion (sociedades territoriales) ----
    clasif = pd.read_csv(CLASIF)
    terr = clasif[clasif["clase"] == "TERRITORIAL"]

    # ---- helpers ----
    def pivot_records(df_long, nivel, moneda):
        """De formato largo (aga,valor) a registros con dict de kpis por slice."""
        key = ["company_id", "pais", "anio", "mes"] if nivel == "sociedad" else ["pais", "anio", "mes"]
        recs = []
        for keyvals, g in df_long.groupby(key, dropna=False):
            kvals = dict(zip(key, keyvals if isinstance(keyvals, tuple) else (keyvals,)))
            kpis = {r["aga"]: (None if pd.isna(r["valor"]) else round(float(r["valor"]), 2))
                    for _, r in g.iterrows()}
            pais = kvals["pais"]
            rec = {
                "nivel": nivel, "pais": PAIS_LABEL.get(pais, pais), "pais_code": PAIS_CODE.get(pais),
                "company_id": (int(kvals["company_id"]) if nivel == "sociedad" and pd.notna(kvals.get("company_id")) else None),
                "anio": int(kvals["anio"]), "mes": int(kvals["mes"]),
                "moneda": moneda, "divisa": ("USD" if moneda == "USD" else DIVISA_ML.get(pais, "ML")),
                "reconciled": pais in RECONCILED, "kpis": kpis,
            }
            recs.append(rec)
        return recs

    records = []
    records += pivot_records(ml_pa, "pais", "ML")
    records += pivot_records(usd_pa, "pais", "USD")
    records += pivot_records(ml_soc, "sociedad", "ML")
    records += pivot_records(usd_soc, "sociedad", "USD")

    # ---- consolidado USD (suma de paises por anio/mes) ----
    cons = (usd_pa.groupby(["anio", "mes", "aga"], as_index=False)["valor"].sum())
    for (anio, mes), g in cons.groupby(["anio", "mes"]):
        kpis = {r["aga"]: round(float(r["valor"]), 2) for _, r in g.iterrows()}
        records.append({"nivel": "consolidado", "pais": "Consolidado", "pais_code": None,
                        "company_id": None, "anio": int(anio), "mes": int(mes),
                        "moneda": "USD", "divisa": "USD", "reconciled": False, "kpis": kpis})

    # ---- marca preliminar: ultimos 2 (anio,mes) con data, por scope ----
    for r in records:
        r["preliminar"] = False

    def mark_prelim(filter_fn, group_key_fn):
        groups: dict = {}
        for r in records:
            if not filter_fn(r):
                continue
            groups.setdefault(group_key_fn(r), set()).add((r["anio"], r["mes"]))
        prelim_by_group = {gk: set(sorted(pers)[-2:]) for gk, pers in groups.items()}
        for r in records:
            if filter_fn(r) and (r["anio"], r["mes"]) in prelim_by_group.get(group_key_fn(r), set()):
                r["preliminar"] = True

    # pais: por (pais_code) — independiente de la moneda (ML/USD comparten periodos)
    mark_prelim(lambda r: r["nivel"] == "pais", lambda r: r["pais_code"])
    # sociedad: por (company_id)
    mark_prelim(lambda r: r["nivel"] == "sociedad", lambda r: r["company_id"])
    # consolidado: global
    mark_prelim(lambda r: r["nivel"] == "consolidado", lambda r: "ALL")

    # ---- paises meta (con sus sociedades territoriales) ----
    paises_meta = []
    for pais in sorted(PAIS_CODE):
        socs = terr[terr["pais"] == pais][["company_id", "company_name"]]
        paises_meta.append({
            "code": PAIS_CODE[pais], "label": PAIS_LABEL[pais], "parquet": pais,
            "divisa_ml": DIVISA_ML.get(pais, "ML"), "reconciled": pais in RECONCILED,
            "sociedades": [{"id": int(r["company_id"]), "name": r["company_name"]}
                           for _, r in socs.iterrows()],
        })

    payload = {
        "meta": {
            "generado": dt.date.today().isoformat(),
            "modo": "VALIDACION LOCAL — datos reales Odoo (no produccion)",
            "regla_territorial": "v0.1 (provisional): excluye razones sociales con 'voccare'/'ikatech'",
            "reconciled_countries": sorted(PAIS_LABEL[p] for p in RECONCILED),
            "kpi_order": KPI_ORDER, "kpi_titles": KPI_TITLES,
            "nota_usd": "USD = sum(balance * tasa_cambio) a nivel linea; lineas sin tasa_cambio excluidas del USD.",
            "nota_preliminar": "Ultimos 2 meses con datos por pais = preliminares (devengos sin cerrar).",
        },
        "paises": paises_meta,
        "records": records,
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"[OK] {OUT} ({size_kb:,.0f} KB, {len(records):,} registros)")
    # sanity
    mx_usd = [r for r in records if r["nivel"] == "pais" and r["pais"] == "México"
              and r["moneda"] == "USD" and r["anio"] == 2025 and r["mes"] == 12]
    if mx_usd:
        print(f"[SANITY] Mexico pais USD 2025-12: EBITDA={mx_usd[0]['kpis'].get('AGA29'):,.0f} "
              f"Ingresos={mx_usd[0]['kpis'].get('AGA4'):,.0f} USD")
    print(f"[INFO] paises con badge validado: {sorted(PAIS_LABEL[p] for p in RECONCILED)}")


if __name__ == "__main__":
    main()
