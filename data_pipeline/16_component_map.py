"""
16_component_map.py · Generador de la CAPA DE MAPEO componente -> columna de vista.

Lee el contrato del tablero (Excel de Nelson, LOCAL y gitignored) y emite un JSON
committeable en formulas/component_view_map.json. Ese JSON es la ÚNICA fuente de
verdad que traduce cada código Odoo al nombre EXACTO de columna en las vistas del
warehouse — con sus typos incluidos, porque el esquema es de ellos.

Por qué generar y no transcribir a mano: cualquier typo mal copiado
(ebitda_con_extraorinarios, gasto_generales_de_adminstracion_y_ventas, ...) rompería
el mapeo en silencio. Generándolo desde el contrato, el nombre es literal por
construcción.

El .xlsx NO se versiona (expone la estructura contable del grupo en un repo público);
el JSON derivado sí, igual que los diccionarios de fórmulas ya versionados.

Uso:
    python 16_component_map.py            # regenera el JSON desde el contrato local
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_XLSX = ROOT / "Componentes_Tablero_Finanzas_Addiuva_BR-CEO-KPI-001.xlsx"
SHEET = "Componentes Addiuva"
OUT_JSON = Path(__file__).resolve().parent / "formulas" / "component_view_map.json"
PL_EXTRACT = ROOT / "calcs_202607271131.csv"  # extracto de la vista de P&L (local)

# Encabezado de la hoja (fila 4 en Excel = índice 3): columnas por letra.
COL_NUM, COL_COMP, COL_CONCEPTO, COL_CODIGO, COL_VARIABLE, COL_ESTADO = 0, 1, 5, 6, 7, 9
HEADER_ROW = 3
FIRST_DATA_ROW = 4


def _clean(v) -> str:
    return "" if v is None else str(v).strip()


def _classify_view(code: str) -> str:
    """AGA* -> P&L; A<dígito>* -> Balance General. Códigos combinados con '/'
    comparten vista, así que basta el primero."""
    first = code.split("/")[0].strip()
    return "pl" if first.upper().startswith("AGA") else "bg"


def _parse_variable(raw: str) -> dict:
    """Traduce la celda 'Variable en vista (Nelson)' a columnas concretas.

    Reglas de admisión del contrato:
      - 'FALTA...' / 'no aplica...'  -> sin columna (missing=True). Si dice
        'derivar: <expr>', se captura la expresión (p.ej. AGA30).
      - varias columnas separadas por '·' -> lista (p.ej. Caja y equivalentes).
      - cualquier otra cosa -> una sola columna, LITERAL (typos incluidos).
    """
    text = raw.strip()
    low = text.lower()
    if low.startswith("falta") or low.startswith("no aplica"):
        derive = None
        m = re.search(r"derivar\s*:\s*(.+)$", text, flags=re.IGNORECASE)
        if m:
            derive = m.group(1).strip()
        return {"columns": [], "missing": True, "derive": derive}
    if "·" in text:
        cols = [c.strip() for c in text.split("·") if c.strip()]
        return {"columns": cols, "missing": False, "derive": None}
    return {"columns": [text], "missing": False, "derive": None}


def _pl_extract_cols() -> set[str] | None:
    if not PL_EXTRACT.exists():
        return None
    import csv

    with PL_EXTRACT.open(newline="", encoding="utf-8") as f:
        return set(next(csv.reader(f)))


def build() -> dict:
    if not CONTRACT_XLSX.exists():
        raise SystemExit(
            f"No encuentro el contrato: {CONTRACT_XLSX.name}. Cópialo a la raíz del repo."
        )
    wb = openpyxl.load_workbook(CONTRACT_XLSX, data_only=True)
    ws = wb[SHEET]
    rows = list(ws.iter_rows(values_only=True))

    pl_cols = _pl_extract_cols()

    components: list[dict] = []
    notes: list[str] = []
    current: dict | None = None

    for i in range(FIRST_DATA_ROW, len(rows)):
        r = rows[i]
        col0 = _clean(r[COL_NUM] if len(r) > COL_NUM else None)
        comp = _clean(r[COL_COMP] if len(r) > COL_COMP else None)
        concepto = _clean(r[COL_CONCEPTO] if len(r) > COL_CONCEPTO else None)
        codigo = _clean(r[COL_CODIGO] if len(r) > COL_CODIGO else None)
        variable = _clean(r[COL_VARIABLE] if len(r) > COL_VARIABLE else None)
        estado = _clean(r[COL_ESTADO] if len(r) > COL_ESTADO else None)
        is_num = col0.isdigit()
        num = col0 if is_num else ""

        # Notas al pie: van en celdas combinadas (A106:K106, A108:K108), así que el
        # texto cae en la columna A y no es un número de componente.
        if col0 and not is_num and not comp and not codigo:
            notes.append(col0)
            continue

        # Encabezado de componente: número + nombre, sin código.
        if num and comp and not codigo:
            current = {"num": int(num), "name": comp, "estado": estado, "items": []}
            components.append(current)
            continue

        # Fila de ítem: tiene código.
        if codigo and current is not None:
            view = _classify_view(codigo)
            parsed = _parse_variable(variable)
            item = {
                "code": codigo,
                "concepto": concepto,
                "view": view,
                "columns": parsed["columns"],
                "missing": parsed["missing"],
                "derive": parsed["derive"],
                "estado": estado,
            }
            # Verificación de presencia solo para P&L (tenemos su extracto). Para
            # Balance no hay extracto en mano -> None (desconocido).
            if view == "pl" and pl_cols is not None and not parsed["missing"]:
                item["present_in_extract"] = {c: (c in pl_cols) for c in parsed["columns"]}
            else:
                item["present_in_extract"] = None
            current["items"].append(item)

    return {
        "meta": {
            "source": CONTRACT_XLSX.name,
            "sheet": SHEET,
            "scope": "Addiuva · sociedades territoriales (excl. Voccare/Ikatech)",
            "note": (
                "Nombres de columna LITERALES de las vistas de Nelson, typos incluidos. "
                "Regla de admisión: componente sin su columna -> vacío, nunca 0."
            ),
            "pl_extract": PL_EXTRACT.name if pl_cols is not None else None,
            "pl_extract_cols": sorted(pl_cols) if pl_cols else None,
            "footnotes": notes,
        },
        "components": components,
    }


def main() -> None:
    data = build()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    n_items = sum(len(c["items"]) for c in data["components"])
    print(f"[OK] {OUT_JSON.relative_to(ROOT)}")
    print(f"     {len(data['components'])} componentes · {n_items} ítems")
    # Resumen de admisión P&L (lo que podemos verificar ya).
    missing = []
    for c in data["components"]:
        for it in c["items"]:
            pres = it.get("present_in_extract")
            if pres and not all(pres.values()):
                ausentes = [k for k, v in pres.items() if not v]
                missing.append(f"comp {c['num']} · {it['code']} -> {ausentes}")
    if missing:
        print("[AVISO] columnas del contrato AUSENTES en el extracto P&L:")
        for m in missing:
            print("   ", m)


if __name__ == "__main__":
    main()
