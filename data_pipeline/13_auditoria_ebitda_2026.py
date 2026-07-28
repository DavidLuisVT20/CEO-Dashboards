"""
13_auditoria_ebitda_2026.py
---------------------------
Auditoria de EBITDA de los 19 paises territoriales, ACOTADA a 2026 meses 1-4.
Odoo (AGA29, ML, territorial) vs IFC (Concepto="EBITDA", ML). Unico criterio: EBITDA.

Salidas:
  output/AUDITORIA_EBITDA_2026.md
  output/auditoria_ebitda_2026_detalle.csv
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
KPIS = HERE / "output" / "kpis_territorial_ml.csv"
IFC = Path(r"C:\Users\Luis David\Documents\GitHub\Addiuva\consolidado_ifc_3.9.1.xlsx")
OUT_MD = HERE / "output" / "AUDITORIA_EBITDA_2026.md"
OUT_CSV = HERE / "output" / "auditoria_ebitda_2026_detalle.csv"

TOL = 0.05
ANIO = 2026
MESES = [1, 2, 3, 4]

PAISES_19 = ["Argentina", "Bolivia", "Chile", "Colombia", "Costa Rica",
             "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Guatemala",
             "Honduras", "Mexico", "Nicaragua", "Paraguay", "Peru", "Spain",
             "United States", "Uruguay", "Panama"]
CLUSTER = ["Honduras", "Peru", "Uruguay", "Costa Rica", "Paraguay"]
MEJORES = ["Ecuador", "Nicaragua", "El Salvador"]

IFC_MULTIPAIS = {"IKATECH", "VOCCARE"}
IFC_PAIS_TO_PARQUET = {
    "ESTADOS UNIDOS": "United States", "PUERTO RICO": "United States", "FLORIDA": "United States",
    "ESPANA": "Spain", "REPUBLICA DOMINICANA": "Dominican Republic", "BOGOTA": "Colombia",
}


def _norm(s) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split()).strip()


def map_ifc_pais(p: str):
    n = _norm(p)
    if any(m in n for m in IFC_MULTIPAIS):
        return None
    if n in IFC_PAIS_TO_PARQUET:
        return IFC_PAIS_TO_PARQUET[n]
    for pp in PAISES_19:
        if _norm(pp) == n:
            return pp
    return None


def _fm(v):
    if v is None or pd.isna(v):
        return "_NaN_"
    return f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fp(v, dec=1):
    if v is None or pd.isna(v):
        return "—"
    return f"{v*100:,.{dec}f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    k = pd.read_csv(KPIS)
    pl = k[(k["nivel"] == "pais") & (k["anio"] == ANIO) & (k["mes"].isin(MESES))]
    eb_odoo = pl[pl["aga_code"] == "AGA29"][["pais", "mes", "valor"]].rename(columns={"valor": "ebitda_odoo"})
    ing = pl[pl["aga_code"] == "AGA4"][["pais", "mes", "valor"]].rename(columns={"valor": "ingresos_odoo"})

    ifc = pd.read_excel(IFC, sheet_name=0)
    ifc.columns = [c.strip() for c in ifc.columns]
    ifc["anio"] = pd.to_datetime(ifc["Fecha"], errors="coerce").dt.year
    ifc["mes"] = pd.to_datetime(ifc["Fecha"], errors="coerce").dt.month
    ml = ifc[(ifc["Divisa"] == "ML") & (ifc["anio"] == ANIO) & (ifc["mes"].isin(MESES))].copy()
    ml["concepto_norm"] = ml["Concepto"].map(_norm)
    ml["pais_parquet"] = ml["Pais"].map(map_ifc_pais)
    eb_ifc = ml[(ml["concepto_norm"] == "EBITDA") & ml["pais_parquet"].notna()]
    eb_ifc = (eb_ifc.groupby(["pais_parquet", "mes"], as_index=False)["Monto"]
              .sum().rename(columns={"pais_parquet": "pais", "Monto": "ebitda_ifc"}))

    # universo: todos los pais x mes 1-4
    universo = pd.MultiIndex.from_product([PAISES_19, MESES], names=["pais", "mes"]).to_frame(index=False)
    df = (universo.merge(eb_odoo, on=["pais", "mes"], how="left")
                  .merge(ing, on=["pais", "mes"], how="left")
                  .merge(eb_ifc, on=["pais", "mes"], how="left"))

    def clasifica(r):
        if pd.isna(r["ebitda_odoo"]):
            return "SIN ODOO"
        if pd.notna(r["ingresos_odoo"]) and r["ingresos_odoo"] < 0:
            return "MOTOR SOSPECHOSO"
        if pd.isna(r["ebitda_ifc"]) or r["ebitda_ifc"] == 0:
            return "SIN IFC"
        dif = abs(r["ebitda_odoo"] - r["ebitda_ifc"]) / abs(r["ebitda_ifc"])
        return "CUADRA" if dif <= TOL else "NO CUADRA"

    df["diferencia"] = df["ebitda_odoo"] - df["ebitda_ifc"]
    df["dif_abs_pct"] = df.apply(lambda r: (abs(r["diferencia"]) / abs(r["ebitda_ifc"]))
                                 if pd.notna(r["ebitda_ifc"]) and r["ebitda_ifc"] != 0 else pd.NA, axis=1)
    df["clasificacion"] = df.apply(clasifica, axis=1)
    df.sort_values(["pais", "mes"]).to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"[OK] {OUT_CSV} -> {len(df):,} filas")

    # marca por mes
    def marca(r):
        c = r["clasificacion"]
        return {"CUADRA": "OK", "NO CUADRA": "X", "SIN IFC": "-",
                "MOTOR SOSPECHOSO": "!", "SIN ODOO": "."}[c]

    # scorecard por pais
    rows = []
    for p in PAISES_19:
        d = df[df["pais"] == p].set_index("mes")
        marks = []
        for m in MESES:
            marks.append(marca(d.loc[m]) if m in d.index else ".")
        aud = d[d["clasificacion"].isin(["CUADRA", "NO CUADRA"])]
        n_aud = len(aud)
        # acumulado sobre meses con IFC presente y no sospechoso
        sum_o = aud["ebitda_odoo"].sum() if n_aud else None
        sum_i = aud["ebitda_ifc"].sum() if n_aud else None
        dif_acum = ((sum_o - sum_i) / sum_i) if (n_aud and sum_i not in (0, None) and pd.notna(sum_i)) else None
        n_cuadra = int((aud["dif_abs_pct"] <= TOL).sum()) if n_aud else 0
        factor = (aud["ebitda_odoo"] / aud["ebitda_ifc"]).median() if n_aud else None
        n_neg = int((d["clasificacion"] == "MOTOR SOSPECHOSO").sum())
        n_sinifc = int((d["clasificacion"] == "SIN IFC").sum())
        rows.append({"pais": p, "marks": " ".join(marks), "n_aud": n_aud, "n_cuadra": n_cuadra,
                     "sum_o": sum_o, "sum_i": sum_i, "dif_acum": dif_acum, "factor": factor,
                     "n_neg": n_neg, "n_sinifc": n_sinifc})
    sc = pd.DataFrame(rows)

    # orden: primero los que cuadran acumulado, luego resto
    def keyorder(r):
        if r["n_aud"] == 0:
            return (3, r["pais"])
        if r["dif_acum"] is not None and abs(r["dif_acum"]) < 0.05:
            return (0, r["pais"])
        if r["dif_acum"] is not None and abs(r["dif_acum"]) < 0.10:
            return (1, r["pais"])
        return (2, r["pais"])
    sc["k"] = sc.apply(keyorder, axis=1)
    sc = sc.sort_values("k")

    out = [f"# AUDITORIA DE EBITDA — 19 paises territoriales — SOLO 2026 ene-abr\n"]
    out.append("Criterio UNICO: EBITDA (AGA29 ↔ 'EBITDA' del IFC, ML). Periodo: anio=2026, meses 1-4.")
    out.append("Marcas mes (m1 m2 m3 m4): OK=cuadra<5% · X=no cuadra · -=SIN IFC · !=motor sospechoso (ing. neg) · .=sin data Odoo.")
    out.append(f"Tolerancia cuadre: {int(TOL*100)}%.\n")

    out.append("| pais | audit (de 4) | EBITDA Odoo (ene-abr) | EBITDA IFC (ene-abr) | dif % acum | m1 m2 m3 m4 | factor O/I |")
    out.append("|---|---:|---:|---:|---:|:--:|---:|")
    for _, r in sc.iterrows():
        fac = f"{r['factor']:,.1f}" if r["factor"] is not None and pd.notna(r["factor"]) else "—"
        out.append(f"| {r['pais']} | {r['n_aud']} | {_fm(r['sum_o'])} | {_fm(r['sum_i'])} | "
                   f"{_fp(r['dif_acum'])} | {r['marks']} | {fac} |")
    out.append("")

    # A) conteo
    aud_paises = sc[sc["n_aud"] > 0]
    n_5 = int((aud_paises["dif_acum"].abs() < 0.05).sum())
    n_10 = int((aud_paises["dif_acum"].abs() < 0.10).sum())
    n_sinifc_pais = int((sc["n_aud"] == 0).sum())
    n_conneg = int((sc["n_neg"] > 0).sum())
    out.append("\n## A. Conteo resumen (de 19, sobre 2026 ene-abr)\n")
    out.append(f"- Auditables (algun mes con Odoo+IFC): **{len(aud_paises)}**")
    out.append(f"- Cuadran dif acumulada **< 5%: {n_5}**")
    out.append(f"- Cuadran dif acumulada **< 10%: {n_10}**")
    out.append(f"- Sin meses auditables (SIN IFC o sin Odoo): **{n_sinifc_pais}**")
    out.append(f"- Con algun mes de ingreso negativo (motor sospechoso): **{n_conneg}**\n")

    # B) cluster factor
    out.append("\n## B. Cluster de factor ~10-20x (Honduras/Peru/Uruguay/Costa Rica/Paraguay): ¿persiste en 2026?\n")
    out.append("| pais | factor 2026 (mediano) | dif % acum 2026 | meses audit |")
    out.append("|---|---:|---:|---:|")
    for p in CLUSTER:
        r = sc[sc["pais"] == p].iloc[0]
        fac = f"{r['factor']:,.1f}" if r["factor"] is not None and pd.notna(r["factor"]) else "—"
        out.append(f"| {p} | {fac} | {_fp(r['dif_acum'])} | {int(r['n_aud'])} |")
    out.append("")

    # C) foco mejores
    out.append("\n## C. Foco 2026 en los 3 que iban mejor (Ecuador, Nicaragua, El Salvador)\n")
    for p in MEJORES:
        d = df[df["pais"] == p].sort_values("mes")
        out.append(f"\n### {p}")
        out.append("| mes | EBITDA Odoo | EBITDA IFC | dif_abs_% | clase |")
        out.append("|---|---:|---:|---:|---|")
        for _, r in d.iterrows():
            out.append(f"| {int(r['mes'])} | {_fm(r['ebitda_odoo'])} | {_fm(r['ebitda_ifc'])} | "
                       f"{_fp(r['dif_abs_pct'])} | {r['clasificacion']} |")
    out.append("")

    OUT_MD.write_text("\n".join(out), encoding="utf-8")
    print(f"[OK] {OUT_MD}")
    print("\n=== SCORECARD 2026 ene-abr ===")
    for _, r in sc.iterrows():
        print(f"  {r['pais']:<20} audit={r['n_aud']} dif_acum={_fp(r['dif_acum'])}  [{r['marks']}]")
    print(f"\nCuadran <5%: {n_5} | <10%: {n_10} | sin auditar: {n_sinifc_pais} | con neg: {n_conneg}")


if __name__ == "__main__":
    main()
