"""
12_auditoria_ebitda.py
----------------------
Auditoria COMPLETA de EBITDA de los 19 paises territoriales: Odoo (AGA29, ML,
territorial, excl. Voccare/Ikatech) vs IFC (Concepto="EBITDA", Divisa=ML), mes a
mes, 2022+. UNICO criterio: EBITDA.

Clases de mes:
  - CUADRA:           ambos con dato, dif_abs_% <= tolerancia
  - NO CUADRA:        ambos con dato, dif_abs_% > tolerancia
  - SIN IFC:          IFC nulo/cero (inactivo / no cargado) -> no auditable
  - MOTOR SOSPECHOSO: el mes tiene Total Ingresos (AGA4) territorial NEGATIVO
                      -> EBITDA corrupto ese mes, no comparable

Salidas:
  output/AUDITORIA_EBITDA.md
  output/auditoria_ebitda_detalle.csv
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
KPIS = HERE / "output" / "kpis_territorial_ml.csv"
IFC = Path(r"C:\Users\Luis David\Documents\GitHub\Addiuva\consolidado_ifc_3.9.1.xlsx")
OUT_MD = HERE / "output" / "AUDITORIA_EBITDA.md"
OUT_CSV = HERE / "output" / "auditoria_ebitda_detalle.csv"

TOL = 0.05  # tolerancia principal (5%) para la clasificacion del pais

# Los 19 paises territoriales (18 con data + Panama co47 que solo tiene 2021)
PAISES_19 = ["Argentina", "Bolivia", "Chile", "Colombia", "Costa Rica",
             "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Guatemala",
             "Honduras", "Mexico", "Nicaragua", "Paraguay", "Peru", "Spain",
             "United States", "Uruguay", "Panama"]

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


def _fp(v, dec=1):
    if v is None or pd.isna(v):
        return "—"
    return f"{v*100:,.{dec}f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def _fm(v):
    if v is None or pd.isna(v):
        return "_NaN_"
    return f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    k = pd.read_csv(KPIS)
    pl = k[(k["nivel"] == "pais") & (k["anio"] >= 2022)]
    ebitda_odoo = pl[pl["aga_code"] == "AGA29"][["pais", "anio", "mes", "valor"]].rename(
        columns={"valor": "ebitda_odoo"})
    ingresos = pl[pl["aga_code"] == "AGA4"][["pais", "anio", "mes", "valor"]].rename(
        columns={"valor": "ingresos_odoo"})

    # IFC EBITDA territorial
    ifc = pd.read_excel(IFC, sheet_name=0)
    ifc.columns = [c.strip() for c in ifc.columns]
    ifc["anio"] = pd.to_datetime(ifc["Fecha"], errors="coerce").dt.year
    ifc["mes"] = pd.to_datetime(ifc["Fecha"], errors="coerce").dt.month
    ml = ifc[(ifc["Divisa"] == "ML") & (ifc["anio"] >= 2022)].copy()
    ml["concepto_norm"] = ml["Concepto"].map(_norm)
    ml["pais_parquet"] = ml["Pais"].map(map_ifc_pais)
    eb_ifc = ml[(ml["concepto_norm"] == "EBITDA") & ml["pais_parquet"].notna()]
    ebitda_ifc = (eb_ifc.groupby(["pais_parquet", "anio", "mes"], as_index=False)["Monto"]
                  .sum().rename(columns={"pais_parquet": "pais", "Monto": "ebitda_ifc"}))

    # universo de meses = los que tiene Odoo (por pais). Merge.
    df = ebitda_odoo.merge(ingresos, on=["pais", "anio", "mes"], how="left")
    df = df.merge(ebitda_ifc, on=["pais", "anio", "mes"], how="left")

    # clasificacion por mes
    def clasifica(r):
        if pd.notna(r["ingresos_odoo"]) and r["ingresos_odoo"] < 0:
            return "MOTOR SOSPECHOSO"
        if pd.isna(r["ebitda_ifc"]) or r["ebitda_ifc"] == 0:
            return "SIN IFC"
        dif_abs = abs(r["ebitda_odoo"] - r["ebitda_ifc"]) / abs(r["ebitda_ifc"])
        return "CUADRA" if dif_abs <= TOL else "NO CUADRA"

    df["diferencia"] = df["ebitda_odoo"] - df["ebitda_ifc"]
    df["dif_abs_pct"] = df.apply(
        lambda r: (abs(r["diferencia"]) / abs(r["ebitda_ifc"]))
        if pd.notna(r["ebitda_ifc"]) and r["ebitda_ifc"] != 0 else pd.NA, axis=1)
    df["clasificacion_mes"] = df.apply(clasifica, axis=1)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"[OK] {OUT_CSV} -> {len(df):,} filas")

    # ---- inventario 19 ----
    inv = []
    for p in PAISES_19:
        odoo_n = len(df[df["pais"] == p])
        ifc_n = len(ebitda_ifc[ebitda_ifc["pais"] == p])
        inv.append((p, odoo_n, ifc_n))

    # ---- scorecard por pais ----
    score = []
    for p in PAISES_19:
        d = df[df["pais"] == p]
        n_total = len(d)
        n_suspect = int((d["clasificacion_mes"] == "MOTOR SOSPECHOSO").sum())
        n_sinifc = int((d["clasificacion_mes"] == "SIN IFC").sum())
        aud = d[d["clasificacion_mes"].isin(["CUADRA", "NO CUADRA"])]
        n_aud = len(aud)
        if n_aud > 0:
            f1 = (aud["dif_abs_pct"] <= 0.01).mean()
            f5 = (aud["dif_abs_pct"] <= 0.05).mean()
            f10 = (aud["dif_abs_pct"] <= 0.10).mean()
            med = aud["dif_abs_pct"].median()
        else:
            f1 = f5 = f10 = med = None

        # clasificacion del pais (precedencia)
        if n_total == 0:
            clase = "⚪ SIN IFC"
        elif n_suspect > 0.5 * n_total:
            clase = "⚠️ BLOQUEADO POR MOTOR"
        elif n_aud == 0:
            clase = "⚪ SIN IFC"
        elif f5 >= 0.8:
            clase = "✅ VALIDADO"
        elif f5 >= 0.5:
            clase = "🟡 PARCIAL"
        else:
            clase = "🔴 NO CUADRA"
        score.append({"pais": p, "n_total": n_total, "n_aud": n_aud, "n_sinifc": n_sinifc,
                      "n_suspect": n_suspect, "f1": f1, "f5": f5, "f10": f10, "med": med,
                      "clase": clase})
    sc = pd.DataFrame(score)
    orden = {"✅ VALIDADO": 0, "🟡 PARCIAL": 1, "🔴 NO CUADRA": 2, "⚪ SIN IFC": 3, "⚠️ BLOQUEADO POR MOTOR": 4}
    sc["ord"] = sc["clase"].map(orden)
    sc = sc.sort_values(["ord", "pais"])

    # ---- MD ----
    out = ["# AUDITORIA DE EBITDA — 19 paises territoriales (Odoo vs IFC, ML, 2022+)\n"]
    out.append("Criterio UNICO: EBITDA (AGA29 ↔ Concepto 'EBITDA' del IFC). "
               "IFC en blanco/cero = inactivo/no cargado (SIN IFC, no error). "
               "Mes con ingresos negativos = MOTOR SOSPECHOSO (no comparable).\n")
    out.append(f"Tolerancia de cuadre: {int(TOL*100)}%.\n")

    out.append("\n## Tarea 1 — Inventario de los 19 paises\n")
    out.append("| pais | meses Odoo 2022+ | meses IFC EBITDA 2022+ | auditable? |")
    out.append("|---|---:|---:|---|")
    for p, on, fn in inv:
        aud = "si" if (on > 0 and fn > 0) else ("SIN IFC" if on > 0 else "sin data Odoo")
        out.append(f"| {p} | {on} | {fn} | {aud} |")
    out.append("")

    out.append("\n## Tarea 3 — SCORECARD por pais (juez: EBITDA)\n")
    out.append("| pais | clase | meses audit. | CUADRA <1% | <5% | <10% | dif mediana % | SIN IFC | motor-susp |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in sc.iterrows():
        out.append(f"| {r['pais']} | {r['clase']} | {r['n_aud']} | {_fp(r['f1'])} | {_fp(r['f5'])} | "
                   f"{_fp(r['f10'])} | {_fp(r['med'])} | {r['n_sinifc']} | {r['n_suspect']} |")
    out.append("")

    # A) conteo resumen
    out.append("\n### A. Conteo resumen (de 19)\n")
    cnt = sc["clase"].value_counts()
    out.append("| clasificacion | paises |")
    out.append("|---|---:|")
    for cl in ["✅ VALIDADO", "🟡 PARCIAL", "🔴 NO CUADRA", "⚪ SIN IFC", "⚠️ BLOQUEADO POR MOTOR"]:
        out.append(f"| {cl} | {int(cnt.get(cl, 0))} |")
    out.append("")

    # B) factor para NO CUADRA
    out.append("\n### B. NO CUADRA — factor Odoo/IFC (¿fijo o erratico?)\n")
    nocuadra = sc[sc["clase"] == "🔴 NO CUADRA"]["pais"].tolist()
    if not nocuadra:
        out.append("_Ninguno._\n")
    else:
        out.append("| pais | factor mediano Odoo/IFC | factor min | factor max | consistencia |")
        out.append("|---|---:|---:|---:|---|")
        for p in nocuadra:
            aud = df[(df["pais"] == p) & (df["clasificacion_mes"].isin(["CUADRA", "NO CUADRA"]))].copy()
            aud = aud[aud["ebitda_ifc"] != 0]
            aud["factor"] = aud["ebitda_odoo"] / aud["ebitda_ifc"]
            fac = aud["factor"]
            cons = "fijo (escala/composicion)" if fac.std() / abs(fac.mean()) < 0.5 else "erratico (otra cosa)" if len(fac) > 1 else "n/a"
            out.append(f"| {p} | {fac.median():,.1f} | {fac.min():,.1f} | {fac.max():,.1f} | {cons} |")
        out.append("")

    # C) meses motor sospechoso
    out.append("\n### C. MOTOR SOSPECHOSO — meses con ingreso negativo (fix posterior)\n")
    susp = df[df["clasificacion_mes"] == "MOTOR SOSPECHOSO"].sort_values(["pais", "anio", "mes"])
    out.append(f"Total: {len(susp)} pais-mes.\n")
    out.append("| pais | anio-mes | ingresos_odoo | ebitda_odoo |")
    out.append("|---|---|---:|---:|")
    for _, r in susp.iterrows():
        out.append(f"| {r['pais']} | {int(r['anio'])}-{int(r['mes']):02d} | "
                   f"{_fm(r['ingresos_odoo'])} | {_fm(r['ebitda_odoo'])} |")
    out.append("")

    OUT_MD.write_text("\n".join(out), encoding="utf-8")
    print(f"[OK] {OUT_MD}")
    ascii_clase = {"✅ VALIDADO": "VALIDADO", "🟡 PARCIAL": "PARCIAL", "🔴 NO CUADRA": "NO CUADRA",
                   "⚪ SIN IFC": "SIN IFC", "⚠️ BLOQUEADO POR MOTOR": "BLOQUEADO POR MOTOR"}
    print("\n=== SCORECARD ===")
    for _, r in sc.iterrows():
        f5 = "n/a" if r["f5"] is None else f"{r['f5']*100:.0f}%"
        print(f"  {r['pais']:<20} {ascii_clase[r['clase']]:<20} aud={r['n_aud']:<3} <5%={f5}")
    print("\n=== RESUMEN (de 19) ===")
    for cl in ["✅ VALIDADO", "🟡 PARCIAL", "🔴 NO CUADRA", "⚪ SIN IFC", "⚠️ BLOQUEADO POR MOTOR"]:
        print(f"  {ascii_clase[cl]}: {int(cnt.get(cl, 0))}")


if __name__ == "__main__":
    main()
