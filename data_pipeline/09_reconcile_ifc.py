"""
09_reconcile_ifc.py
-------------------
TAREA 3 + 4: reconcilia los KPIs del motor (kpis_odoo_ml.csv, nivel pais, ML)
contra el IFC consolidado (consolidado_ifc_3.9.1.xlsx, Divisa=ML, 2022+),
anclando en los margenes. Tambien deriva el TC implicito del IFC y lo compara
contra tasa_cambio del parquet.

Salidas:
  output/RECONCILIACION_IFC.md
  output/reconciliacion_detalle.csv
"""
from __future__ import annotations

import os
import sys
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent
KPIS = HERE / "output" / "kpis_odoo_ml.csv"
IFC = Path(r"C:\Users\Luis David\Documents\GitHub\Addiuva\consolidado_ifc_3.9.1.xlsx")
FORMULAS_PNL = HERE / "formulas" / "P&L-2026.json"
GLOB = str(HERE / "data" / "raw" / "complete_apuntes_contables_bi_mts" / "anio=*" / "*.parquet").replace("\\", "/")
OUT_MD = HERE / "output" / "RECONCILIACION_IFC.md"
OUT_CSV = HERE / "output" / "reconciliacion_detalle.csv"

ANCLAS = ["AGA4", "AGA8", "AGA18", "AGA24", "AGA29"]

# Mapa curado AGA -> concepto IFC (normalizado upper sin acentos). Cubre anclas
# y rubros clave donde el nombre AGA y el del IFC no empatan por string exacto.
AGA_TO_IFC = {
    "AGA4":  "TOTAL INGRESOS",
    "AGA1":  "INGRESOS NETOS",
    "AGA2":  "OTROS INGRESOS",
    "AGA5":  "COSTOS DIRECTOS DE OPERACION",
    "AGA8":  "MARGEN BRUTO OPERATIVO",
    "AGA10": "COSTO DIRECTO DE COMERCIALIZACION",
    "AGA11": "COMISIONES BROKERS",
    "AGA18": "MARGEN NETO OPERATIVO & VENTAS",
    "AGA24": "MARGEN NETO DE CONTRIBUCION",
    "AGA25": "GASTOS GENERALES DE ADMON Y VENTAS",
    "AGA29": "EBITDA",
    "AGA32": "EBITDA CON EXTRAORDINARIOS",
    "AGA44": "DEPRECIACION",
    "AGA45": "AMORTIZACION",
    "AGA46": "EBIT",
    "AGA56": "RESULTADO NETO",
}

# IFC pais -> parquet pais (normalizado). Sub-entidades del IFC que el parquet
# agrupa dentro de un pais se mapean para sumar y comparar manzana-manzana.
IFC_PAIS_TO_PARQUET = {
    "ESTADOS UNIDOS": "United States",
    "PUERTO RICO": "United States",
    "FLORIDA": "United States",
    "ESPANA": "Spain",
    "REPUBLICA DOMINICANA": "Dominican Republic",
    "BOGOTA": "Colombia",
    # 1:1 (mismo nombre, distinto casing/acentos) se resuelven por identidad abajo
    # Ikatech / Voccare: cross-entidad, sin mapeo limpio -> se reportan aparte.
}
PARQUET_PAISES = ["Argentina", "Bolivia", "Chile", "Colombia", "Costa Rica",
                  "Dominican Republic", "Ecuador", "Egypt", "El Salvador",
                  "Guatemala", "Honduras", "Mexico", "Nicaragua", "Paraguay",
                  "Peru", "Spain", "United States", "Uruguay"]


def _norm(s) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split()).strip()


def map_ifc_pais(p: str) -> str | None:
    n = _norm(p)
    if n in IFC_PAIS_TO_PARQUET:
        return IFC_PAIS_TO_PARQUET[n]
    # identidad: buscar un parquet pais cuyo _norm coincida
    for pp in PARQUET_PAISES:
        if _norm(pp) == n:
            return pp
    return None  # Ikatech, Voccare, etc.


def _fm(v) -> str:
    if v is None or pd.isna(v):
        return "_NaN_"
    return f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fp(v) -> str:
    if v is None or pd.isna(v):
        return "_NaN_"
    return f"{v*100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    # ---- KPIs Odoo (nivel pais, ML) ----
    kpis = pd.read_csv(KPIS)
    odoo = kpis[(kpis["nivel"] == "pais") & (kpis["anio"] >= 2022)].copy()
    odoo = odoo[["pais", "anio", "mes", "aga_code", "valor"]].rename(columns={"valor": "valor_odoo"})

    # ---- IFC consolidado ----
    print("[INFO] Leyendo IFC consolidado...")
    ifc = pd.read_excel(IFC, sheet_name=0)
    ifc.columns = [c.strip() for c in ifc.columns]
    ifc["anio"] = pd.to_datetime(ifc["Fecha"], errors="coerce").dt.year
    ifc["mes"] = pd.to_datetime(ifc["Fecha"], errors="coerce").dt.month
    ifc_ml = ifc[(ifc["Divisa"] == "ML") & (ifc["anio"] >= 2022)].copy()
    ifc_ml["concepto_norm"] = ifc_ml["Concepto"].map(_norm)
    ifc_ml["pais_parquet"] = ifc_ml["Pais"].map(map_ifc_pais)

    # concepto IFC -> aga_code (invertir AGA_TO_IFC)
    ifc_to_aga = {}
    for aga, ifc_concepto in AGA_TO_IFC.items():
        ifc_to_aga.setdefault(ifc_concepto, aga)
    ifc_ml["aga_code"] = ifc_ml["concepto_norm"].map(ifc_to_aga)

    # conceptos IFC no mapeados (informativo)
    no_map = (ifc_ml[ifc_ml["aga_code"].isna()]
              .groupby("concepto_norm").size().sort_values(ascending=False))

    # sumar IFC a nivel pais_parquet (suma sub-entidades: PR+FL+EEUU->United States, etc.)
    ifc_match = ifc_ml.dropna(subset=["pais_parquet", "aga_code"]).copy()
    ifc_agg = (ifc_match.groupby(["pais_parquet", "anio", "mes", "aga_code"], as_index=False)["Monto"]
               .sum().rename(columns={"pais_parquet": "pais", "Monto": "monto_ifc"}))

    # ---- Join ----
    rec = odoo.merge(ifc_agg, on=["pais", "anio", "mes", "aga_code"], how="inner")
    rec["diferencia"] = rec["valor_odoo"] - rec["monto_ifc"]
    rec["dif_pct"] = rec.apply(
        lambda r: (r["diferencia"] / r["monto_ifc"]) if r["monto_ifc"] not in (0, None) and pd.notna(r["monto_ifc"]) else pd.NA,
        axis=1)
    rec["concepto"] = rec["aga_code"].map(AGA_TO_IFC)
    rec.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"[OK] {OUT_CSV} -> {len(rec):,} filas reconciliadas")

    # ---- Semaforo por pais (sobre anclas) ----
    def cuadra(row_mask: pd.DataFrame, code: str) -> float:
        sub = row_mask[row_mask["aga_code"] == code]
        if sub.empty:
            return None
        ok = sub["dif_pct"].abs() < 0.01
        return ok.mean()  # fraccion de periodos que cuadran

    paises = sorted(rec["pais"].unique())
    semaforo = []
    for p in paises:
        rp = rec[rec["pais"] == p]
        anc = {}
        for code in ANCLAS:
            sub = rp[rp["aga_code"] == code]
            if sub.empty:
                anc[code] = None
            else:
                anc[code] = float((sub["dif_pct"].abs() < 0.01).mean())
        ing_ok = (anc.get("AGA4") or 0) >= 0.9
        ebitda_ok = (anc.get("AGA29") or 0) >= 0.9
        all_ok = all((anc.get(c) or 0) >= 0.9 for c in ANCLAS)
        if all_ok:
            color = "VERDE"
        elif ing_ok and ebitda_ok:
            color = "AMARILLO"
        else:
            color = "ROJO"
        semaforo.append((p, color, anc))

    # ---- TC: implicito IFC (USD/ML) vs parquet ----
    print("[INFO] Derivando TC implicito IFC y comparando con parquet...")
    ifc_all = ifc[(ifc["anio"] >= 2022)].copy()
    ifc_all["pais_parquet"] = ifc_all["Pais"].map(map_ifc_pais)
    ifc_all["concepto_norm"] = ifc_all["Concepto"].map(_norm)
    piv = ifc_all.pivot_table(index=["pais_parquet", "anio", "mes", "concepto_norm"],
                              columns="Divisa", values="Monto", aggfunc="sum")
    piv = piv.dropna(subset=["ML", "USD"])
    piv = piv[(piv["ML"].abs() > 1) & (piv["USD"].abs() > 1)]
    piv["tc_ifc"] = piv["ML"] / piv["USD"]
    tc_ifc = (piv.reset_index().groupby(["pais_parquet", "anio", "mes"])["tc_ifc"]
              .median().reset_index().rename(columns={"pais_parquet": "pais"}))

    con = duckdb.connect(); con.execute("PRAGMA disable_progress_bar")
    tc_parq = con.execute(f"""
        SELECT pais, anio, mes, avg(tasa_cambio) tc_parq
        FROM read_parquet('{GLOB}', hive_partitioning=1)
        WHERE anio >= 2022 AND tasa_cambio IS NOT NULL
        GROUP BY pais, anio, mes
    """).fetch_df()
    # parquet tasa_cambio: ML->USD (multiplicador) o USD/ML? comparar ambas orientaciones
    tc = tc_ifc.merge(tc_parq, on=["pais", "anio", "mes"], how="inner")
    # tc_ifc = ML/USD. parquet tc: probar 1/tc_parq tambien.
    tc["ratio_directo"] = tc["tc_ifc"] / tc["tc_parq"]
    tc["ratio_inverso"] = tc["tc_ifc"] * tc["tc_parq"]
    tc_pais = tc.groupby("pais").agg(
        tc_ifc_med=("tc_ifc", "median"),
        tc_parq_med=("tc_parq", "median"),
        ratio_directo_med=("ratio_directo", "median"),
        ratio_inverso_med=("ratio_inverso", "median"),
        n=("tc_ifc", "size"),
    ).reset_index()

    # ---- Escribir MD ----
    out = ["# RECONCILIACION IFC vs motor Odoo (moneda local, 2022+)\n"]
    out.append(f"- KPIs Odoo: nivel pais, {len(odoo):,} filas. IFC ML 2022+: {len(ifc_ml):,} filas.")
    out.append(f"- Rubros reconciliados (join exitoso): {len(rec):,} filas.")
    out.append(f"- Umbral 'cuadra': |dif_%| < 1%.\n")

    out.append("\n## A. Semaforo por pais (anclas)\n")
    out.append("Fraccion de periodos (mes) que cuadran por ancla. Semaforo: VERDE=las 5 anclas; "
               "AMARILLO=ingresos+EBITDA ok pero algun margen no; ROJO=ni ingresos ni EBITDA.\n")
    out.append("| pais | sem | AGA4 Ingr | AGA8 MBO | AGA18 MNOV | AGA24 MNC | AGA29 EBITDA |")
    out.append("|---|---|---:|---:|---:|---:|---:|")
    for p, color, anc in semaforo:
        cells = [(_fp(anc[c]) if anc[c] is not None else "—") for c in ANCLAS]
        out.append(f"| {p} | {color} | " + " | ".join(cells) + " |")
    out.append("")

    out.append("\n## B. Detalle de descuadres (|dif_%| >= 1%), top por magnitud\n")
    desq = rec[(rec["dif_pct"].abs() >= 0.01) & rec["dif_pct"].notna()].copy()
    desq["abs_dif"] = desq["diferencia"].abs()
    desq = desq.sort_values("abs_dif", ascending=False)
    out.append(f"Total rubros-periodo descuadrados: {len(desq):,} de {len(rec):,}\n")
    out.append("| pais | anio | mes | aga | concepto | valor_odoo | monto_ifc | diferencia | dif_% |")
    out.append("|---|---|---|---|---|---:|---:|---:|---:|")
    for _, r in desq.head(40).iterrows():
        out.append(f"| {r['pais']} | {r['anio']} | {r['mes']} | {r['aga_code']} | {r['concepto']} | "
                   f"{_fm(r['valor_odoo'])} | {_fm(r['monto_ifc'])} | {_fm(r['diferencia'])} | {_fp(r['dif_pct'])} |")
    out.append("")

    out.append("\n## C. Argentina (co44) y Guatemala (co18) — descuadres conocidos\n")
    for p in ["Argentina", "Guatemala"]:
        rp = desq[desq["pais"] == p]
        out.append(f"\n### {p}: {len(rp)} rubros-periodo descuadrados")
        if not rp.empty:
            out.append("| anio | mes | aga | concepto | valor_odoo | monto_ifc | dif_% |")
            out.append("|---|---|---|---|---:|---:|---:|")
            for _, r in rp.head(15).iterrows():
                out.append(f"| {r['anio']} | {r['mes']} | {r['aga_code']} | {r['concepto']} | "
                           f"{_fm(r['valor_odoo'])} | {_fm(r['monto_ifc'])} | {_fp(r['dif_pct'])} |")
        out.append("")

    out.append("\n## D. Tipos de cambio: IFC implicito (ML/USD) vs parquet (tasa_cambio)\n")
    out.append("ratio_directo = tc_ifc / tc_parq (≈1 si parquet ya es ML/USD); "
               "ratio_inverso = tc_ifc * tc_parq (≈1 si parquet es USD/ML).\n")
    out.append("| pais | tc_ifc (med) | tc_parq (med) | ratio_directo | ratio_inverso | n |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for _, r in tc_pais.iterrows():
        out.append(f"| {r['pais']} | {r['tc_ifc_med']:,.2f} | {r['tc_parq_med']:,.4f} | "
                   f"{r['ratio_directo_med']:,.3f} | {r['ratio_inverso_med']:,.3f} | {int(r['n'])} |")
    out.append("")

    out.append("\n## E. Conceptos del IFC que NO se mapearon a ningun AGA (revisar)\n")
    out.append(f"Total conceptos IFC distintos sin mapeo: {len(no_map)} (se listan top 30 por frecuencia)\n")
    out.append("| concepto_ifc (normalizado) | filas |")
    out.append("|---|---:|")
    for c, n in no_map.head(30).items():
        out.append(f"| {c} | {n} |")
    out.append("")

    OUT_MD.write_text("\n".join(out), encoding="utf-8")
    print(f"[OK] {OUT_MD}")

    # eco consola
    print("\nSemaforo:")
    for p, color, anc in semaforo:
        print(f"  {p:<22} {color}")


if __name__ == "__main__":
    main()
