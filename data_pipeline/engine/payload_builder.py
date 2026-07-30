"""
payload_builder.py · Ensambla el payload del tablero a partir de filas de la
vista de P&L, INDEPENDIENTE de la fuente (CSV local hoy; vista/S3 mañana).

Por qué vive aquí y no en el script de ingesta: el adaptador de runtime (Fase 2,
lectura directa de la vista) reutiliza build_payload() tal cual, sin duplicar la
lógica. Mapeo columna->código, medidas derivadas, grano, regla de mes cerrado y
motivos de vacío viven en esta capa + en component_map, no en el ingestor.
"""

from __future__ import annotations

from . import component_map as cm

# Compañía sintética mientras el extracto de P&L no traiga la dimensión de compañía.
SYN_COMPANY_ID = "CONSOLIDADO"
SYN_COMPANY_NAME = "Addiuva Territorial (consolidado)"

# Motivos legibles para las tarjetas que no se pueden poblar todavía (van a la
# tarjeta, no solo a consola).
EMPTY_COMPONENTS = {
    "5": "Sin extracto de la vista de Balance. Tarjeta cableada, a la espera del dato.",
    "6": "FCF necesita 2 cierres consecutivos; la vista de Balance no expone periodo (solo fecha_generacion).",
    "7": "ROIC necesita 'impuestos' (ausente en el extracto de P&L) y 13 cierres de Balance con periodo.",
}


def pl_code_to_column() -> dict[str, str]:
    """Inverso del mapeo para P&L: código Odoo -> columna EXACTA de la vista.
    Solo ítems 'pl', no derivados, no FALTA, de una sola columna."""
    out: dict[str, str] = {}
    for comp in cm.components():
        for it in comp["items"]:
            if it["view"] != "pl" or it["missing"] or len(it["columns"]) != 1:
                continue
            out[it["code"]] = it["columns"][0]
    return out


def _fnum(s) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def build_payload(rows: list[dict], header, *, generado_de: str | None = None) -> dict:
    """Ensambla el payload (meta + records) a grano (company_id, anio, mes).

    Args:
        rows:   filas de la vista de P&L (una por periodo/compañía), dict-like.
        header: columnas disponibles en la fuente (para la regla de admisión).
        generado_de: etiqueta informativa de la fuente.

    El consolidado NO se calcula aquí: se emite el grano y el front agrega. Las
    medidas derivadas (p.ej. COSTOS_TOT_OP) salen de la capa de mapeo.
    """
    header = set(header)
    code_col = pl_code_to_column()
    usable = {c: col for c, col in code_col.items() if col in header}

    divisas = sorted({r["divisa"] for r in rows if r.get("divisa")})
    periods = sorted({(int(r["anio"]), int(r["mes"])) for r in rows})
    prelim = cm.classify_periods(periods)
    closed = cm.last_closed_period(periods)

    records = []
    for r in rows:
        anio, mes = int(r["anio"]), int(r["mes"])
        measures = {code: _fnum(r[col]) for code, col in usable.items()}
        # Medidas derivadas (definición autoritativa en component_map).
        for code in cm.DERIVED_MEASURES:
            v = cm.derived_value(code, lambda c: _fnum(r[c]) if c in header else None)
            if v is not None:
                measures[code] = v
        records.append({
            "company_id": SYN_COMPANY_ID,
            "company_name": SYN_COMPANY_NAME,
            "pais": None,
            "anio": anio,
            "mes": mes,
            "divisa": r.get("divisa"),
            "preliminar": bool(prelim.get((anio, mes), False)),
            "measures": measures,
        })

    return {
        "meta": {
            "generado_de": generado_de,
            "arquitectura": "vista P&L (KPIs resueltos en backend)",
            "grano": ["company_id", "anio", "mes"],
            "scope_label": "Consolidado · Sociedades territoriales Addiuva",
            "closed_period": ({"anio": closed[0], "mes": closed[1]} if closed else None),
            "ratio_codes": ["AGA30"],  # se recalculan sobre agregados, no se suman
            "aga30_derive": {"num": cm.AGA30_NUM, "den": cm.AGA30_DEN},
            "medidas_derivadas": {k: v["columns"] for k, v in cm.DERIVED_MEASURES.items()},
            "divisa": {"values": divisas, "mixed": len(divisas) > 1},
            "companies": [
                {"company_id": SYN_COMPANY_ID, "company_name": SYN_COMPANY_NAME, "pais": None}
            ],
            "empty_components": EMPTY_COMPONENTS,
            "codigos_incluidos": sorted(usable.keys()),
            "codigos_faltantes_pl": sorted(set(code_col) - set(usable)),
        },
        "records": records,
    }
