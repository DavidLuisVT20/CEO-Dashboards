"""
17_build_finanzas_payload_vista.py · Ingesta CSV -> payload del tablero.

Fuente: extracto de la vista de P&L (CSV local). La LÓGICA de ensamblado vive en
engine/payload_builder (compartida con el futuro adaptador de runtime que leerá la
vista directo); aquí solo leemos el CSV y escribimos el JSON.

Salida: data_pipeline/output/finanzas_payload.json (GITIGNORED — cifras reales).

Uso:
    python 17_build_finanzas_payload_vista.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine.payload_builder import build_payload  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PL_EXTRACT = ROOT / "calcs_202607271131.csv"
OUT = Path(__file__).resolve().parent / "output" / "finanzas_payload.json"


def main() -> None:
    if not PL_EXTRACT.exists():
        raise SystemExit(f"Falta el extracto de P&L: {PL_EXTRACT.name}")
    with PL_EXTRACT.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    header = list(rows[0].keys()) if rows else []

    data = build_payload(rows, header, generado_de=PL_EXTRACT.name)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    m = data["meta"]
    print(f"[OK] {OUT.relative_to(ROOT)}")
    print(f"     {len(data['records'])} registros · grano {m['grano']} · closed {m['closed_period']}")
    print(f"     codigos: {m['codigos_incluidos']} · derivadas {list(m['medidas_derivadas'])}")
    print(f"     faltantes P&L: {m['codigos_faltantes_pl']} · divisa {m['divisa']}")
    if m["closed_period"]:
        cp = (m["closed_period"]["anio"], m["closed_period"]["mes"])
        me = next(r for r in data["records"] if (r["anio"], r["mes"]) == cp)["measures"]
        cierre = me["AGA4"] - me["COSTOS_TOT_OP"] - me["AGA25"]
        print(f"     [check cascada {cp}] Ing {me['AGA4']:,.2f} - CostosTot {me['COSTOS_TOT_OP']:,.2f}"
              f" - G&A {me['AGA25']:,.2f} = {cierre:,.2f} (EBITDA {me['AGA29']:,.2f})")


if __name__ == "__main__":
    main()
