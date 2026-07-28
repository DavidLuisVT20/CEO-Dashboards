"""
02_profile.py
-------------
Perfila el parquet local de apuntes contables y valida su cobertura contra
los diccionarios de formulas (P&L y Balance). Escribe PROFILE_REPORT.md.

Uso:
    python 02_profile.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from tabulate import tabulate


HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "data" / "raw"
FORMULAS_DIR = HERE / "formulas"
REPORT_PATH = HERE / "PROFILE_REPORT.md"

# Columnas esperadas (esquema confirmado en el brief)
EXPECTED_COLS = [
    "fecha", "anio", "mes", "pais", "company_id", "company_name", "diario",
    "asiento_contable", "codigo_cuenta", "nombre_cuenta", "tipo_cuenta",
    "contacto", "etiqueta", "id_cuenta_analitica", "cuenta_analitica",
    "id_etiquetas_analiticas", "etiquetas_analiticas", "debito", "credito",
    "balance", "divisa", "tasa_cambio",
]

# Regex que extraen constantes literales de los STRINGS DE FORMULA
# (las formulas vienen serializadas como dominios de Odoo: cadenas tipo
#  "[('account_id.code','ilike','42______'), ('analytic_account_id_ika','in',[62,63])]")
#
# CODE_LIKE: cualquier literal entre comillas simples que parezca codigo contable.
CODE_LIKE_RE = re.compile(r"'([0-9][0-9_%]{2,15})'")
# ANALYTIC_IN: extrae el contenido de [...] dentro de
#   ('analytic_account_id_ika','in',[N1, N2, ...])
ANALYTIC_IN_RE = re.compile(
    r"analytic_account_id_ika['\"]\s*,\s*['\"]in['\"]\s*,\s*\[([^\]]+)\]",
    re.IGNORECASE,
)
# ACCOUNT_TYPE_USE: detecta si la formula usa account_id.account_type
ACCOUNT_TYPE_RE = re.compile(r"account_id\.account_type", re.IGNORECASE)


def _iter_formula_nodes(payload: Any):
    """
    Itera los nodos top-level del JSON de formulas: (clave_kpi, concepto, formula_str).
    Maneja dos formatos:
    - { "AGA1": { "concepto": "...", "formula": "..." }, ... }
    - { "A74": { "expressions": [ { "label": "...", "formula": "..." }, ... ] }, ... }
    """
    if not isinstance(payload, dict):
        return
    for k, node in payload.items():
        if not isinstance(node, dict):
            continue
        concepto = node.get("concepto") or k
        formula = node.get("formula")
        if isinstance(formula, str):
            yield k, concepto, formula
        # variante con "expressions": [ {label, formula}, ... ]
        for expr in node.get("expressions", []) or []:
            if isinstance(expr, dict) and isinstance(expr.get("formula"), str):
                label = expr.get("label") or "expr"
                yield f"{k}.{label}", f"{concepto} ({label})", expr["formula"]


# ---------- helpers ----------------------------------------------------------

def _fmt_int(n: int | float) -> str:
    return f"{int(n):,}".replace(",", ".")


def _fmt_pct(num: int | float, den: int | float) -> str:
    if not den:
        return "0,00%"
    return f"{(num / den) * 100:,.2f}%".replace(".", ",")


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    return tabulate(df, headers="keys", tablefmt="github", showindex=False)


def _like_to_regex(pattern: str) -> re.Pattern[str]:
    """Convierte un patron SQL LIKE ('_' = 1 char, '%' = 0+ chars) a regex.
    Se construye char por char porque re.escape en Python 3.7+ NO escapa '_',
    asi que un .replace post-escape no funciona."""
    parts: list[str] = []
    for ch in pattern:
        if ch == "_":
            parts.append(".")
        elif ch == "%":
            parts.append(".*")
        else:
            parts.append(re.escape(ch))
    return re.compile("^" + "".join(parts) + "$")


# ---------- carga del parquet ------------------------------------------------

def _find_parquet() -> Path:
    parquets = sorted(RAW_DIR.glob("*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not parquets:
        print(f"[ERROR] No hay .parquet en {RAW_DIR}. Corre primero 01_fetch_parquet.py.", file=sys.stderr)
        sys.exit(1)
    return parquets[0]


def _load_df() -> tuple[pd.DataFrame, Path]:
    pq_path = _find_parquet()
    print(f"[INFO] Leyendo {pq_path} ...")
    df = pd.read_parquet(pq_path)
    print(f"[INFO] OK. shape={df.shape}")
    return df, pq_path


# ---------- parseo de los JSON de formulas -----------------------------------

def _walk(node: Any):
    """Generador recursivo: yield (parent_key, value) para cada hoja/contenedor."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield None, v
            yield from _walk(v)


def _extract_codes_from_formula(formula: str) -> set[str]:
    """Extrae patrones de codigo contable embebidos en un string de dominio Odoo."""
    return set(CODE_LIKE_RE.findall(formula))


def _extract_analytic_ids_from_formula(formula: str) -> set[int]:
    ids: set[int] = set()
    for m in ANALYTIC_IN_RE.finditer(formula):
        for tok in m.group(1).split(","):
            tok = tok.strip().strip("'\"")
            if tok.isdigit():
                ids.add(int(tok))
    return ids


def _formula_uses_account_type(formula: str) -> bool:
    return bool(ACCOUNT_TYPE_RE.search(formula))


def _load_formula_jsons() -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not FORMULAS_DIR.exists():
        print(f"[WARN] {FORMULAS_DIR} no existe.")
        return out
    for p in sorted(FORMULAS_DIR.glob("*.json")):
        try:
            with p.open(encoding="utf-8") as fh:
                out[p.name] = json.load(fh)
            print(f"[INFO] Cargado {p.name}")
        except Exception as e:
            print(f"[WARN] No pude leer {p.name}: {e}")
    return out


# ---------- secciones del reporte --------------------------------------------

def _section_header(df: pd.DataFrame, pq_path: Path) -> list[str]:
    out = []
    out.append("# PROFILE_REPORT — apuntes contables\n")
    out.append(f"**Archivo:** `{pq_path.name}`  ")
    out.append(f"**Filas:** {_fmt_int(len(df))}  ")
    out.append(f"**Columnas:** {df.shape[1]}  \n")
    return out


def _section_schema(df: pd.DataFrame) -> list[str]:
    rows = []
    for c in df.columns:
        s = df[c]
        sample = s.dropna().iloc[0] if s.notna().any() else None
        sample_str = str(sample)
        if len(sample_str) > 60:
            sample_str = sample_str[:57] + "..."
        rows.append({
            "columna": c,
            "dtype": str(s.dtype),
            "nulos_%": _fmt_pct(s.isna().sum(), len(s)),
            "cardinalidad": _fmt_int(s.nunique(dropna=True)),
            "ejemplo": sample_str,
        })
    out = ["## A.1 Esquema, nulos y cardinalidad\n"]
    out.append(_md_table(pd.DataFrame(rows)))

    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    extra = [c for c in df.columns if c not in EXPECTED_COLS]
    out.append("\n\n**Diferencias contra el esquema esperado:**\n")
    out.append(f"- Columnas faltantes: {missing if missing else 'ninguna'}")
    out.append(f"- Columnas extra: {extra if extra else 'ninguna'}\n")
    return out


def _section_value_counts(df: pd.DataFrame) -> list[str]:
    out = ["## A.2 value_counts() de categoricas clave\n"]
    for col in ["pais", "company_id", "divisa", "tipo_cuenta"]:
        if col not in df.columns:
            out.append(f"\n### {col}\n_(columna no presente)_\n")
            continue
        vc = df[col].value_counts(dropna=False).head(30).reset_index()
        vc.columns = [col, "n_lineas"]
        vc["%"] = (vc["n_lineas"] / len(df) * 100).round(2)
        out.append(f"\n### {col} (top 30)\n")
        out.append(_md_table(vc))
        out.append("\n")
    return out


def _section_dates(df: pd.DataFrame) -> list[str]:
    out = ["## A.3 Rango de fechas y granularidad temporal\n"]
    if "fecha" not in df.columns:
        out.append("_(columna `fecha` no presente)_\n")
        return out
    fechas = pd.to_datetime(df["fecha"], errors="coerce")
    out.append(f"- Min fecha: **{fechas.min()}**")
    out.append(f"- Max fecha: **{fechas.max()}**")
    out.append(f"- Nulos en fecha: **{_fmt_pct(fechas.isna().sum(), len(fechas))}**\n")

    if "anio" in df.columns and "mes" in df.columns:
        anio_mes = df.groupby(["anio", "mes"]).size().reset_index(name="n_lineas")
        out.append(f"\nMeses cubiertos: **{len(anio_mes)}** combinaciones (anio, mes)\n")
        years = sorted(df["anio"].dropna().unique().tolist())
        out.append(f"\nAnios presentes: {years}\n")
        per_year = df.groupby("anio").size().reset_index(name="n_lineas")
        out.append("\n**Lineas por anio:**\n")
        out.append(_md_table(per_year))
        out.append("\n")
    return out


def _section_describe(df: pd.DataFrame) -> list[str]:
    out = ["## A.4 describe() de montos\n"]
    cols = [c for c in ["debito", "credito", "balance", "tasa_cambio"] if c in df.columns]
    if not cols:
        out.append("_(ninguna columna numerica esperada presente)_\n")
        return out
    desc = df[cols].describe().T
    desc = desc.round(2)
    out.append(_md_table(desc.reset_index().rename(columns={"index": "columna"})))
    out.append("\n")
    return out


def _section_sample(df: pd.DataFrame) -> list[str]:
    out = ["## A.5 Muestra (20 filas aleatorias)\n"]
    sample = df.sample(min(20, len(df)), random_state=42)
    out.append(_md_table(sample))
    out.append("\n")
    return out


def _section_balance_check(df: pd.DataFrame) -> list[str]:
    out = ["## A.6 Verificacion: balance == debito - credito\n"]
    if not {"balance", "debito", "credito"}.issubset(df.columns):
        out.append("_(faltan columnas para esta verificacion)_\n")
        return out
    diff = (df["balance"] - (df["debito"] - df["credito"])).abs()
    tol = 0.01
    mismatch = diff > tol
    n_bad = int(mismatch.sum())
    out.append(f"- Filas con `|balance - (debito - credito)| > {tol}`: **{_fmt_int(n_bad)}** ({_fmt_pct(n_bad, len(df))})\n")
    if n_bad:
        ejemplos = df.loc[mismatch, ["fecha", "codigo_cuenta", "debito", "credito", "balance"]].head(10)
        out.append("\n**Ejemplos de filas que NO cumplen:**\n")
        out.append(_md_table(ejemplos))
        out.append("\n")
    return out


def _section_granularity(df: pd.DataFrame) -> list[str]:
    out = ["## B. Granularidad (transaccional vs agregada)\n"]
    if "asiento_contable" not in df.columns:
        out.append("_(columna `asiento_contable` no presente)_\n")
        return out
    n_asientos = df["asiento_contable"].nunique(dropna=True)
    lineas_por_asiento = df.groupby("asiento_contable").size()
    out.append(f"- Asientos distintos: **{_fmt_int(n_asientos)}**")
    out.append(f"- Lineas totales: **{_fmt_int(len(df))}**")
    out.append(f"- Lineas/asiento — promedio: **{lineas_por_asiento.mean():.2f}**, "
               f"mediana: **{lineas_por_asiento.median():.0f}**, "
               f"max: **{int(lineas_por_asiento.max())}**\n")
    dist = lineas_por_asiento.describe().round(2).reset_index()
    dist.columns = ["estadistico", "valor"]
    out.append("\n**Distribucion de lineas por asiento:**\n")
    out.append(_md_table(dist))
    out.append("\n\n**Conclusion:** la granularidad es **transaccional** "
               "(multiples lineas por asiento).\n")
    return out


def _section_account_coverage(df: pd.DataFrame, formulas: dict[str, Any]) -> list[str]:
    out = ["## C. Cobertura de codigos contables (P&L y Balance)\n"]
    if "codigo_cuenta" not in df.columns:
        out.append("_(columna `codigo_cuenta` no presente)_\n")
        return out
    if not formulas:
        out.append("_(no se encontraron JSON en data_pipeline/formulas/)_\n")
        return out

    codigos_set = set(df["codigo_cuenta"].dropna().astype(str).unique())
    out.append(f"- Codigos distintos en el parquet: **{_fmt_int(len(codigos_set))}**\n")

    for fname, payload in formulas.items():
        out.append(f"\n### Origen: `{fname}`\n")

        per_formula_rows = []
        all_patterns: set[str] = set()
        all_miss_patterns: set[str] = set()
        formulas_using_account_type: list[tuple[str, str]] = []

        for kpi_key, concepto, formula in _iter_formula_nodes(payload):
            patterns = _extract_codes_from_formula(formula)
            all_patterns |= patterns
            uses_type = _formula_uses_account_type(formula)
            if uses_type:
                formulas_using_account_type.append((kpi_key, concepto))

            if not patterns and not uses_type:
                continue

            n_pat = len(patterns)
            n_pat_ok = 0
            n_pat_miss = 0
            n_codigos_total = 0
            miss_examples: list[str] = []
            for pat in sorted(patterns):
                rgx = _like_to_regex(pat)
                matches = [c for c in codigos_set if rgx.match(c)]
                n_codigos_total += len(matches)
                if matches:
                    n_pat_ok += 1
                else:
                    n_pat_miss += 1
                    miss_examples.append(pat)
                    all_miss_patterns.add(pat)

            per_formula_rows.append({
                "kpi": kpi_key,
                "concepto": concepto[:55],
                "usa_account_type": "SI" if uses_type else "",
                "n_patrones": n_pat,
                "patrones_OK": n_pat_ok,
                "patrones_FALTAN": n_pat_miss,
                "n_codigos_match": n_codigos_total,
                "patrones_faltantes": ", ".join(miss_examples[:6]) + ("..." if len(miss_examples) > 6 else ""),
            })

        if not per_formula_rows:
            out.append("- _No se detectaron formulas con patrones de codigo en este JSON._\n")
            continue

        out.append(f"- Total de patrones distintos referidos: **{_fmt_int(len(all_patterns))}**")
        out.append(f"- Patrones distintos SIN match en parquet: **{_fmt_int(len(all_miss_patterns))}**\n")

        out.append("\n**Cobertura por KPI/formula:**\n")
        out.append(_md_table(pd.DataFrame(per_formula_rows)))
        out.append("\n")

        if all_miss_patterns:
            out.append("\n**Patrones que NO encontraron ningun codigo (union):**\n")
            for p in sorted(all_miss_patterns):
                out.append(f"- `{p}`")
            out.append("\n")

        if formulas_using_account_type:
            out.append("\n**ATENCION — formulas que usan `account_id.account_type`** "
                       "(la columna `tipo_cuenta` NO esta en el parquet; estas formulas no se pueden calcular tal cual):\n")
            for k, c in formulas_using_account_type:
                out.append(f"- `{k}` — {c}")
            out.append("\n")
    return out


def _section_analytic_coverage(df: pd.DataFrame, formulas: dict[str, Any]) -> list[str]:
    out = ["## D. Cobertura de cuenta analitica (critico para EBITDA)\n"]
    if "id_cuenta_analitica" not in df.columns:
        out.append("_(columna `id_cuenta_analitica` no presente)_\n")
        return out

    # En este parquet, "sin analitica" se codifica como NaN o como 0.
    ana = df["id_cuenta_analitica"]
    sin_analitica = ana.isna() | (ana == 0)

    out.append("> **Nota:** se trata `id_cuenta_analitica` como **vacia** cuando es NaN o **igual a 0** "
               "(en el parquet, 0 funciona como sentinel de 'sin cuenta analitica asignada').\n")

    # 1) "Nulos" (NaN | 0) de id_cuenta_analitica, segmentado por cuentas 6/7 vs resto.
    if "codigo_cuenta" in df.columns:
        cc = df["codigo_cuenta"].astype(str)
        es_gasto = cc.str.startswith(("6", "7"))
        gasto_mask = es_gasto
        resto_mask = ~es_gasto

        sin_g = int((sin_analitica & gasto_mask).sum())
        sin_r = int((sin_analitica & resto_mask).sum())
        n_g = int(gasto_mask.sum())
        n_r = int(resto_mask.sum())

        out.append("### D.1 Lineas SIN analitica (NaN o 0) por familia de cuenta\n")
        tabla = pd.DataFrame([
            {
                "familia": "cuentas 6/7 (gasto — debe tener analitica)",
                "n_lineas": _fmt_int(n_g),
                "sin_analitica (NaN o 0)": _fmt_int(sin_g),
                "%_sin_analitica": _fmt_pct(sin_g, n_g),
            },
            {
                "familia": "resto (1/2/3/4/5/8/9 — balance/saldos iniciales; vacio es normal)",
                "n_lineas": _fmt_int(n_r),
                "sin_analitica (NaN o 0)": _fmt_int(sin_r),
                "%_sin_analitica": _fmt_pct(sin_r, n_r),
            },
        ])
        out.append(_md_table(tabla))
        out.append("\n")

    # 2) IDs analiticos referidos por los JSON vs los presentes en el parquet.
    ids_presentes_raw = ana[~sin_analitica]
    ids_presentes: set[int] = set()
    for v in ids_presentes_raw.unique():
        try:
            iv = int(v)
            if iv != 0:
                ids_presentes.add(iv)
        except (TypeError, ValueError):
            pass
    out.append(f"- IDs analiticos distintos en el parquet (excluye NaN/0): **{_fmt_int(len(ids_presentes))}**\n")

    if not formulas:
        out.append("_(no hay JSON de formulas cargados)_\n")
        return out

    for fname, payload in formulas.items():
        out.append(f"\n### Origen: `{fname}`\n")

        per_formula_rows = []
        all_ids: set[int] = set()
        for kpi_key, concepto, formula in _iter_formula_nodes(payload):
            ids = _extract_analytic_ids_from_formula(formula)
            if not ids:
                continue
            all_ids |= ids
            present_here = sorted(ids & ids_presentes)
            missing_here = sorted(ids - ids_presentes)
            per_formula_rows.append({
                "kpi": kpi_key,
                "concepto": concepto[:55],
                "ids_referidos": sorted(ids),
                "presentes": present_here,
                "FALTAN": missing_here if missing_here else "",
            })

        if not per_formula_rows:
            out.append("- _Este JSON no contiene filtros `analytic_account_id_ika in [...]` en sus formulas._\n")
            continue

        missing_total = sorted(all_ids - ids_presentes)
        present_total = sorted(all_ids & ids_presentes)
        out.append(f"- IDs analiticos distintos referidos por las formulas: **{_fmt_int(len(all_ids))}**")
        out.append(f"- Presentes en el parquet: **{_fmt_int(len(present_total))}**")
        out.append(f"- FALTAN en el parquet: **{_fmt_int(len(missing_total))}**\n")
        if missing_total:
            out.append(f"\n**IDs analiticos referidos que NO existen en el parquet:** `{missing_total}`\n")

        out.append("\n**Detalle por KPI:**\n")
        out.append(_md_table(pd.DataFrame(per_formula_rows)))
        out.append("\n")

    return out


def _section_entities_mexico(df: pd.DataFrame) -> list[str]:
    out = ["## E. Entidades por company_id (Mexico legacy vs actual)\n"]
    if "company_id" not in df.columns:
        out.append("_(columna `company_id` no presente)_\n")
        return out
    cols = ["company_id"]
    if "company_name" in df.columns:
        cols.append("company_name")
    if "pais" in df.columns:
        cols.append("pais")
    grp = df.groupby(cols, dropna=False).agg(
        n_lineas=("company_id", "size"),
        fecha_min=("fecha", "min") if "fecha" in df.columns else ("company_id", "size"),
        fecha_max=("fecha", "max") if "fecha" in df.columns else ("company_id", "size"),
    ).reset_index()
    out.append(_md_table(grp))
    out.append("\n\n_Documental: existen company_id 39 (...-2022, legacy pre-2022) y company_id 1 (actual 2022+). "
               "El merge/dedup queda para una fase posterior._\n")
    return out


def _section_fx(df: pd.DataFrame) -> list[str]:
    out = ["## F. Tasa de cambio (pendientes para consolidacion USD)\n"]
    if "tasa_cambio" not in df.columns:
        out.append("_(columna `tasa_cambio` no presente)_\n")
        return out
    out.append(f"- Nulos totales en `tasa_cambio`: **{_fmt_pct(df['tasa_cambio'].isna().sum(), len(df))}**\n")
    if "anio" in df.columns:
        per_year = df.groupby("anio")["tasa_cambio"].agg(
            n_lineas="size",
            nulos=lambda s: int(s.isna().sum()),
        ).reset_index()
        per_year["%_nulos"] = (per_year["nulos"] / per_year["n_lineas"] * 100).round(2)
        out.append("**Nulos por anio:**\n")
        out.append(_md_table(per_year))
        out.append("\n")

    if "divisa" in df.columns:
        ej = (df.dropna(subset=["tasa_cambio"])
                .groupby("divisa")["tasa_cambio"]
                .agg(["min", "max", "mean", "count"])
                .round(4)
                .reset_index())
        out.append("\n**Tasa de cambio por divisa (sin nulos):**\n")
        out.append(_md_table(ej))
        out.append("\n")

    out.append("\n### PENDIENTES PARA CONSOLIDACION USD\n")
    out.append("- Definir tasa autoritaria por (anio, mes, divisa) — ¿la que viene en el parquet o una tabla externa?\n")
    out.append("- Confirmar con Ikatech si las lineas con `tasa_cambio` NaN son intencionales (USD nativo) o un hueco.\n")
    out.append("- Decidir politica para apuntes pre-2022 (legacy company_id 39): ¿re-expresar a USD historico o usar tipo de cambio actual?\n")
    return out


# ---------- main -------------------------------------------------------------

def main() -> None:
    df, pq_path = _load_df()
    formulas = _load_formula_jsons()

    parts: list[str] = []
    parts.extend(_section_header(df, pq_path))
    parts.extend(_section_schema(df))
    parts.extend(_section_value_counts(df))
    parts.extend(_section_dates(df))
    parts.extend(_section_describe(df))
    parts.extend(_section_sample(df))
    parts.extend(_section_balance_check(df))
    parts.extend(_section_granularity(df))
    parts.extend(_section_account_coverage(df, formulas))
    parts.extend(_section_analytic_coverage(df, formulas))
    parts.extend(_section_entities_mexico(df))
    parts.extend(_section_fx(df))

    REPORT_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"\n[OK] Reporte escrito en {REPORT_PATH}")


if __name__ == "__main__":
    main()
