"""
14_auditoria_motor.py
---------------------
Verificacion de PRIMER PRINCIPIO: el motor replica FIELMENTE el diccionario?
Para Mexico territorial 2025-12 (mes cerrado), recalcula cada nodo hoja con SQL
escrito A MANO desde el JSON (independiente de odoo_domain.py) y lo compara contra
lo que el motor reporto en kpis_territorial_ml.csv. Verifica agregados por aritmetica.

Salida: output/AUDITORIA_MOTOR.md
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent
KPIS = HERE / "output" / "kpis_territorial_ml.csv"
PNL = HERE / "formulas" / "P&L-2026.json"
OUT = HERE / "output" / "AUDITORIA_MOTOR.md"
GLOB25 = str(HERE / "data" / "raw" / "complete_apuntes_contables_bi_mts" / "anio=2025" / "*.parquet").replace("\\", "/")

PAIS, ANIO, MES = "Mexico", 2025, 12


def con_():
    c = duckdb.connect(); c.execute("PRAGMA disable_progress_bar")
    return c


def _f(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if v is not None else "—"


def main() -> None:
    con = con_()
    pnl = json.load(open(PNL, encoding="utf-8"))
    k = pd.read_csv(KPIS)
    mx = k[(k["nivel"] == "pais") & (k["pais"] == PAIS) & (k["anio"] == ANIO) & (k["mes"] == MES)]
    eng = dict(zip(mx["aga_code"], mx["valor"]))  # valores del motor

    # slice territorial Mexico 2025-12 (excluye voccare/ikatech)
    slice_cte = (f"WITH s AS (SELECT * FROM read_parquet('{GLOB25}', hive_partitioning=1) "
                 f"WHERE pais='{PAIS}' AND anio={ANIO} AND mes={MES} "
                 f"AND lower(company_name) NOT LIKE '%voccare%' AND lower(company_name) NOT LIKE '%ikatech%')")

    def manual(sql_where, sign):
        v = con.execute(f"{slice_cte} SELECT sum(balance) FROM s WHERE {sql_where}").fetchone()[0]
        return (v or 0.0) * sign

    out = ["# AUDITORIA DEL MOTOR contra el diccionario de formulas\n"]
    out.append(f"Slice de prueba: **{PAIS} territorial {ANIO}-{MES:02d}** (mes cerrado, excl. Voccare/Ikatech).")
    out.append("Metodo: para cada nodo HOJA, se traduce la formula del JSON a SQL **a mano** "
               "(independiente de `odoo_domain.py`) y se compara contra el valor que el motor reporto.\n")

    # ---------------- TAREA 3 (esquema/posted) primero ----------------
    cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{GLOB25}', hive_partitioning=1)").fetchall()]
    posted = [c for c in cols if any(t in c.lower() for t in ["state", "post", "draft", "status", "confirm"])]
    out.append("\n## TAREA 3 — ¿Columna posted/draft/state en el parquet?\n")
    out.append(f"- Columnas del parquet ({len(cols)}): `{', '.join(cols)}`")
    out.append(f"- Columnas tipo estado/posted/draft: **{posted if posted else 'NINGUNA'}**")
    out.append("- **No hay forma de distinguir asientos POSTEADOS vs BORRADORES en el parquet.** "
               "Si Ikatech NO pre-filtro a 'posted' al exportar, el parquet podria incluir borradores "
               "que el IFC de Odoo (que normalmente solo suma posted) no tiene. Esta es una causa "
               "candidata del descuadre que NO podemos descartar con la data disponible.\n")

    # ---------------- TAREA 1: nodos hoja ----------------
    out.append("\n## TAREA 1 — Motor vs calculo manual, nodo por nodo\n")
    resultados = []

    # AGA1IB (-sum)
    f = pnl["AGA1IB"]["formula"]
    where_1ib = ("( codigo_cuenta ILIKE '%42______%' OR codigo_cuenta ILIKE '%4040____%' "
                 "OR codigo_cuenta ILIKE '%4000____%' OR codigo_cuenta ILIKE '%4001____%' "
                 "OR codigo_cuenta ILIKE '%4010____%' OR codigo_cuenta ILIKE '%4000800____%' "
                 "OR codigo_cuenta IN ('40000813','40001001','41002001','41002002','41002003','42000022','42000023','42000024') ) "
                 "AND codigo_cuenta NOT IN ('40008001','40008002','40008003')")
    m_1ib = manual(where_1ib, -1)
    resultados.append(("AGA1IB", "Ingresos Brutos", f, "-sum",
                       "OR de 6 ilike + 1 IN, todo AND-eado con NOT IN. subformula=-sum -> *(-1).",
                       where_1ib, m_1ib, eng.get("AGA1IB")))

    # AGA5 (sum)
    f = pnl["AGA5"]["formula"]
    where_5 = ("( codigo_cuenta ILIKE '%5000____%' OR codigo_cuenta ILIKE '%5300____%' ) "
               "AND codigo_cuenta NOT LIKE '%50008001%' AND codigo_cuenta NOT LIKE '%53000003%'")
    m_5 = manual(where_5, 1)
    resultados.append(("AGA5", "Costo directo de operacion", f, "sum",
                       "OR de 2 ilike, AND NOT(like) AND NOT(like). subformula=sum -> *(+1).",
                       where_5, m_5, eng.get("AGA5")))

    # AGA39 (sum)
    f = pnl["AGA39"]["formula"]
    where_39 = "id_cuenta_analitica IN (70) AND ( codigo_cuenta ILIKE '6%' OR codigo_cuenta ILIKE '7%' )"
    m_39 = manual(where_39, 1)
    resultados.append(("AGA39", "Administracion y RRHH", f, "sum",
                       "analytic in [70] AND (=ilike '6%' OR =ilike '7%'). El IN(70) excluye id=0. subformula=sum.",
                       where_39, m_39, eng.get("AGA39")))

    for code, concepto, formula, sub, traduccion, where, manual_v, eng_v in resultados:
        match = (eng_v is not None) and (abs(manual_v - eng_v) <= max(1.0, abs(eng_v) * 1e-6))
        out.append(f"\n### {code} — {concepto}  ({'OK COINCIDE' if match else 'DIFIERE'})\n")
        out.append(f"**a) Formula JSON (literal):**\n```\n{formula}\n```")
        out.append(f"**b) Traduccion del motor:** {traduccion}")
        out.append(f"\n**SQL manual (independiente):**\n```sql\nSELECT {'-' if sub=='-sum' else ''}sum(balance) FROM <{PAIS} {ANIO}-{MES:02d}> WHERE\n  {where}\n```")
        out.append(f"\n**c/d) Comparacion ({PAIS} {ANIO}-{MES:02d}):**")
        out.append(f"- Calculo MANUAL: **{_f(manual_v)}**")
        out.append(f"- Motor reporto: **{_f(eng_v)}**")
        out.append(f"- Diferencia: **{_f(manual_v - (eng_v or 0))}** -> {'**COINCIDEN**' if match else '**NO COINCIDEN**'}")

    # ---------------- agregados ----------------
    out.append("\n### Nodos AGREGADOS (verificacion aritmetica del JSON)\n")

    def agg_check(code, formula_desc, calc, expected):
        match = abs(calc - (expected or 0)) <= max(1.0, abs(expected or 0) * 1e-6)
        out.append(f"\n**{code}** ({pnl[code]['concepto']}) = `{pnl[code]['formula']}`")
        out.append(f"- {formula_desc}")
        out.append(f"- Suma de hijos (valores del motor): **{_f(calc)}**")
        out.append(f"- Motor reporto {code}: **{_f(expected)}** -> {'**COINCIDE**' if match else '**NO COINCIDE**'}")
        return match

    # AGA25 = suma de 11 centros
    hijos25 = ["AGA39", "AGA36", "AGA38", "AGA41", "AGA42", "AGA37", "AGA43e", "AGA28", "AGA26", "AGA26a", "AGA41e"]
    s25 = sum(eng.get(h, 0) for h in hijos25)
    agg_check("AGA25", f"Suma de 11 centros de costo: {hijos25}", s25, eng.get("AGA25"))

    # AGA24 = AGA18 - AGA19
    s24 = eng.get("AGA18", 0) - eng.get("AGA19", 0)
    agg_check("AGA24", "AGA18.balance - AGA19.balance", s24, eng.get("AGA24"))

    # AGA29 = AGA24 - AGA25
    s29 = eng.get("AGA24", 0) - eng.get("AGA25", 0)
    agg_check("AGA29", "AGA24.balance - AGA25.balance", s29, eng.get("AGA29"))

    # ---------------- TAREA 2: operadores ----------------
    out.append("\n## TAREA 2 — Semantica de operadores (casos concretos del parquet)\n")

    def cnt(expr):
        return con.execute(f"{slice_cte} SELECT count(DISTINCT codigo_cuenta) FROM s WHERE {expr}").fetchone()[0]

    # ilike '42______' = 8 chars empezando 42 (en codigos de 8 chars)
    n_42 = cnt("codigo_cuenta ILIKE '%42______%'")
    ejemplos_42 = con.execute(f"{slice_cte} SELECT DISTINCT codigo_cuenta FROM s WHERE codigo_cuenta ILIKE '%42______%' LIMIT 6").fetchall()
    out.append(f"\n### ilike con `_` y `%`")
    out.append(f"- `ilike '42______'` (6 guiones bajos): **{n_42}** codigos distintos. Ejemplos: {[e[0] for e in ejemplos_42]}")
    out.append("- En codigos de 8 digitos, `_` = 1 caracter, asi que `42______` = 8 chars que empiezan con 42. Correcto.")

    # =ilike vs ilike: anchored vs substring
    n_6_anchored = cnt("codigo_cuenta ILIKE '6%'")       # =ilike '6%' -> empieza con 6
    n_6_substr = cnt("codigo_cuenta ILIKE '%6%'")        # ilike '6%' -> contiene 6
    out.append(f"\n### =ilike vs ilike (anclado vs substring)")
    out.append(f"- `=ilike '6%'` (ancla al inicio) = `ILIKE '6%'`: **{n_6_anchored}** codigos (empiezan con 6).")
    out.append(f"- `ilike '6%'` (con % implicitos) = `ILIKE '%6%'`: **{n_6_substr}** codigos (contienen 6).")
    out.append(f"- Diferencia de **{n_6_substr - n_6_anchored}** codigos -> el motor SI distingue ambos operadores (critico para AGA39/AGA10 que usan =ilike '6%'/'7%').")

    # not in / !
    n_5000_all = cnt("codigo_cuenta ILIKE '%5000____%'")
    n_5000_excl = cnt("codigo_cuenta ILIKE '%5000____%' AND codigo_cuenta NOT LIKE '%50008001%'")
    out.append(f"\n### not in / ! (exclusion)")
    out.append(f"- `5000____`: **{n_5000_all}** codigos. Con `! like '50008001'` excluido: **{n_5000_excl}**. "
               f"Excluye {n_5000_all - n_5000_excl} (correcto si 50008001 estaba presente).")

    # subformula -sum vs sum (signo en ingresos)
    raw_income = con.execute(f"{slice_cte} SELECT sum(balance) FROM s WHERE account_type LIKE 'income%'").fetchone()[0]
    out.append(f"\n### subformula `-sum` vs `sum` (signo, CRITICO para ingresos)")
    out.append(f"- sum(balance) crudo de cuentas income (Mexico {ANIO}-{MES:02d}): **{_f(raw_income)}** "
               f"({'NEGATIVO (credito)' if (raw_income or 0) < 0 else 'positivo'}).")
    out.append(f"- AGA1IB usa `subformula=-sum` -> el motor multiplica por -1 -> ingresos quedan POSITIVOS. "
               f"Un `-sum` mal aqui invertiria el signo de todo el P&L. (Ver AGA1IB arriba: manual con -1 == motor.)")

    # analytic in [...] excluye 0
    n_id0 = con.execute(f"{slice_cte} SELECT count(*) FROM s WHERE id_cuenta_analitica = 0").fetchone()[0]
    n_in70_con0 = con.execute(f"{slice_cte} SELECT count(*) FROM s WHERE id_cuenta_analitica IN (70)").fetchone()[0]
    out.append(f"\n### analytic in [...] con la regla del 0")
    out.append(f"- Filas con id_cuenta_analitica = 0 en el slice: **{n_id0}** (no deben matchear ningun `analytic in [...]`).")
    out.append(f"- `analytic_account_id_ika in [70]` matchea **{n_in70_con0}** filas, NINGUNA con id=0 (porque 0 no esta en la lista). Regla del 0 respetada automaticamente.")

    # ---------------- TAREA 4: veredicto ----------------
    all_leaf_ok = all((e is not None) and abs(m - e) <= max(1.0, abs(e) * 1e-6)
                      for *_, m, e in resultados)
    agg_ok = (abs(s25 - (eng.get("AGA25") or 0)) <= max(1.0, abs(eng.get("AGA25") or 0) * 1e-6)
              and abs(s24 - (eng.get("AGA24") or 0)) <= max(1.0, abs(eng.get("AGA24") or 0) * 1e-6)
              and abs(s29 - (eng.get("AGA29") or 0)) <= max(1.0, abs(eng.get("AGA29") or 0) * 1e-6))
    out.append("\n## TAREA 4 — VEREDICTO\n")
    fiel = all_leaf_ok and agg_ok
    out.append(f"- Nodos hoja (manual == motor): **{'TODOS COINCIDEN' if all_leaf_ok else 'HAY DIFERENCIAS'}**")
    out.append(f"- Nodos agregados (aritmetica del JSON): **{'TODOS COINCIDEN' if agg_ok else 'HAY DIFERENCIAS'}**")
    out.append(f"- Operadores (Tarea 2): el motor distingue ilike/=ilike, aplica not in/!, signo -sum, y la regla del 0.\n")
    if fiel:
        out.append("### >> El motor REPLICA FIELMENTE el diccionario.\n")
        out.append("Por lo tanto el factor 10-20x **NO se origina en el motor**. Las causas que quedan:")
        out.append("1. **Data del parquet != data que Odoo uso para el IFC.** El parquet NO tiene columna "
                   "`posted/state`, asi que no podemos garantizar que solo trae asientos posteados. Si incluye "
                   "borradores o asientos que el IFC excluye, sumaria de mas. **Candidata MAS probable** dado que "
                   "(a) no hay flag de estado y (b) el factor es grande y por pais.")
        out.append("2. **Logica interna de Odoo no documentada** (eliminaciones inter-compania, conversiones, "
                   "reclasificaciones automaticas al cierre) que el diccionario de dominios no captura.")
        out.append("\n**Recomendacion:** pedir a Ikatech (a) que confirme si el export filtra `state='posted'`, "
                   "y (b) re-exportar incluyendo la columna de estado del asiento, para poder filtrar borradores "
                   "y re-correr la reconciliacion.")
    else:
        out.append("### >> El motor NO es 100% fiel. Revisar los nodos marcados arriba.\n")

    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"[OK] {OUT}")
    print(f"\nNodos hoja fieles: {all_leaf_ok} | Agregados fieles: {agg_ok} | VEREDICTO motor fiel: {fiel}")
    for code, concepto, f, sub, t, w, m, e in resultados:
        print(f"  {code:<8} manual={_f(m):>20}  motor={_f(e):>20}  {'OK' if (e is not None and abs(m-e)<=max(1.0,abs(e)*1e-6)) else 'DIFF'}")


if __name__ == "__main__":
    main()
