"""
17_build_finanzas_payload_vista.py · Construye el payload del tablero desde la
VISTA de P&L (arquitectura nueva: KPIs resueltos en el backend).

Grano de salida: (company_id, anio, mes). El CONSOLIDADO es una agregación sobre
ese grano en el front, no un camino aparte. Mientras el extracto no traiga
compañía, se emite UNA compañía sintética; cuando la vista exponga
company_id/pais/company_name (junto con 'impuestos'), este mismo script produce
N compañías sin cambiar la ruta de agregación del front.

Reglas (capa de mapeo, engine/component_map):
  - Nombres de columna LITERALES del contrato (typos incluidos).
  - Componente sin su columna -> vacío con motivo (nunca 0). Comps 5/6/7 salen
    vacíos: la vista de Balance no expone periodo (solo fecha_generacion) e
    'impuestos' (AGA54) falta en el extracto de P&L.
  - Último mes cerrado = penúltimo periodo (el más reciente es preliminar).

Salida: data_pipeline/output/finanzas_payload.json  (GITIGNORED — cifras reales).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import component_map as cm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PL_EXTRACT = ROOT / "calcs_202607271131.csv"
OUT = Path(__file__).resolve().parent / "output" / "finanzas_payload.json"

# Compañía sintética mientras el extracto de P&L no traiga la dimensión.
SYN_COMPANY_ID = "CONSOLIDADO"
SYN_COMPANY_NAME = "Addiuva Territorial (consolidado)"

# Costos Totales de Operación (tarjeta nueva del contrato — opción C). La vista
# expone estos rubros pero el contrato no los cardeaba por separado; su suma es la
# base de costo que EBITDA ya neteó, y hace que la cascada cierre en pantalla:
#   Ingresos − Costos Totales − G&A = EBITDA
# Es aditiva (suma de flujos) -> agrega entre compañías como cualquier medida.
# Nombres LITERALES de columna, typos incluidos.
COSTOS_TOT_OP_COLS = [
    "costo_directo_de_operaciones",
    "otros_costos_de_operaciones",
    "costo_directo_de_comercializacion",
    "comisiones_brokers",
    "costo_indirecto_operacion",
]


def _pl_code_to_column() -> dict[str, str]:
    """Inverso del mapeo para P&L: código Odoo -> nombre EXACTO de columna.
    Solo ítems de vista 'pl', no derivados, no FALTA, y una sola columna."""
    out: dict[str, str] = {}
    for comp in cm.components():
        for it in comp["items"]:
            if it["view"] != "pl" or it["missing"] or len(it["columns"]) != 1:
                continue
            out[it["code"]] = it["columns"][0]
    return out


def _fnum(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def build() -> dict:
    if not PL_EXTRACT.exists():
        raise SystemExit(f"Falta el extracto de P&L: {PL_EXTRACT.name}")

    with PL_EXTRACT.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    header = set(rows[0].keys()) if rows else set()

    code_col = _pl_code_to_column()
    # solo códigos cuya columna EXISTE en este extracto (admisión por columna)
    usable = {code: col for code, col in code_col.items() if col in header}

    # divisa: ¿única o mezclada? (si mezclada, sumar entre compañías es inválido)
    divisas = sorted({r["divisa"] for r in rows if r.get("divisa")})
    divisa_mixed = len(divisas) > 1

    periods = sorted({(int(r["anio"]), int(r["mes"])) for r in rows})
    prelim = cm.classify_periods(periods)           # {(anio,mes): bool}
    closed = cm.last_closed_period(periods)          # (anio, mes) | None

    ct_cols_ok = [c for c in COSTOS_TOT_OP_COLS if c in header]

    records = []
    for r in rows:
        anio, mes = int(r["anio"]), int(r["mes"])
        measures = {code: _fnum(r[col]) for code, col in usable.items()}
        # Costos Totales de Operación (derivado). Solo si TODOS sus rubros están
        # (regla de admisión: sin una columna -> sin la tarjeta, nunca parcial).
        ct_parts = [_fnum(r[c]) for c in ct_cols_ok]
        if len(ct_cols_ok) == len(COSTOS_TOT_OP_COLS) and all(p is not None for p in ct_parts):
            measures["COSTOS_TOT_OP"] = sum(ct_parts)
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

    empty_components = {
        "5": "Sin extracto de la vista de Balance. Tarjeta cableada, a la espera del dato.",
        "6": "FCF necesita 2 cierres consecutivos; la vista de Balance no expone periodo (solo fecha_generacion).",
        "7": "ROIC necesita 'impuestos' (ausente en el extracto de P&L) y 13 cierres de Balance con periodo.",
    }

    return {
        "meta": {
            "generado_de": PL_EXTRACT.name,
            "arquitectura": "vista P&L (KPIs resueltos en backend)",
            "grano": ["company_id", "anio", "mes"],
            "scope_label": "Consolidado · Sociedades territoriales Addiuva",
            "closed_period": ({"anio": closed[0], "mes": closed[1]} if closed else None),
            "ratio_codes": ["AGA30"],   # se recalculan sobre agregados, no se suman
            "aga30_derive": {"num": cm.AGA30_NUM, "den": cm.AGA30_DEN},
            "medidas_derivadas": {"COSTOS_TOT_OP": COSTOS_TOT_OP_COLS},
            "divisa": {"values": divisas, "mixed": divisa_mixed},
            "companies": [
                {"company_id": SYN_COMPANY_ID, "company_name": SYN_COMPANY_NAME, "pais": None}
            ],
            "empty_components": empty_components,
            "codigos_incluidos": sorted(usable.keys()),
            "codigos_faltantes_pl": sorted(set(code_col) - set(usable)),
        },
        "records": records,
    }


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    m = data["meta"]
    print(f"[OK] {OUT.relative_to(ROOT)}")
    print(f"     {len(data['records'])} registros · grano {m['grano']}")
    print(f"     divisa={m['divisa']} · closed={m['closed_period']}")
    print(f"     codigos incluidos: {m['codigos_incluidos']}")
    print(f"     faltantes en P&L: {m['codigos_faltantes_pl']}")

    # --- Sanity: el consolidado del mes cerrado debe igualar el extracto crudo ---
    if m["closed_period"]:
        cp = (m["closed_period"]["anio"], m["closed_period"]["mes"])
        rec = next(r for r in data["records"] if (r["anio"], r["mes"]) == cp)
        eb, ing = rec["measures"].get("AGA29"), rec["measures"].get("AGA4")
        pct = (eb / ing * 100) if (eb is not None and ing) else None
        print(f"     [check] cierre {cp}: EBITDA={eb:,.2f} Ingresos={ing:,.2f} "
              f"EBITDA%={pct:.2f}%")


if __name__ == "__main__":
    main()
