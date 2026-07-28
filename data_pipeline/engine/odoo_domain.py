"""
engine/odoo_domain.py
---------------------
Parser y evaluador de dominios Odoo sobre DataFrames de pandas.

Un dominio Odoo es una lista de condiciones, donde:
- Las condiciones son tuplas (field, operator, value).
- Hay operadores prefijos en notacion polaca: '|' (OR), '&' (AND), '!' (NOT).
  '|' y '&' consumen los siguientes 2 elementos; '!' consume 1.
- Si no hay operador entre dos condiciones consecutivas a nivel raiz, se asume AND.

Operadores de condicion soportados:
- '=', '!=', '<', '<=', '>', '>=': comparaciones directas.
- 'in', 'not in': pertenencia/exclusion sobre listas/tuplas.
- 'like', 'not like': SQL LIKE, case-sensitive, % implicitos a ambos lados.
- 'ilike', 'not ilike': SQL LIKE, case-insensitive, % implicitos a ambos lados.
- '=like': SQL LIKE, case-sensitive, SIN % implicitos.
- '=ilike': SQL LIKE, case-insensitive, SIN % implicitos.

En LIKE: '_' = exactamente 1 caracter, '%' = 0 o mas caracteres.

Los nombres de campo en el dominio (estilo Odoo) se traducen al nombre real
del DataFrame via COLUMN_MAP.
"""
from __future__ import annotations

import ast
import re
from typing import Any

import pandas as pd


# Mapeo nombres Odoo -> nombres reales en el DataFrame del parquet.
COLUMN_MAP: dict[str, str] = {
    "account_id.code": "codigo_cuenta",
    "analytic_account_id_ika": "id_cuenta_analitica",
    "account_id.account_type": "tipo_cuenta",
    "balance": "balance",
    "partner": "contacto",
    "contacto": "contacto",
    "fecha": "fecha",
    "anio": "anio",
    "mes": "mes",
    "pais": "pais",
    "company_id": "company_id",
    "company_name": "company_name",
    "divisa": "divisa",
    "tasa_cambio": "tasa_cambio",
}


# ----------------------------------------------------------------------------
# 1) LIKE -> regex
# ----------------------------------------------------------------------------

def _like_to_regex(pattern: str) -> str:
    """Convierte un patron SQL LIKE a regex Python.

    '_' -> '.', '%' -> '.*'. Los demas chars se escapan con re.escape.
    Se construye char por char porque re.escape en Python 3.7+ NO escapa '_',
    asi que un .replace post-escape no detecta el '_' literal.
    """
    parts: list[str] = []
    for ch in pattern:
        if ch == "_":
            parts.append(".")
        elif ch == "%":
            parts.append(".*")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def _eval_like(
    series: pd.Series,
    pattern: str,
    *,
    case_insensitive: bool,
    implicit_percent: bool,
) -> pd.Series:
    """Evalua un LIKE/ILIKE/=LIKE/=ILIKE sobre una serie de strings."""
    rgx = _like_to_regex(pattern)
    flags = re.IGNORECASE if case_insensitive else 0
    s = series.astype("string")
    if implicit_percent:
        # Sustring match: SQL LIKE con %valor% es equivalente a re.search.
        return s.str.contains(rgx, flags=flags, regex=True, na=False)
    else:
        # Match completo: el patron debe cubrir todo el string.
        return s.str.fullmatch(rgx, flags=flags, na=False)


# ----------------------------------------------------------------------------
# 2) Parser del dominio (notacion polaca)
# ----------------------------------------------------------------------------

class _Parser:
    """Parser de listas de dominio Odoo a un arbol de expresiones."""

    def __init__(self, items: list[Any]) -> None:
        self.items = items
        self.pos = 0

    def _consume(self) -> Any:
        if self.pos >= len(self.items):
            raise ValueError(
                f"Dominio mal formado: se esperaba un termino mas pero se "
                f"agoto la lista (pos={self.pos}, items={self.items!r})"
            )
        item = self.items[self.pos]
        self.pos += 1

        if isinstance(item, str) and item in ("|", "&", "!"):
            if item == "!":
                child = self._consume()
                return ("NOT", child)
            op = "OR" if item == "|" else "AND"
            left = self._consume()
            right = self._consume()
            return (op, left, right)

        # Condicion: tuple (field, operator, value) o lista equivalente
        if isinstance(item, (tuple, list)) and len(item) == 3:
            field, operator, value = item
            return ("COND", field, operator, value)

        raise ValueError(f"Termino de dominio inesperado: {item!r}")

    def parse_all(self) -> Any:
        """Parsea todos los items y los une con AND implicito al nivel raiz."""
        nodes = []
        while self.pos < len(self.items):
            nodes.append(self._consume())
        if not nodes:
            return None
        if len(nodes) == 1:
            return nodes[0]
        # AND implicito entre todos los nodos top-level
        return ("AND_LIST", nodes)


def parse_domain(formula: str) -> Any:
    """Parsea un string de dominio Odoo y devuelve un arbol de expresion."""
    formula = formula.strip()
    items = ast.literal_eval(formula)
    if not isinstance(items, list):
        raise ValueError(f"Dominio debe ser una lista, recibi {type(items)}")
    return _Parser(items).parse_all()


# ----------------------------------------------------------------------------
# 3) Evaluacion del arbol contra un DataFrame
# ----------------------------------------------------------------------------

def _eval_condition(
    df: pd.DataFrame, field: str, operator: str, value: Any
) -> pd.Series:
    col = COLUMN_MAP.get(field, field)
    if col not in df.columns:
        raise KeyError(
            f"Columna desconocida en el DataFrame: '{col}' "
            f"(field Odoo: '{field}'). Columnas disponibles: {list(df.columns)}"
        )
    s = df[col]

    if operator == "=":
        return s == value
    if operator == "!=":
        return s != value
    if operator == "<":
        return s < value
    if operator == "<=":
        return s <= value
    if operator == ">":
        return s > value
    if operator == ">=":
        return s >= value
    if operator == "in":
        return s.isin(list(value))
    if operator == "not in":
        return ~s.isin(list(value))
    if operator == "like":
        return _eval_like(s, value, case_insensitive=False, implicit_percent=True)
    if operator == "not like":
        return ~_eval_like(s, value, case_insensitive=False, implicit_percent=True)
    if operator == "ilike":
        return _eval_like(s, value, case_insensitive=True, implicit_percent=True)
    if operator == "not ilike":
        return ~_eval_like(s, value, case_insensitive=True, implicit_percent=True)
    if operator == "=like":
        return _eval_like(s, value, case_insensitive=False, implicit_percent=False)
    if operator == "=ilike":
        return _eval_like(s, value, case_insensitive=True, implicit_percent=False)

    raise ValueError(f"Operador no soportado: {operator!r}")


def _eval_tree(df: pd.DataFrame, node: Any) -> pd.Series:
    if node is None:
        return pd.Series(True, index=df.index)

    tag = node[0]
    if tag == "COND":
        _, field, op, value = node
        return _eval_condition(df, field, op, value)
    if tag == "NOT":
        return ~_eval_tree(df, node[1])
    if tag == "AND":
        return _eval_tree(df, node[1]) & _eval_tree(df, node[2])
    if tag == "OR":
        return _eval_tree(df, node[1]) | _eval_tree(df, node[2])
    if tag == "AND_LIST":
        masks = [_eval_tree(df, n) for n in node[1]]
        out = masks[0]
        for m in masks[1:]:
            out = out & m
        return out

    raise ValueError(f"Nodo de arbol desconocido: {node!r}")


def evaluate_domain(formula: str, df: pd.DataFrame) -> pd.Series:
    """Parsea y evalua el dominio. Devuelve una mascara booleana sobre df."""
    tree = parse_domain(formula)
    if tree is None:
        return pd.Series(True, index=df.index)
    mask = _eval_tree(df, tree)
    # Asegurar Series booleano alineado al indice
    return mask.fillna(False).astype(bool)


# ----------------------------------------------------------------------------
# 4) Tests embebidos
# ----------------------------------------------------------------------------

def _run_tests() -> None:
    """Tests minimos cubriendo los casos pedidos por el brief."""
    print("Corriendo tests de odoo_domain...")

    # DataFrame de prueba con codigos y cuentas analiticas representativos.
    df = pd.DataFrame(
        {
            "codigo_cuenta": [
                "42000022", "42000099", "5000ABCD", "53001234",
                "10010101", "10010800", "4000800X", "62066021",
                "70001500", "70003ABC", "50008001",
            ],
            "id_cuenta_analitica": [0, 70, 62, 4376, 0, 78, 65, 64, 0, 86, 4361],
            "balance": [1.0] * 11,
        }
    )

    def assert_mask(formula: str, expected_indices: list[int], label: str) -> None:
        mask = evaluate_domain(formula, df)
        got = sorted(df.index[mask].tolist())
        exp = sorted(expected_indices)
        ok = got == exp
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {label}")
        if not ok:
            print(f"         esperado={exp} got={got}")
            print(f"         mask={mask.tolist()}")
        assert ok, f"Test fallo: {label}"

    # Test 1: ilike con _ y % — '42______' debe matchear codigos de 8 chars con 42 al inicio.
    assert_mask(
        "[('account_id.code','ilike','42______')]",
        [0, 1],
        "ilike '42______' matchea 8-char codes que empiezan con 42",
    )

    # Test 2: =ilike sin % implicitos — matchea TODOS los 8-char codes que empiezan con 5000
    assert_mask(
        "[('account_id.code','=ilike','5000____')]",
        [2, 10],  # '5000ABCD' y '50008001'
        "=ilike '5000____' matchea todos los 8-char codes que empiezan con 5000",
    )

    # Test 3: =ilike con % terminal
    assert_mask(
        "[('account_id.code','=ilike','70001%')]",
        [8],
        "=ilike '70001%' matchea cualquier code que empiece con 70001",
    )

    # Test 4: in con lista de ints (cuentas analiticas)
    assert_mask(
        "[('analytic_account_id_ika','in',[62, 64])]",
        [2, 7],
        "in [62,64] matchea analytic 62 y 64",
    )

    # Test 5: in NO matchea id_cuenta_analitica=0 (regla de negocio confirmada)
    assert_mask(
        "[('analytic_account_id_ika','in',[70])]",
        [1],
        "regla 0: in [70] NO incluye filas con analytic=0",
    )

    # Test 6: in [4361] con dato que SI tiene 4361 (no es el caso de produccion,
    # pero verifica el operador). En el real, 4361 no existe -> mask vacio.
    assert_mask(
        "[('analytic_account_id_ika','in',[4361])]",
        [10],
        "in [4361] con dato presente lo encuentra",
    )

    # Test 6b: regla 4361 en datos reales (sin 4361): mask vacio sin error
    df_sin_4361 = df[df["id_cuenta_analitica"] != 4361]
    mask_4361 = evaluate_domain("[('analytic_account_id_ika','in',[4361])]", df_sin_4361)
    assert mask_4361.sum() == 0, "regla 4361 deberia dar mask vacio en datos sin 4361"
    print("  [OK  ] regla 4361: in [4361] sin datos -> mask vacio sin error")

    # Test 7: not in (lista de strings)
    assert_mask(
        "[('account_id.code','not in',('42000022','42000099'))]",
        [2, 3, 4, 5, 6, 7, 8, 9, 10],
        "not in excluye los codigos listados",
    )

    # Test 8: combinacion |, ilike sobre prefijos largos
    assert_mask(
        "['|',('account_id.code','=ilike','6%'),('account_id.code','=ilike','7%')]",
        [7, 8, 9],
        "OR de dos =ilike por prefijo (cuentas 6/7)",
    )

    # Test 9: encadenamiento largo de | (analytic in varias listas)
    assert_mask(
        "['|','|',"
        "('analytic_account_id_ika','in',[78]),"
        "('analytic_account_id_ika','in',[65]),"
        "('analytic_account_id_ika','in',[64])]",
        [5, 6, 7],
        "OR encadenado de 3 condiciones analitic in",
    )

    # Test 10: ! (NOT)
    assert_mask(
        "['!',('account_id.code','=','42000022')]",
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "NOT (= '42000022') excluye solo esa fila",
    )

    # Test 11: AND implicito en top-level (lista de varios items)
    # AGA10-like: analytic in [78] AND (code ilike 6% OR code ilike 7%)
    assert_mask(
        "[('analytic_account_id_ika','in',[78]),"
        "'|',('account_id.code','=ilike','6%'),('account_id.code','=ilike','7%')]",
        [],  # idx 5 tiene analytic=78 PERO codigo '10010800' no empieza con 6 ni 7
        "AND implicito + OR anidado (AGA10 sin matches)",
    )

    # Test 11b: el mismo patron con datos que SI cumplen
    df_aga10 = df.copy()
    df_aga10.loc[5, "codigo_cuenta"] = "62001000"  # ahora si empieza con 6 y tiene analytic=78
    mask_aga10 = evaluate_domain(
        "[('analytic_account_id_ika','in',[78]),"
        "'|',('account_id.code','=ilike','6%'),('account_id.code','=ilike','7%')]",
        df_aga10,
    )
    assert mask_aga10.sum() == 1, f"AGA10 con codigo 6XX deberia matchear 1, dio {mask_aga10.sum()}"
    print("  [OK  ] AND + OR anidado: 1 match cuando se cumplen ambos lados")

    # Test 12: lista de patrones con 7 pipes seguidos (estilo AGA1IB)
    assert_mask(
        "['|','|','|','|','|','|','|',"
        "('account_id.code','=ilike','42______'),"
        "('account_id.code','=ilike','5000____'),"
        "('account_id.code','=ilike','5300____'),"
        "('account_id.code','=ilike','10010101'),"
        "('account_id.code','=','62066021'),"
        "('account_id.code','=','70003ABC'),"
        "('account_id.code','=','50008001'),"
        "('account_id.code','=','99999999')]",
        [0, 1, 2, 3, 4, 7, 9, 10],
        "7 pipes con 8 condiciones (AGA1IB-style polish notation)",
    )

    # Test 13: 'like' (con % implicitos) — case-sensitive substring
    assert_mask(
        "[('account_id.code','like','62066')]",
        [7],
        "like '62066' (con % implicitos) -> substring match",
    )

    print()
    print("Todos los tests pasaron.")


if __name__ == "__main__":
    _run_tests()
