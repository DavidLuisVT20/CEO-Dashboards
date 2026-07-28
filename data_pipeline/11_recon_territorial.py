"""
11_recon_territorial.py
-----------------------
TAREA 3 + 4: reconcilia el rollup TERRITORIAL de Odoo (kpis_territorial_ml.csv)
contra el IFC territorial (consolidado, Divisa=ML, 2022+, EXCLUYENDO entidades
multipais Voccare/Ikatech). Juzgado por EBITDA (AGA29).

Salidas:
  output/RECON_TERRITORIAL.md
  output/recon_territorial_detalle.csv
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
KPIS = HERE / "output" / "kpis_territorial_ml.csv"
IFC = Path(r"C:\Users\Luis David\Documents\GitHub\Addiuva\consolidado_ifc_3.9.1.xlsx")
OUT_MD = HERE / "output" / "RECON_TERRITORIAL.md"
OUT_CSV = HERE / "output" / "recon_territorial_detalle.csv"

ANCLAS = ["AGA4", "AGA8", "AGA18", "AGA24", "AGA29"]
EBITDA = "AGA29"

AGA_TO_IFC = {
    "AGA4": "TOTAL INGRESOS", "AGA8": "MARGEN BRUTO OPERATIVO",
    "AGA18": "MARGEN NETO OPERATIVO & VENTAS", "AGA24": "MARGEN NETO DE CONTRIBUCION",
    "AGA29": "EBITDA",
}

# IFC entidades multipais a EXCLUIR del territorial
IFC_MULTIPAIS = {"IKATECH", "VOCCARE"}

# IFC pais -> parquet pais (territorial). Sub-territorios suman al padre.
IFC_PAIS_TO_PARQUET = {
    "ESTADOS UNIDOS": "United States", "PUERTO RICO": "United States", "FLORIDA": "United States",
    "ESPANA": "Spain", "REPUBLICA DOMINICANA": "Dominican Republic", "BOGOTA": "Colombia",
}
PARQUET_PAISES = ["Argentina", "Bolivia", "Chile", "Colombia", "Costa Rica",
                  "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Guatemala",
                  "Honduras", "Mexico", "Nicaragua", "Paraguay", "Peru", "Spain",
                  "United States", "Uruguay"]


def _norm(s) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split()).strip()


def map_ifc_pais(p: str):
    n = _norm(p)
    if any(m in n for m in IFC_MULTIPAIS):
        return None  # entidad multipais -> excluir del territorial
    if n in IFC_PAIS_TO_PARQUET:
        return IFC_PAIS_TO_PARQUET[n]
    for pp in PARQUET_PAISES:
        if _norm(pp) == n:
            return pp
    return None


def _fm(v):
    if v is None or pd.isna(v):
        return "_NaN_"
    return f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fp(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v*100:,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    k = pd.read_csv(KPIS)
    odoo = k[(k["nivel"] == "pais") & (k["anio"] >= 2022)][
        ["pais", "anio", "mes", "aga_code", "valor"]].rename(columns={"valor": "valor_odoo"})

    ifc = pd.read_excel(IFC, sheet_name=0)
    ifc.columns = [c.strip() for c in ifc.columns]
    ifc["anio"] = pd.to_datetime(ifc["Fecha"], errors="coerce").dt.year
    ifc["mes"] = pd.to_datetime(ifc["Fecha"], errors="coerce").dt.month

    # Reporte de paises IFC: cuales territorial vs entidad
    pais_vals = sorted(ifc["Pais"].dropna().unique())
    territoriales = [p for p in pais_vals if map_ifc_pais(p) is not None]
    entidades = [p for p in pais_vals if map_ifc_pais(p) is None]

    ml = ifc[(ifc["Divisa"] == "ML") & (ifc["anio"] >= 2022)].copy()
    ml["pais_parquet"] = ml["Pais"].map(map_ifc_pais)
    ml["concepto_norm"] = ml["Concepto"].map(_norm)
    ifc_to_aga = {v: kk for kk, v in AGA_TO_IFC.items()}
    ml["aga_code"] = ml["concepto_norm"].map(ifc_to_aga)
    ifc_match = ml.dropna(subset=["pais_parquet", "aga_code"])
    ifc_agg = (ifc_match.groupby(["pais_parquet", "anio", "mes", "aga_code"], as_index=False)["Monto"]
               .sum().rename(columns={"pais_parquet": "pais", "Monto": "monto_ifc"}))

    rec = odoo.merge(ifc_agg, on=["pais", "anio", "mes", "aga_code"], how="inner")
    rec["diferencia"] = rec["valor_odoo"] - rec["monto_ifc"]
    rec["dif_pct"] = rec.apply(lambda r: (r["diferencia"] / r["monto_ifc"])
                               if pd.notna(r["monto_ifc"]) and r["monto_ifc"] != 0 else pd.NA, axis=1)
    rec["concepto"] = rec["aga_code"].map(AGA_TO_IFC)
    rec.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"[OK] {OUT_CSV} -> {len(rec):,} filas")

    # ---- Veredicto por EBITDA ----
    paises = sorted(rec["pais"].unique())
    verdict = []
    for p in paises:
        eb = rec[(rec["pais"] == p) & (rec["aga_code"] == EBITDA)].copy()
        eb = eb[eb["dif_pct"].notna()]
        n = len(eb)
        if n == 0:
            verdict.append((p, "SIN DATOS", 0, 0, 0, 0))
            continue
        f1 = (eb["dif_pct"].abs() < 0.01).mean()
        f5 = (eb["dif_pct"].abs() < 0.05).mean()
        f10 = (eb["dif_pct"].abs() < 0.10).mean()
        if f5 > 0.8:
            color = "VERDE"
        elif f10 > 0.5:
            color = "AMARILLO"
        else:
            color = "ROJO"
        verdict.append((p, color, n, f1, f5, f10))

    # ---- MD ----
    out = ["# RECON TERRITORIAL (Odoo excl. Voccare/Ikatech) vs IFC territorial — juzgado por EBITDA\n"]
    out.append(f"- Regla exclusion v0.1 (PROVISIONAL): se excluyen razones sociales con 'voccare'/'ikatech'.")
    out.append(f"- Odoo territorial nivel pais: {len(odoo):,} filas. IFC ML 2022+ territorial: {len(ifc_match):,} filas.")
    out.append(f"- Rubros reconciliados: {len(rec):,}.\n")

    out.append("\n## Paises del IFC: territoriales vs entidad (excluidas)\n")
    out.append(f"- Tratados como TERRITORIAL: {territoriales}")
    out.append(f"- Tratados como ENTIDAD multipais (excluidos): {entidades}\n")

    out.append("\n## A. VEREDICTO POR PAIS — juzgado por EBITDA (AGA29)\n")
    out.append("Semaforo: VERDE si >80% de meses con |dif_%| EBITDA < 5%; AMARILLO si >50% dentro de 10%; ROJO si no.\n")
    out.append("| pais | sem EBITDA | meses | <1% | <5% | <10% |")
    out.append("|---|---|---:|---:|---:|---:|")
    for p, color, n, f1, f5, f10 in verdict:
        out.append(f"| {p} | {color} | {n} | {_fp(f1)} | {_fp(f5)} | {_fp(f10)} |")
    out.append("")
    verdes = [p for p, c, *_ in verdict if c == "VERDE"]
    amar = [p for p, c, *_ in verdict if c == "AMARILLO"]
    rojos = [p for p, c, *_ in verdict if c == "ROJO"]
    out.append(f"\n**EBITDA cuadra (VERDE): {len(verdes)} paises** -> {verdes}")
    out.append(f"\n**AMARILLO: {len(amar)}** -> {amar}")
    out.append(f"\n**ROJO: {len(rojos)}** -> {rojos}\n")

    out.append("\n## B. Los 5 anclas como referencia (mediana |dif_%| por pais)\n")
    out.append("> El criterio es EBITDA. Los otros anclas ayudan a ver si el descuadre viene de arriba (ingresos) o de costos.\n")
    out.append("| pais | AGA4 Ingr | AGA8 MBO | AGA18 MNOV | AGA24 MNC | AGA29 EBITDA |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for p in paises:
        cells = []
        for code in ANCLAS:
            sub = rec[(rec["pais"] == p) & (rec["aga_code"] == code)]
            sub = sub[sub["dif_pct"].notna()]
            cells.append(_fp(sub["dif_pct"].abs().median()) if len(sub) else "—")
        out.append(f"| {p} | " + " | ".join(cells) + " |")
    out.append("")

    out.append("\n## C. EBITDA mensual: Odoo vs IFC (paises clave)\n")
    for p in ["Mexico", "Colombia", "Guatemala", "Argentina", "Chile", "Bolivia", "Ecuador"]:
        eb = rec[(rec["pais"] == p) & (rec["aga_code"] == EBITDA)].sort_values(["anio", "mes"])
        if eb.empty:
            continue
        out.append(f"\n### {p}")
        out.append("| anio-mes | EBITDA Odoo | EBITDA IFC | dif_% |")
        out.append("|---|---:|---:|---:|")
        for _, r in eb.head(18).iterrows():
            out.append(f"| {int(r['anio'])}-{int(r['mes']):02d} | {_fm(r['valor_odoo'])} | "
                       f"{_fm(r['monto_ifc'])} | {_fp(r['dif_pct'])} |")
    out.append("")

    OUT_MD.write_text("\n".join(out), encoding="utf-8")
    print(f"[OK] {OUT_MD}")
    print("\nVeredicto EBITDA por pais:")
    for p, color, n, f1, f5, f10 in verdict:
        print(f"   {p:<20} {color:<10} (<5%: {_fp(f5)} de {n} meses)")


if __name__ == "__main__":
    main()
