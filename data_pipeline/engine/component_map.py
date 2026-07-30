"""
component_map.py · Capa lógica del mapeo componente -> columna de vista.

Consume el JSON generado por 16_component_map.py (fuente de verdad, literal del
contrato) y expone las REGLAS del BR que la Fase 3 aplica al poblar el tablero:

  - Regla de admisión: un componente sin su columna devuelve VACÍO, nunca 0.
  - Tasa efectiva del ROIC con guarda de cordura 0%-60%.
  - Derivación de AGA30 (EBITDA %) = ebitda / total_ingreso.
  - Regla del último mes cerrado (no el MAX(mes) crudo).

Todas las funciones son puras y no tocan I/O salvo load_map(), para que el
constructor del payload y las pruebas las llamen sin efectos colaterales.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_MAP_PATH = Path(__file__).resolve().parent.parent / "formulas" / "component_view_map.json"

# ---- Constantes de reglas (definición aquí; aplicación en Fase 3) ----

# Guarda de cordura del ROIC: si la tasa efectiva cae fuera de este rango, el
# componente 7 devuelve vacío. La cuenta 72002001 (Otros Impuestos) tiene un
# problema conocido de tasa_cambio que puede inflar la bolsa AGA54 varios órdenes
# de magnitud; sin esta guarda, t se dispara, NOPAT sale negativo y el ROIC se
# vuelve absurdo sin marcar error.
TAX_RATE_GUARD = (0.0, 0.60)

# AGA30 (EBITDA %) no viene en la vista de P&L: se deriva en el front.
AGA30_NUM, AGA30_DEN = "ebitda", "total_ingreso"

# Columna de la vista de P&L que alimenta la tasa efectiva (código AGA54).
# Verificado contra el extracto real: AUSENTE en calcs_202607271131.csv -> el
# componente 7 no es calculable hasta que la vista la exponga.
TAX_COLUMN = "impuestos"


@lru_cache(maxsize=1)
def load_map() -> dict:
    return json.loads(_MAP_PATH.read_text(encoding="utf-8"))


def components() -> list[dict]:
    return load_map()["components"]


def component(num: int) -> dict | None:
    return next((c for c in components() if c["num"] == num), None)


def required_columns(num: int, view: str | None = None) -> list[str]:
    """Columnas concretas (no derivadas, no FALTA) que un componente necesita.
    Filtra opcionalmente por vista ('pl' | 'bg')."""
    comp = component(num)
    if not comp:
        return []
    cols: list[str] = []
    for it in comp["items"]:
        if it["missing"]:
            continue
        if view and it["view"] != view:
            continue
        cols.extend(it["columns"])
    # únicos, preservando orden
    seen: set[str] = set()
    return [c for c in cols if not (c in seen or seen.add(c))]


def resolve(num: int, available: set[str]) -> dict:
    """Regla de admisión del BR.

    Dado el conjunto de columnas disponibles en la(s) vista(s), decide si el
    componente es poblable. Devuelve:
      {ok: bool, missing: [cols ausentes], columns: [cols requeridas]}
    ok=False => el front debe pintar VACÍO (nunca 0, nunca estimado, nunca
    heredado del mes anterior).
    """
    req = required_columns(num)
    missing = [c for c in req if c not in available]
    return {"ok": not missing, "missing": missing, "columns": req}


def effective_tax_rate(impuestos: float | None, resultado_neto: float | None) -> tuple[float | None, str]:
    """t = impuestos / (resultado_neto + impuestos), con guarda 0%-60%.

    Devuelve (t, motivo). Si no es calculable o cae fuera de rango, t=None y el
    motivo explica por qué (para registrar y NO publicar un ROIC absurdo).
    """
    if impuestos is None:
        return None, f"columna '{TAX_COLUMN}' (AGA54) ausente en la vista de P&L"
    if resultado_neto is None:
        return None, "resultado_neto (AGA56) ausente"
    denom = resultado_neto + impuestos
    if denom == 0:
        return None, "denominador (resultado_neto + impuestos) = 0"
    t = impuestos / denom
    lo, hi = TAX_RATE_GUARD
    if not (lo <= t <= hi):
        return None, f"tasa efectiva {t:.1%} fuera de rango [{lo:.0%}, {hi:.0%}] (posible tasa_cambio de 72002001)"
    return t, "ok"


def nopat(ebit: float | None, impuestos: float | None, resultado_neto: float | None) -> tuple[float | None, str]:
    """NOPAT = ebit * (1 - t). Vacío si la tasa no pasa la guarda o falta ebit."""
    if ebit is None:
        return None, "ebit (AGA46) ausente"
    t, reason = effective_tax_rate(impuestos, resultado_neto)
    if t is None:
        return None, reason
    return ebit * (1 - t), "ok"


def classify_periods(periods: list[tuple[int, int]]) -> dict[tuple[int, int], bool]:
    """Marca qué (anio, mes) es PRELIMINAR.

    Regla: el mes más reciente presente es preliminar (sus devengos aún no se
    postean por completo); se vuelve cerrado cuando el pipeline añade el mes
    siguiente. Es determinista, no depende del reloj, y NO es el MAX(mes) al azar:
    explícitamente marca el último y deja como cerrado el penúltimo.

    Convención de reporte financiero: la cifra titular es el último mes CERRADO;
    el mes en curso se muestra pero badge-ado como preliminar.
    """
    if not periods:
        return {}
    order = sorted(set(periods))
    newest = order[-1]
    return {p: (p == newest) for p in order}


def last_closed_period(periods: list[tuple[int, int]]) -> tuple[int, int] | None:
    """Último mes CERRADO = el más reciente que NO es preliminar. None si no hay."""
    flags = classify_periods(periods)
    closed = [p for p, prelim in flags.items() if not prelim]
    return max(closed) if closed else None
