"""
06_descuadre_co44.py
--------------------
Diagnostico del descuadre de partida doble (debito != credito) localizado en:
  - co44 AMERICAN ASSIST INTERNATIONAL SRL (Argentina): 2024, 2025
  - co18 GUATEMALA CONCENTRA CENTER (Guatemala): 2024
  - (2022 global, menor)

NO modifica datos. Solo diagnostica y escribe evidencia para Ikatech.

Salida: output/descuadre/DESCUADRE_co44_co18.md

Uso:
    python 06_descuadre_co44.py
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data" / "raw" / "complete_apuntes_contables_bi_mts"
GLOB = str(DATA_DIR / "anio=*" / "*.parquet").replace("\\", "/")
OUT_DIR = HERE / "output" / "descuadre"
REPORT = OUT_DIR / "DESCUADRE_co44_co18.md"

# (company_id, anio) a diagnosticar a nivel asiento
TARGETS = [(44, 2024), (44, 2025), (18, 2024)]

# terminos para la hipotesis de ajuste inflacionario
INFLA_TERMS = ["inflacion", "inflacionario", "ajuste", "recpam", "reexpresion", "monetari"]


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='6GB'")
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA disable_progress_bar")
    tmp = HERE / "data" / "duckdb_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    con.execute(f"PRAGMA temp_directory='{str(tmp).replace(chr(92), '/')}'")
    return con


def _fm(v) -> str:
    if v is None:
        return "_NaN_"
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fi(v) -> str:
    if v is None:
        return "0"
    return f"{int(v):,}".replace(",", ".")


def main() -> None:
    if not DATA_DIR.exists():
        raise SystemExit(f"No existe {DATA_DIR}. Corre 01_fetch_parquet.py.")
    con = _con()
    rel = f"read_parquet('{GLOB}', hive_partitioning=1)"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out: list[str] = []

    out.append("# Descuadre de partida doble — co44 (Argentina) y co18 (Guatemala)\n")
    out.append("Evidencia accionable para Ikatech. **No es duplicacion** (dataset ya sin dups, "
               "con `aml_id`). Es que en ciertos asientos `sum(debito) != sum(credito)`.\n")
    out.append(f"**Dataset:** `{DATA_DIR.name}`  ·  **Motor:** DuckDB {duckdb.__version__}\n")

    # contexto: descuadre por sociedad/anio (los 3 targets + 2022 global)
    out.append("\n## 0. Contexto — descuadre por sociedad/anio\n")
    ctx = con.execute(f"""
        SELECT company_id, anio, any_value(company_name) nm, count(*) filas,
               sum(debito) deb, sum(credito) cred, sum(debito)-sum(credito) dif
        FROM {rel}
        WHERE (company_id=44 AND anio IN (2024,2025)) OR (company_id=18 AND anio=2024)
        GROUP BY company_id, anio ORDER BY abs(sum(debito)-sum(credito)) DESC
    """).fetchall()
    out.append("| company_id | anio | sociedad | filas | sum debito | sum credito | diferencia |")
    out.append("|---|---|---|---:|---:|---:|---:|")
    for cid, an, nm, fl, deb, cred, dif in ctx:
        out.append(f"| {cid} | {an} | {nm} | {_fi(fl)} | {_fm(deb)} | {_fm(cred)} | {_fm(dif)} |")
    out.append("")

    # =============================================== 1. nivel asiento ====
    out.append("\n## 1. Asientos que descuadran (|diferencia| > 1), top 100 por sociedad/anio\n")
    seccion2_data = []  # para resumen de contribucion
    for cid, an in TARGETS:
        asientos = con.execute(f"""
            SELECT asiento_contable,
                   any_value(diario) diario,
                   min(fecha) fecha,
                   count(*) n_lineas,
                   sum(debito) deb, sum(credito) cred,
                   sum(debito)-sum(credito) dif
            FROM {rel}
            WHERE company_id={cid} AND anio={an}
            GROUP BY asiento_contable
            HAVING abs(sum(debito)-sum(credito)) > 1
            ORDER BY abs(sum(debito)-sum(credito)) DESC
        """).fetchall()
        # totales para resumen
        total_asientos = con.execute(
            f"SELECT count(DISTINCT asiento_contable) FROM {rel} WHERE company_id={cid} AND anio={an}"
        ).fetchone()[0]
        desc_total = sum(a[6] for a in asientos)
        top10 = sum(a[6] for a in asientos[:10])
        seccion2_data.append((cid, an, len(asientos), total_asientos, desc_total, top10))

        out.append(f"\n### co{cid} — {an}  ({len(asientos):,} asientos descuadran de {total_asientos:,} totales)\n")
        if not asientos:
            out.append("_Ninguno descuadra._\n")
            continue
        out.append("| asiento_contable | diario | fecha | # lineas | sum debito | sum credito | diferencia |")
        out.append("|---|---|---|---:|---:|---:|---:|")
        for asi, dia, fe, nl, deb, cred, dif in asientos[:100]:
            out.append(f"| {asi} | {dia} | {fe} | {nl} | {_fm(deb)} | {_fm(cred)} | {_fm(dif)} |")
        if len(asientos) > 100:
            out.append(f"\n_(+{len(asientos)-100} asientos mas no listados)_")
        out.append("")

    # =============================================== 2. contribucion ====
    out.append("\n## 2. Resumen de contribucion (¿punado o sistemico?)\n")
    out.append("| sociedad/anio | asientos que descuadran | asientos totales | % asientos | descuadre total | top-10 asientos | % del descuadre en top-10 |")
    out.append("|---|---:|---:|---:|---:|---:|---:|")
    for cid, an, n_desc, n_tot, desc_total, top10 in seccion2_data:
        pct_asi = (n_desc / n_tot * 100) if n_tot else 0
        pct_top10 = (top10 / desc_total * 100) if desc_total else 0
        out.append(f"| co{cid} {an} | {_fi(n_desc)} | {_fi(n_tot)} | {pct_asi:.2f}% | "
                   f"{_fm(desc_total)} | {_fm(top10)} | {pct_top10:.1f}% |")
    out.append("")

    # =============================================== 3. inflacion ====
    out.append("\n## 3. Hipotesis: ajuste por inflacion (co44 Argentina)\n")
    like_clause = " OR ".join([f"lower(nombre_cuenta) LIKE '%{t}%'" for t in INFLA_TERMS])
    infla = con.execute(f"""
        SELECT anio,
               sum(balance) FILTER (WHERE {like_clause}) balance_inflacion,
               sum(debito)-sum(credito) descuadre_total
        FROM {rel} WHERE company_id=44 AND anio IN (2022,2023,2024,2025,2026)
        GROUP BY anio ORDER BY anio
    """).fetchall()
    out.append(f"Terminos buscados en `nombre_cuenta`: {', '.join(INFLA_TERMS)}\n")
    out.append("| anio | balance cuentas de inflacion/ajuste | descuadre total co44 | ¿coincide magnitud? |")
    out.append("|---|---:|---:|---|")
    for an, bal_inf, desc in infla:
        coincide = ""
        if bal_inf and desc and abs(desc) > 1:
            ratio = abs(bal_inf) / abs(desc)
            coincide = f"ratio |infla/descuadre| = {ratio:.2f}"
        out.append(f"| {an} | {_fm(bal_inf)} | {_fm(desc)} | {coincide} |")
    out.append("")

    # detalle: cuentas de inflacion de co44 que aparecen
    out.append("\n**Cuentas de inflacion/ajuste presentes en co44 (todas los anios):**\n")
    infla_acc = con.execute(f"""
        SELECT codigo_cuenta, any_value(nombre_cuenta) nm, any_value(account_type) acctype,
               sum(balance) bal, count(*) filas
        FROM {rel} WHERE company_id=44 AND ({like_clause})
        GROUP BY codigo_cuenta ORDER BY abs(sum(balance)) DESC LIMIT 20
    """).fetchall()
    if not infla_acc:
        out.append("_Ninguna cuenta con esos terminos en co44._\n")
    else:
        out.append("| codigo_cuenta | nombre_cuenta | account_type | balance | filas |")
        out.append("|---|---|---|---:|---:|")
        for cc, nm, at, bal, fl in infla_acc:
            out.append(f"| {cc} | {nm} | {at} | {_fm(bal)} | {_fi(fl)} |")
    out.append("")

    # =============================================== 4. cuentas involucradas ====
    out.append("\n## 4. Cuentas mas presentes en los asientos que descuadran (co44, 2024+2025)\n")
    cuentas = con.execute(f"""
        WITH desq AS (
            SELECT asiento_contable
            FROM {rel} WHERE company_id=44 AND anio IN (2024,2025)
            GROUP BY asiento_contable
            HAVING abs(sum(debito)-sum(credito)) > 1
        )
        SELECT t.codigo_cuenta, any_value(t.nombre_cuenta) nm, any_value(t.account_type) acctype,
               sum(t.balance) bal, count(*) filas
        FROM {rel} t
        JOIN desq USING (asiento_contable)
        WHERE t.company_id=44 AND t.anio IN (2024,2025)
        GROUP BY t.codigo_cuenta ORDER BY abs(sum(t.balance)) DESC LIMIT 20
    """).fetchall()
    out.append("| codigo_cuenta | nombre_cuenta | account_type | balance | # lineas |")
    out.append("|---|---|---|---:|---:|")
    for cc, nm, at, bal, fl in cuentas:
        out.append(f"| {cc} | {nm} | {at} | {_fm(bal)} | {_fi(fl)} |")
    out.append("")

    REPORT.write_text("\n".join(out), encoding="utf-8")
    print(f"[OK] {REPORT}")
    # eco a consola del resumen de contribucion
    print("\nResumen de contribucion:")
    for cid, an, n_desc, n_tot, desc_total, top10 in seccion2_data:
        pct = (top10/desc_total*100) if desc_total else 0
        print(f"  co{cid} {an}: {n_desc}/{n_tot} asientos descuadran, descuadre={desc_total:,.2f}, top10={pct:.1f}%")


if __name__ == "__main__":
    main()
