"""
06_profile_complete.py
----------------------
Perfilado del dataset 'complete_apuntes_contables_bi_mts' (Hive, ~113M filas,
4.68 GB) usando DuckDB para no reventar memoria (streaming + spill a disco).

Genera data_pipeline/PROFILE_REPORT_complete.md con:
  - Tarea 2: completitud (filas/anios/paises/divisas/sociedades) vs baseline.
  - Tarea 3: esquema (22 cols, equity_unaffected, tasa_cambio, particionado).
  - Tarea 4: sanidad, DUPLICADOS (total vs unicas), Balance por anio, cobertura.

Uso:
    python 06_profile_complete.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data" / "raw" / "complete_apuntes_contables_bi_mts"
GLOB = str(DATA_DIR / "anio=*" / "*.parquet").replace("\\", "/")
REPORT = HERE / "PROFILE_REPORT_complete.md"
FORMULAS_PNL = HERE / "formulas" / "P&L-2026.json"
FORMULAS_BAL = HERE / "formulas" / "Balance-General-2026.json"

# Baselines conocidos de sesiones anteriores
BASE_RECORTADO_FILAS = 222_634
BASE_ORIGINAL_FILAS = 8_050_896
PAISES_QUE_FALTABAN = ["Chile", "Peru", "Ecuador", "Nicaragua", "Honduras", "Paraguay",
                       "Panama", "El Salvador", "Republica Dominicana", "Venezuela",
                       "Brasil", "Espana", "Egipto"]
DIVISAS_QUE_FALTABAN = ["CLP", "PEN", "DOP", "PYG", "NIO", "EGP", "EUR"]


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='6GB'")
    con.execute("PRAGMA threads=4")
    tmp = (HERE / "data" / "duckdb_tmp")
    tmp.mkdir(parents=True, exist_ok=True)
    con.execute(f"PRAGMA temp_directory='{str(tmp).replace(chr(92), '/')}'")
    return con


def _fi(v) -> str:
    if v is None:
        return "0"
    return f"{int(v):,}".replace(",", ".")


def _fm(v) -> str:
    if v is None:
        return "_NaN_"
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _like_to_regex(pattern: str) -> str:
    parts = []
    for ch in pattern:
        if ch == "_":
            parts.append(".")
        elif ch == "%":
            parts.append(".*")
        else:
            parts.append(re.escape(ch))
    return "^" + "".join(parts) + "$"


def main() -> None:
    if not DATA_DIR.exists():
        print(f"[ERROR] No existe {DATA_DIR}. Corre 01_fetch_parquet.py.", file=sys.stderr)
        sys.exit(1)

    con = _con()
    rel = f"read_parquet('{GLOB}', hive_partitioning=1)"
    out: list[str] = []
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"[{time.time()-t0:6.1f}s] {msg}", flush=True)

    out.append("# PROFILE_REPORT — complete_apuntes_contables_bi_mts\n")
    out.append(f"**Dataset:** `{DATA_DIR.name}` (Hive)  ")
    out.append(f"**Motor:** DuckDB {duckdb.__version__}  \n")

    # ---------------------------------------------------- esquema ----
    log("Esquema...")
    cols = con.execute(f"DESCRIBE SELECT * FROM {rel}").fetchall()
    colnames = [c[0] for c in cols]
    esperadas = ["fecha", "anio", "mes", "pais", "company_id", "company_name", "diario",
                 "asiento_contable", "codigo_cuenta", "nombre_cuenta", "tipo_cuenta",
                 "contacto", "etiqueta", "id_cuenta_analitica", "cuenta_analitica",
                 "id_etiquetas_analiticas", "etiquetas_analiticas", "debito", "credito",
                 "balance", "divisa", "tasa_cambio"]
    # tipo_cuenta llega como account_type
    alias = {"account_type": "tipo_cuenta"}
    present_norm = set(colnames) | {alias.get(c, c) for c in colnames}
    falt = [c for c in esperadas if c not in present_norm]
    extra = [c for c in colnames if c not in esperadas and alias.get(c, c) not in esperadas]

    tc = "tipo_cuenta" if "tipo_cuenta" in colnames else ("account_type" if "account_type" in colnames else None)

    # --------------------------------------------- Tarea 2: filas ----
    log("Conteo de filas total y por anio...")
    total = con.execute(f"SELECT count(*) FROM {rel}").fetchone()[0]
    por_anio = con.execute(
        f"SELECT anio, count(*) n FROM {rel} GROUP BY anio ORDER BY anio"
    ).fetchall()

    out.append("\n---\n## TAREA 2 — Completitud\n")
    out.append(f"**Filas totales:** {_fi(total)}  ")
    out.append(f"- Baseline recortado (sesion previa): {_fi(BASE_RECORTADO_FILAS)}  ")
    out.append(f"- Baseline original (mayo): {_fi(BASE_ORIGINAL_FILAS)}  ")
    factor = total / BASE_ORIGINAL_FILAS if BASE_ORIGINAL_FILAS else 0
    out.append(f"- Este dataset es **{factor:.1f}x** el original de mayo.  \n")

    out.append("\n### Filas por anio\n")
    out.append("| anio | filas |")
    out.append("|---|---:|")
    anios_presentes = []
    for a, n in por_anio:
        anios_presentes.append(int(a))
        out.append(f"| {a} | {_fi(n)} |")
    out.append("")
    faltan_anios = [y for y in range(2015, 2022) if y not in anios_presentes]
    out.append(f"- **Anios 2015-2021:** {'TODOS presentes' if not faltan_anios else 'faltan ' + str(faltan_anios)}")
    out.append(f"- Rango: {min(anios_presentes)}–{max(anios_presentes)}\n")

    # ----------------------------------------------- paises ----
    log("Paises...")
    paises = con.execute(
        f"SELECT pais, count(*) n FROM {rel} GROUP BY pais ORDER BY n DESC"
    ).fetchall()
    out.append("\n### Paises (columna `pais`)\n")
    out.append(f"**Total paises distintos:** {len(paises)}\n")
    out.append("| pais | filas |")
    out.append("|---|---:|")
    for p, n in paises:
        out.append(f"| {p} | {_fi(n)} |")
    out.append("")
    norm_paises = {(_p or "").lower() for _p, _ in paises}
    def _norm(s): return s.lower().replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
    volvieron = []
    siguen_faltando = []
    ALIAS = {"espana": ["spain"], "egipto": ["egypt"], "peru": ["peru"],
             "republica dominicana": ["dominican republic", "dominicana"]}
    for p in PAISES_QUE_FALTABAN:
        np = _norm(p)
        formas = {np} | {_norm(a) for a in ALIAS.get(np, [])}
        # Solo paises NO nulos; nunca comparar contra cadena vacia.
        hit = any(
            (pp and (np in _norm(pp) or any(f in _norm(pp) for f in formas)))
            for pp, _ in paises
        )
        (volvieron if hit else siguen_faltando).append(p)
    out.append(f"- De los 13 que faltaban, **volvieron:** {volvieron if volvieron else 'ninguno'}")
    out.append(f"- **Siguen faltando:** {siguen_faltando if siguen_faltando else 'ninguno'}\n")

    # ----------------------------------------------- divisas ----
    log("Divisas...")
    divisas = con.execute(
        f"SELECT divisa, count(*) n FROM {rel} GROUP BY divisa ORDER BY n DESC"
    ).fetchall()
    out.append("\n### Divisas\n")
    out.append(f"**Total divisas distintas:** {len(divisas)}\n")
    out.append("| divisa | filas |")
    out.append("|---|---:|")
    for d, n in divisas:
        out.append(f"| {d} | {_fi(n)} |")
    out.append("")
    div_set = {(d or "").upper() for d, _ in divisas}
    div_volv = [d for d in DIVISAS_QUE_FALTABAN if d in div_set]
    div_falt = [d for d in DIVISAS_QUE_FALTABAN if d not in div_set]
    out.append(f"- Divisas que faltaban y **volvieron:** {div_volv if div_volv else 'ninguna'}")
    out.append(f"- **Siguen faltando:** {div_falt if div_falt else 'ninguna'}\n")

    # ----------------------------------------------- sociedades ----
    log("Sociedades...")
    n_soc = con.execute(f"SELECT count(DISTINCT company_id) FROM {rel}").fetchone()[0]
    out.append(f"\n### Sociedades\n**company_id distintos:** {n_soc}  (recortado tenia 19; original ~44)\n")

    # --------------------------------------------- Tarea 3: esquema ----
    out.append("\n---\n## TAREA 3 — Esquema\n")
    out.append(f"**Columnas ({len(colnames)}):** {colnames}\n")
    out.append(f"- Faltantes vs 22 esperadas: {falt if falt else 'NINGUNA'}")
    out.append(f"- Extra: {extra if extra else 'ninguna'}")
    out.append(f"- `tipo_cuenta` llega como: **`{tc}`**\n")

    # tipo_cuenta valores
    log("account_type / tipo_cuenta...")
    tc_vals = con.execute(
        f"SELECT {tc} t, count(*) n FROM {rel} GROUP BY {tc} ORDER BY n DESC"
    ).fetchall()
    out.append("\n### Valores de `tipo_cuenta` (account_type)\n")
    out.append("| account_type | filas |")
    out.append("|---|---:|")
    tipos = set()
    for t, n in tc_vals:
        tipos.add(t)
        out.append(f"| {t} | {_fi(n)} |")
    out.append("")
    eq_u = "equity_unaffected" in tipos
    eq = "equity" in tipos
    out.append("### Checks CRITICOS de account_type\n")
    out.append(f"- **`equity_unaffected` presente:** {'SI ✅' if eq_u else 'NO ❌ (A74 NO se calcula, Balance bloqueado)'}")
    out.append(f"- **`equity` presente:** {'SI' if eq else 'NO'}")
    out.append(f"- asset_* presentes: {sorted(t for t in tipos if t and t.startswith('asset'))}")
    out.append(f"- liability_* presentes: {sorted(t for t in tipos if t and t.startswith('liability'))}")
    out.append(f"- expense/expense_direct_cost: {'SI' if any(t in tipos for t in ['expense','expense_direct_cost']) else 'NO'}\n")

    # tasa_cambio nulos
    log("tasa_cambio nulos por anio...")
    tc_null = con.execute(
        f"SELECT anio, count(*) n, count(*) FILTER (WHERE tasa_cambio IS NULL) nulos "
        f"FROM {rel} GROUP BY anio ORDER BY anio"
    ).fetchall()
    out.append("\n### tasa_cambio — % nulos por anio\n")
    out.append("| anio | filas | nulos | % nulos |")
    out.append("|---|---:|---:|---:|")
    for a, n, nu in tc_null:
        pct = (nu / n * 100) if n else 0
        out.append(f"| {a} | {_fi(n)} | {_fi(nu)} | {pct:.1f}% |")
    out.append("")

    # particionado: min/max fecha por anio
    log("Integridad de particionado (min/max fecha por anio)...")
    part = con.execute(
        f"SELECT anio, min(fecha) mn, max(fecha) mx, "
        f"count(*) FILTER (WHERE CAST(substr(fecha,1,4) AS INT) <> anio) fuera "
        f"FROM {rel} GROUP BY anio ORDER BY anio"
    ).fetchall()
    out.append("\n### Integridad de particionado (fecha dentro del anio de la particion)\n")
    out.append("| particion anio | min fecha | max fecha | filas con fecha de OTRO anio |")
    out.append("|---|---|---|---:|")
    part_bug = 0
    for a, mn, mx, fuera in part:
        part_bug += fuera
        flag = "" if fuera == 0 else " ⚠️"
        out.append(f"| {a} | {mn} | {mx} | {_fi(fuera)}{flag} |")
    out.append("")
    out.append(f"- Total filas mal particionadas: **{_fi(part_bug)}** {'(OK)' if part_bug==0 else '(BUG de particionado)'}\n")

    # ---------------------------------------- Tarea 4A: sanidad ----
    out.append("\n---\n## TAREA 4 — Perfilado, duplicados, Balance\n")
    log("Sanidad balance = debito - credito...")
    bad_bal = con.execute(
        f"SELECT count(*) FROM {rel} WHERE abs(balance - (debito - credito)) > 0.01"
    ).fetchone()[0]
    out.append("### A. Sanidad\n")
    out.append(f"- Filas con `balance != debito - credito` (tol 0.01): **{_fi(bad_bal)}** "
               f"({bad_bal/total*100:.4f}%)")
    # granularidad
    lineas_por_asiento = con.execute(
        f"SELECT count(*)*1.0/count(DISTINCT asiento_contable) FROM {rel}"
    ).fetchone()[0]
    out.append(f"- Lineas por asiento (promedio): **{lineas_por_asiento:.2f}** → granularidad transaccional\n")

    # ---------------------------------------- Tarea 4B: duplicados ----
    log("DUPLICADOS: distinct sobre todas las columnas (puede tardar)...")
    distinct_all = con.execute(
        f"SELECT count(*) FROM (SELECT DISTINCT * FROM {rel})"
    ).fetchone()[0]
    log("DUPLICADOS: distinct excluyendo columnas de etiquetas analiticas...")
    distinct_no_tags = con.execute(
        f"SELECT count(*) FROM (SELECT DISTINCT * EXCLUDE (id_etiquetas_analiticas, etiquetas_analiticas) FROM {rel})"
    ).fetchone()[0]
    out.append("### B. Duplicados\n")
    out.append(f"- Filas TOTALES: **{_fi(total)}**")
    out.append(f"- Filas UNICAS (DISTINCT de las 24 columnas): **{_fi(distinct_all)}**")
    dups = total - distinct_all
    out.append(f"- Filas duplicadas exactas: **{_fi(dups)}** ({dups/total*100:.1f}%)")
    out.append(f"- Filas UNICAS excluyendo `id_etiquetas_analiticas`+`etiquetas_analiticas`: **{_fi(distinct_no_tags)}**")
    # Solo es "explosion por etiquetas" si al excluirlas el distinct cae MUCHO (>10%).
    caida_tags = (distinct_all - distinct_no_tags) / distinct_all if distinct_all else 0
    if caida_tags > 0.10:
        out.append(f"  - ⚠️ Excluir las etiquetas reduce el distinct {caida_tags*100:.1f}% "
                   f"→ parte de la duplicacion proviene de explosion por etiquetas analiticas.")
    else:
        out.append(f"  - Excluir las etiquetas casi no cambia el distinct ({caida_tags*100:.2f}%) "
                   f"→ NO es explosion por etiquetas: son **filas exactas completas duplicadas**.")
    factor_dup = total / distinct_all if distinct_all else 1
    out.append(f"- Factor de duplicacion global (total/unicas): **{factor_dup:.2f}x**")
    out.append("- ⚠️ Revertir con DISTINCT NO es seguro sin un identificador de linea (move_line_id): "
               "lineas legitimamente identicas se colapsarian. Ver verificacion de trial balance dedup.\n")

    # ---------------------------------------- Tarea 4C: Balance ----
    log("Balance por anio (trial balance + componentes)...")
    bal = con.execute(f"""
        SELECT anio,
          sum(balance) FILTER (WHERE {tc} LIKE 'asset%') activos,
          sum(balance) FILTER (WHERE {tc} LIKE 'liability%') pasivos,
          sum(balance) FILTER (WHERE {tc} IN ('equity','equity_unaffected')) patrimonio,
          sum(balance) FILTER (WHERE {tc} LIKE 'income%') ingresos,
          sum(balance) FILTER (WHERE {tc} LIKE 'expense%') gastos,
          sum(balance) total_trial
        FROM {rel} GROUP BY anio ORDER BY anio
    """).fetchall()
    out.append("### C. Balance por anio (suma de `balance`, signo Odoo: debito-credito)\n")
    out.append("> Nota: en signo Odoo, activos salen positivos y pasivos/patrimonio negativos. "
               "El *trial balance* (suma de TODO) debe ser ≈0 si debitos=creditos. "
               "La suma mezcla divisas; cada sociedad cuadra en SU moneda, asi que el total global "
               "tambien suma ≈0 (suma de ceros), pero los componentes entre paises NO son comparables.\n")
    out.append("| anio | activos | pasivos | patrimonio | ingresos | gastos | trial balance (≈0?) |")
    out.append("|---|---:|---:|---:|---:|---:|---:|")
    for a, act, pas, pat, ing, gas, tot in bal:
        out.append(f"| {a} | {_fm(act)} | {_fm(pas)} | {_fm(pat)} | {_fm(ing)} | {_fm(gas)} | {_fm(tot)} |")
    out.append("")

    # ---------------------------------------- Tarea 4D: cobertura ----
    log("Cobertura de formulas (distinct codes + analytics)...")
    codes = set(r[0] for r in con.execute(
        f"SELECT DISTINCT codigo_cuenta FROM {rel} WHERE codigo_cuenta IS NOT NULL"
    ).fetchall())
    analytics = set(r[0] for r in con.execute(
        f"SELECT DISTINCT id_cuenta_analitica FROM {rel} WHERE id_cuenta_analitica IS NOT NULL AND id_cuenta_analitica <> 0"
    ).fetchall())
    out.append("### D. Cobertura de formulas (sobre codigos/analiticos que EXISTEN en la data)\n")
    out.append(f"- codigo_cuenta distintos: **{_fi(len(codes))}**")
    out.append(f"- id_cuenta_analitica distintos (excl. 0): **{_fi(len(analytics))}**\n")

    # patrones clave del P&L
    def codes_match(pattern: str) -> int:
        rgx = re.compile(_like_to_regex(pattern))
        return sum(1 for c in codes if rgx.match(str(c)))

    kpi_codes = {
        "AGA4 Total Ingresos (42______/40xx)": ["42______", "4040____", "4000____", "4001____", "4010____"],
        "AGA5 Siniestralidad (5000____/5300____)": ["5000____", "5300____"],
        "AGA44 Depreciacion (65000%)": ["65000%"],
    }
    out.append("**Patrones de codigo de KPIs clave (cuantos codigos hacen match):**\n")
    out.append("| KPI | patron | # codigos en data |")
    out.append("|---|---|---:|")
    for kpi, pats in kpi_codes.items():
        for p in pats:
            out.append(f"| {kpi} | `{p}` | {codes_match(p)} |")
    out.append("")

    # analiticos del P&L (EBITDA/GAV)
    pnl_analytics = [61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,78,79,2653,4361,4376,42110]
    presentes_an = sorted(a for a in pnl_analytics if a in analytics)
    faltan_an = sorted(a for a in pnl_analytics if a not in analytics)
    out.append("**Cuentas analiticas del P&L (EBITDA/GAV):**\n")
    out.append(f"- Presentes: {presentes_an}")
    out.append(f"- Ausentes: {faltan_an}  (4361 es ausente por diseno, regla confirmada)\n")

    # ---------------------------------------- Tarea 4E: mapeo ----
    log("Mapeo company_id -> pais -> company_name...")
    mapeo = con.execute(f"""
        SELECT company_id, any_value(company_name) nm, any_value(pais) pais,
               count(*) filas, min(fecha) mn, max(fecha) mx
        FROM {rel} GROUP BY company_id ORDER BY pais, nm
    """).fetchall()
    out.append("### E. Mapeo company_id → pais → company_name\n")
    out.append("| company_id | company_name | pais | filas | fecha min | fecha max |")
    out.append("|---|---|---|---:|---|---|")
    for cid, nm, pais, fl, mn, mx in mapeo:
        out.append(f"| {cid} | {nm} | {pais} | {_fi(fl)} | {mn} | {mx} |")
    out.append("")

    REPORT.write_text("\n".join(out), encoding="utf-8")
    log(f"Reporte escrito en {REPORT}")

    # Resumen a consola
    print("\n" + "=" * 70)
    print("RESUMEN EJECUTIVO")
    print("=" * 70)
    print(f"  Filas totales      : {_fi(total)}")
    print(f"  Filas unicas (24c) : {_fi(distinct_all)}  (dups: {_fi(total-distinct_all)})")
    print(f"  Filas unicas s/tags: {_fi(distinct_no_tags)}  (factor inflado: {total/distinct_no_tags:.2f}x)")
    print(f"  Anios              : {min(anios_presentes)}-{max(anios_presentes)} ({len(anios_presentes)})")
    print(f"  Paises             : {len(paises)}")
    print(f"  Divisas            : {len(divisas)}")
    print(f"  Sociedades         : {n_soc}")
    print(f"  equity_unaffected  : {'SI' if eq_u else 'NO'}")
    print(f"  balance != deb-cred: {_fi(bad_bal)}")
    print(f"  particion mal filt : {_fi(part_bug)}")


if __name__ == "__main__":
    main()
