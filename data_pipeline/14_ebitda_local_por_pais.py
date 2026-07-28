"""
14_ebitda_local_por_pais.py
---------------------------
Tabla limpia del EBITDA TERRITORIAL en MONEDA LOCAL por pais y mes, para comparar
MANUALMENTE contra la reporteria de Odoo (Contabilidad -> Reportes -> P&L).

La vara es ODOO DIRECTO (no el IFC). Esto es el motor consigo mismo en ML.
EBITDA = AGA29. Territorial v0.1 = excluye Voccare/Ikatech (ya aplicado en el CSV).

Reusa: output/kpis_territorial_ml.csv y output/clasificacion_razones_v0_1.csv.

Salidas:
  output/EBITDA_LOCAL_POR_PAIS.md
  output/ebitda_local_por_pais.csv
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
KPIS = HERE / "output" / "kpis_territorial_ml.csv"
CLASIF = HERE / "output" / "clasificacion_razones_v0_1.csv"
OUT_MD = HERE / "output" / "EBITDA_LOCAL_POR_PAIS.md"
OUT_CSV = HERE / "output" / "ebitda_local_por_pais.csv"

# Divisa local por pais (columna divisa del parquet; validado en sesiones previas).
DIVISA_ML = {
    "Argentina": "ARS", "Bolivia": "BOB", "Chile": "CLP", "Colombia": "COP", "Costa Rica": "CRC",
    "Dominican Republic": "DOP", "Ecuador": "USD", "Egypt": "EGP", "El Salvador": "USD",
    "Guatemala": "GTQ", "Honduras": "HNL", "Mexico": "MXN", "Nicaragua": "NIO", "Paraguay": "PYG",
    "Peru": "PEN", "Spain": "EUR", "United States": "USD", "Uruguay": "UYU",
}
MESES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
         7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}
# cadena del EBITDA (peldanos)
CADENA = [("AGA4", "Total Ingresos"), ("AGA5", "Costo Directo Op. (Siniestr.)"),
          ("AGA8", "Margen Bruto Operativo"), ("AGA18", "Margen Neto Op. & Venta"),
          ("AGA19", "Costos Indirectos Op."), ("AGA24", "Margen Neto Contribución"),
          ("AGA25", "Gastos Generales (GAV)"), ("AGA29", "EBITDA")]


def _fm(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    k = pd.read_csv(KPIS)
    clasif = pd.read_csv(CLASIF)
    terr = clasif[clasif["clase"] == "TERRITORIAL"]
    name_of = dict(zip(terr["company_id"], terr["company_name"]))

    pais_lvl = k[(k["nivel"] == "pais")].copy()
    soc_lvl = k[(k["nivel"] == "sociedad")].copy()

    eb_pais = pais_lvl[pais_lvl["aga_code"] == "AGA29"][["pais", "anio", "mes", "valor"]]
    paises = sorted(eb_pais["pais"].unique())

    # preliminar: ultimos 2 (anio,mes) con dato por pais (a nivel pais)
    prelim_pais = {}
    for p, g in eb_pais.groupby("pais"):
        pers = sorted(set(zip(g["anio"], g["mes"])))
        prelim_pais[p] = set(pers[-2:])
    # preliminar por sociedad
    eb_soc = soc_lvl[soc_lvl["aga_code"] == "AGA29"]
    prelim_soc = {}
    for cid, g in eb_soc.groupby("company_id"):
        pers = sorted(set(zip(g["anio"], g["mes"])))
        prelim_soc[cid] = set(pers[-2:])

    # ultimo mes cerrado por pais (ultimo no-preliminar)
    ultimo_cerrado = {}
    for p, g in eb_pais.groupby("pais"):
        pers = sorted(set(zip(g["anio"], g["mes"])))
        no_prelim = [pe for pe in pers if pe not in prelim_pais[p]]
        ultimo_cerrado[p] = (no_prelim[-1] if no_prelim else (pers[-1] if pers else None))

    out = ["# EBITDA TERRITORIAL en MONEDA LOCAL — por país y mes (para comparar vs Odoo directo)\n"]
    out.append("> Vara = **Odoo directo** (Contabilidad → Reportes → P&L), NO el IFC. "
               "EBITDA = AGA29 (motor validado al centavo vs diccionario). "
               "Territorial v0.1: excluye Voccare/Ikatech. **(P)** = mes preliminar "
               "(últimos 1-2 meses por país; devengos sin postear en Odoo → esperar incompletos).\n")

    # ============ SECCION 1: TABLA PRINCIPAL ============
    def tabla_anio(anio, titulo):
        meses_disp = sorted(eb_pais[eb_pais["anio"] == anio]["mes"].unique())
        if not meses_disp:
            return
        out.append(f"\n## 1. EBITDA por país × mes — {titulo} (moneda local)\n")
        header = "| País | Divisa | " + " | ".join(MESES[m] for m in meses_disp) + " |"
        out.append(header)
        out.append("|---|---|" + "|".join(["---:"] * len(meses_disp)) + "|")
        for p in paises:
            row = [p, DIVISA_ML.get(p, "ML")]
            for m in meses_disp:
                cell = eb_pais[(eb_pais["pais"] == p) & (eb_pais["anio"] == anio) & (eb_pais["mes"] == m)]
                if cell.empty:
                    row.append("—")
                else:
                    v = cell["valor"].iloc[0]
                    mark = " (P)" if (anio, m) in prelim_pais.get(p, set()) else ""
                    row.append(_fm(v) + mark)
            out.append("| " + " | ".join(row) + " |")
        out.append("")

    tabla_anio(2026, "2026")
    tabla_anio(2025, "2025 (contexto)")

    # ============ SECCION 3: COBERTURA (antes de la 2, util como mapa) ============
    out.append("\n## 3. Resumen de cobertura y señales de ruido (2026)\n")
    out.append("| País | meses 2026 | último cerrado | EBITDA últ. cerrado | meses negativos 2026 | meses en cero 2026 |")
    out.append("|---|---:|---|---:|---|---|")
    n_con_2026 = 0
    for p in paises:
        g26 = eb_pais[(eb_pais["pais"] == p) & (eb_pais["anio"] == 2026)]
        if g26.empty:
            out.append(f"| {p} | 0 | — | — | — | — |")
            continue
        n_con_2026 += 1
        uc = ultimo_cerrado[p]
        uc_val = None
        if uc:
            cc = eb_pais[(eb_pais["pais"] == p) & (eb_pais["anio"] == uc[0]) & (eb_pais["mes"] == uc[1])]
            uc_val = cc["valor"].iloc[0] if not cc.empty else None
        negs = sorted(m for m in g26["mes"] if g26[g26["mes"] == m]["valor"].iloc[0] < 0)
        zeros = sorted(m for m in g26["mes"] if abs(g26[g26["mes"] == m]["valor"].iloc[0]) < 1)
        uc_lbl = f"{MESES[uc[1]]} {uc[0]}" if uc else "—"
        out.append(f"| {p} | {g26['mes'].nunique()} | {uc_lbl} | {_fm(uc_val)} | "
                   f"{', '.join(MESES[m] for m in negs) if negs else 'ninguno'} | "
                   f"{', '.join(MESES[m] for m in zeros) if zeros else 'ninguno'} |")
    out.append("")

    # ============ SECCION 2: NIVEL SOCIEDAD (2026) ============
    out.append("\n## 2. EBITDA por SOCIEDAD (2026) — para comparar manzana-vs-manzana en Odoo\n")
    out.append("> En Odoo descargas por sociedad (ej. 'Chile SPA'), no por país. Para países con "
               "varias razones sociales, compara aquí sociedad por sociedad.\n")
    meses26 = sorted(eb_soc[eb_soc["anio"] == 2026]["mes"].unique())
    for p in paises:
        socs = sorted(soc_lvl[soc_lvl["pais"] == p]["company_id"].dropna().unique())
        if not socs:
            continue
        out.append(f"\n### {p}  ({DIVISA_ML.get(p, 'ML')})\n")
        out.append("| company_id | Razón social | " + " | ".join(MESES[m] for m in meses26) + " |")
        out.append("|---|---|" + "|".join(["---:"] * len(meses26)) + "|")
        for cid in socs:
            cid_i = int(cid)
            row = [str(cid_i), str(name_of.get(cid_i, name_of.get(cid, "?")))[:42]]
            for m in meses26:
                cell = eb_soc[(eb_soc["company_id"] == cid) & (eb_soc["anio"] == 2026) & (eb_soc["mes"] == m)]
                if cell.empty:
                    row.append("—")
                else:
                    v = cell["valor"].iloc[0]
                    mark = " (P)" if (2026, m) in prelim_soc.get(cid, set()) else ""
                    row.append(_fm(v) + mark)
            out.append("| " + " | ".join(row) + " |")
        out.append("")

    # ============ SECCION 4: CADENA DEL EBITDA (ultimo mes cerrado) ============
    out.append("\n## 4. Cadena del EBITDA por país — último mes cerrado (ML)\n")
    out.append("> Si un país NO hace match en Odoo, mira en qué peldaño se abre la diferencia. "
               "AGA8 = AGA4−AGA5−AGA7 · AGA18 = AGA8−AGA10−AGA11 · AGA24 = AGA18−AGA19 · AGA29 = AGA24−AGA25.\n")
    out.append("| País | Mes cerrado | " + " | ".join(c for _, c in CADENA) + " |")
    out.append("|---|---|" + "|".join(["---:"] * len(CADENA)) + "|")
    for p in paises:
        uc = ultimo_cerrado[p]
        if not uc:
            continue
        anio, mes = uc
        row = [p, f"{MESES[mes]} {anio}"]
        slice_p = pais_lvl[(pais_lvl["pais"] == p) & (pais_lvl["anio"] == anio) & (pais_lvl["mes"] == mes)]
        vals = dict(zip(slice_p["aga_code"], slice_p["valor"]))
        for code, _ in CADENA:
            row.append(_fm(vals.get(code)))
        out.append("| " + " | ".join(row) + " |")
    out.append("")

    OUT_MD.write_text("\n".join(out), encoding="utf-8")

    # ============ CSV (todo el detalle) ============
    keep = ["AGA4", "AGA5", "AGA8", "AGA18", "AGA19", "AGA24", "AGA25", "AGA29"]
    concepto = {c: n for c, n in CADENA}
    rows = []
    # nivel pais
    for _, r in pais_lvl[pais_lvl["aga_code"].isin(keep)].iterrows():
        rows.append({"pais": r["pais"], "company_id": "", "company_name": "(consolidado país)",
                     "divisa": DIVISA_ML.get(r["pais"], "ML"), "anio": int(r["anio"]), "mes": int(r["mes"]),
                     "aga_code": r["aga_code"], "concepto": concepto.get(r["aga_code"], r["aga_code"]),
                     "valor_ml": r["valor"],
                     "preliminar": (int(r["anio"]), int(r["mes"])) in prelim_pais.get(r["pais"], set())})
    # nivel sociedad
    for _, r in soc_lvl[soc_lvl["aga_code"].isin(keep)].iterrows():
        cid = int(r["company_id"]) if pd.notna(r["company_id"]) else ""
        rows.append({"pais": r["pais"], "company_id": cid, "company_name": name_of.get(cid, "?"),
                     "divisa": DIVISA_ML.get(r["pais"], "ML"), "anio": int(r["anio"]), "mes": int(r["mes"]),
                     "aga_code": r["aga_code"], "concepto": concepto.get(r["aga_code"], r["aga_code"]),
                     "valor_ml": r["valor"],
                     "preliminar": (int(r["anio"]), int(r["mes"])) in prelim_soc.get(r["company_id"], set())})
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8")

    print(f"[OK] {OUT_MD}")
    print(f"[OK] {OUT_CSV} ({len(rows):,} filas)")
    print(f"[INFO] Paises territoriales con EBITDA en 2026: {n_con_2026} de {len(paises)}")


if __name__ == "__main__":
    main()
