"""
07_compare_dicts.py
-------------------
TAREA 1 (gate): compara los diccionarios Odoo .py (Diccionarios/Odoo/) contra
los JSON que usa el motor (data_pipeline/formulas/). Diff exacto campo por campo.

Salida: imprime a consola. Si hay diferencias, las lista para decidir.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ODOO_DIR = Path(r"C:\Users\Luis David\Documents\GitHub\Addiuva\Diccionarios\Odoo")
PYL_PY = ODOO_DIR / "diccionario_odoo_pyl_addiuva_enterprises_mexico.py"
BAL_PY = ODOO_DIR / "diccionario_odoo_balance_addiuva_enterprises_mexico.py"
PYL_JSON = HERE / "formulas" / "P&L-2026.json"
BAL_JSON = HERE / "formulas" / "Balance-General-2026.json"

FIELDS = ["concepto", "nivel", "motor", "subformula", "formula"]


def load_py_dict(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # buscar la primera variable que sea un dict grande
    candidates = {k: v for k, v in vars(mod).items()
                  if isinstance(v, dict) and not k.startswith("__")}
    if not candidates:
        raise SystemExit(f"No encontre dict en {path}")
    # el dict de formulas (el mas grande)
    name = max(candidates, key=lambda k: len(candidates[k]))
    return name, candidates[name]


import ast


def _parse_formula(s):
    """Intenta parsear una formula-dominio Odoo a su estructura (ignora espacios).
    Devuelve (parsed, True) si es un dominio (lista); si es expresion aritmetica,
    normaliza colapsando espacios. Devuelve (repr_normalizado, es_dominio)."""
    if not isinstance(s, str):
        return (s, False)
    txt = s.strip()
    try:
        return (ast.literal_eval(txt), True)  # dominio (lista/tupla)
    except (ValueError, SyntaxError):
        # expresion aritmetica: normaliza espacios para comparar semantica
        return ("".join(txt.split()), False)


def _formula_equiv(a, b) -> bool:
    pa, _ = _parse_formula(a)
    pb, _ = _parse_formula(b)
    return pa == pb


def compare(py_dict: dict, json_dict: dict, label: str) -> bool:
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    kpy = set(py_dict.keys())
    kjson = set(json_dict.keys())
    only_py = sorted(kpy - kjson)
    only_json = sorted(kjson - kpy)
    common = sorted(kpy & kjson)

    print(f"  Codigos en .py    : {len(kpy)}")
    print(f"  Codigos en .json  : {len(kjson)}")
    print(f"  Comunes           : {len(common)}")
    print(f"  Solo en .py       : {only_py if only_py else 'ninguno'}")
    print(f"  Solo en .json     : {only_json if only_json else 'ninguno'}")

    cosmetic = []      # formula difiere solo en espacios (parse-equivalente)
    substantive = []   # difiere en tokens reales -> cambia el resultado
    for k in common:
        a = py_dict[k]
        b = json_dict[k]
        if not isinstance(a, dict) or not isinstance(b, dict):
            if a != b:
                substantive.append((k, "valor", repr(a), repr(b)))
            continue
        fields = set(a.keys()) | set(b.keys())
        for f in fields:
            va = a.get(f, "<<ausente>>")
            vb = b.get(f, "<<ausente>>")
            if va == vb:
                continue
            if f == "formula" and _formula_equiv(va, vb):
                cosmetic.append((k, f))
            else:
                substantive.append((k, f, repr(va), repr(vb)))

    print(f"\n  Formulas que difieren SOLO en espacios (parse-equivalentes, OK para el motor): {len(cosmetic)}")
    print(f"    {sorted(set(k for k, _ in cosmetic))}")
    print(f"\n  Diferencias SUSTANTIVAS (cambian resultado o concepto): {len(substantive)}")
    for item in substantive:
        k, f = item[0], item[1]
        print(f"    [{k}] campo '{f}':")
        if len(item) == 4:
            print(f"        .py   : {item[2]}")
            print(f"        .json : {item[3]}")

    identical = not only_py and not only_json and not substantive and not cosmetic
    equiv_for_engine = not only_py and not only_json and not substantive
    print(f"\n  VEREDICTO {label}: "
          f"{'IDENTICOS' if identical else ('EQUIVALENTES p/motor (solo espacios)' if equiv_for_engine else 'DIFIEREN SUSTANTIVAMENTE')}")
    return identical


def main() -> None:
    name_pyl, pyl_py = load_py_dict(PYL_PY)
    with PYL_JSON.open(encoding="utf-8") as fh:
        pyl_json = json.load(fh)
    print(f"[INFO] .py var P&L: {name_pyl} ({len(pyl_py)} codigos)")
    ok_pyl = compare(pyl_py, pyl_json, "P&L  (.py vs P&L-2026.json)")

    name_bal, bal_py = load_py_dict(BAL_PY)
    with BAL_JSON.open(encoding="utf-8") as fh:
        bal_json = json.load(fh)
    print(f"\n[INFO] .py var Balance: {name_bal} ({len(bal_py)} codigos)")
    ok_bal = compare(bal_py, bal_json, "Balance  (.py vs Balance-General-2026.json)")

    print(f"\n{'#'*70}")
    print(f"RESULTADO FINAL: P&L {'OK' if ok_pyl else 'DIFIERE'} | "
          f"Balance {'OK' if ok_bal else 'DIFIERE'}")
    print(f"{'#'*70}")


if __name__ == "__main__":
    main()
