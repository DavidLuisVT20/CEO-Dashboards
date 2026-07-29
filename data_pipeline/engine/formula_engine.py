"""
engine/formula_engine.py
------------------------
Motor de evaluacion de formulas contables (P&L y Balance).

Carga un JSON con el arbol de formulas, construye un DAG de dependencias,
hace topological sort y evalua cada nodo:

- Nodos "Dominio de Odoo": delegan al parser odoo_domain para filtrar el df,
  multiplican balance por +1 (subformula='sum') o -1 (subformula='-sum') y
  agregan con groupby + sum.

- Nodos "Agregar otras fórmulas": parsean la expresion aritmetica con ast.parse
  (mode='eval') y la evaluan substituyendo cada referencia <NODE>.balance por
  el resultado del nodo previamente calculado.

- Nodos sin motor (section headers con formula null): se ignoran.

Para que las operaciones entre Series sean estables, cada resultado se
reindexa al "universo" comun (todas las combinaciones de las columnas de
groupby que existen en el dataset), rellenando con 0 los slices ausentes.
Eso evita NaNs por desalineacion y trata como 0 los slices donde un nodo no
matchea ninguna fila (ej. AGA26a con la cuenta analitica 4361 inexistente).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import odoo_domain


class FormulaEngine:
    """Carga formulas desde un JSON y las evalua sobre un DataFrame."""

    def __init__(self, formulas_path: Path) -> None:
        with formulas_path.open(encoding="utf-8") as fh:
            self.nodes: dict[str, dict[str, Any]] = json.load(fh)
        self.dag: dict[str, set[str]] = self._build_dag()
        self.topo_order: list[str] = self._topo_sort()

    # ------------------------------------------------------------------ DAG --

    @staticmethod
    def _is_domain_node(node: dict[str, Any]) -> bool:
        return (
            node.get("motor") == "Dominio de Odoo"
            and isinstance(node.get("formula"), str)
        )

    @staticmethod
    def _is_agg_node(node: dict[str, Any]) -> bool:
        return (
            node.get("motor") == "Agregar otras fórmulas"
            and isinstance(node.get("formula"), str)
        )

    def _is_evaluable(self, node: dict[str, Any]) -> bool:
        return self._is_domain_node(node) or self._is_agg_node(node)

    @staticmethod
    def _extract_deps(formula: str) -> set[str]:
        """De una formula aritmetica, extrae los nodos referidos via Name."""
        try:
            tree = ast.parse(formula, mode="eval")
        except SyntaxError:
            return set()
        deps: set[str] = set()
        for sub in ast.walk(tree):
            if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name):
                deps.add(sub.value.id)
            elif isinstance(sub, ast.Name):
                deps.add(sub.id)
        return deps

    def _build_dag(self) -> dict[str, set[str]]:
        """Mapea cada nodo evaluable a su conjunto de deps (codigos AGA/A...)."""
        dag: dict[str, set[str]] = {}
        for code, node in self.nodes.items():
            if self._is_agg_node(node):
                dag[code] = self._extract_deps(node["formula"])
            elif self._is_domain_node(node):
                dag[code] = set()
        return dag

    def _topo_sort(self) -> list[str]:
        """Topological sort vía Kahn. Solo cuenta deps que son evaluables."""
        in_count = {c: 0 for c in self.dag}
        dependents: dict[str, set[str]] = {c: set() for c in self.dag}
        for c, deps in self.dag.items():
            for d in deps:
                if d in self.dag:
                    in_count[c] += 1
                    dependents[d].add(c)

        queue = [c for c, cnt in in_count.items() if cnt == 0]
        ordered: list[str] = []
        while queue:
            c = queue.pop(0)
            ordered.append(c)
            for dep in dependents[c]:
                in_count[dep] -= 1
                if in_count[dep] == 0:
                    queue.append(dep)

        if len(ordered) != len(self.dag):
            faltan = set(self.dag) - set(ordered)
            raise ValueError(
                f"Ciclo o nodos no resueltos en DAG: {sorted(faltan)}"
            )
        return ordered

    # ------------------------------------------------------ Evaluacion --

    def _build_universe_idx(
        self, df: pd.DataFrame, groupby_cols: list[str]
    ) -> pd.Index | pd.MultiIndex:
        u = (
            df[groupby_cols]
            .drop_duplicates()
            .sort_values(groupby_cols)
            .reset_index(drop=True)
        )
        if len(groupby_cols) == 1:
            return pd.Index(u[groupby_cols[0]].tolist(), name=groupby_cols[0])
        return pd.MultiIndex.from_frame(u)

    def evaluate(
        self,
        df: pd.DataFrame,
        groupby_cols: list[str] | None = None,
        seed_results: dict[str, pd.Series] | None = None,
    ) -> tuple[dict[str, pd.Series], dict[str, str]]:
        """
        Evalua todos los nodos en orden topologico.
        Devuelve (resultados, errores):
          - resultados: dict {code: Series indexada por groupby_cols}.
          - errores: dict {code: mensaje} para nodos que fallaron.
        """
        if groupby_cols is None:
            groupby_cols = ["pais", "anio", "mes"]
        if "balance" not in df.columns:
            raise KeyError("El DataFrame debe tener la columna 'balance'")

        universe_idx = self._build_universe_idx(df, groupby_cols)
        zero_series = pd.Series(0.0, index=universe_idx, dtype="float64")

        # Cross-report: siembra resultados externos precalculados (p.ej. PL1001 del
        # Balance = AGA56 del P&L), reindexados al universo de este slice antes del
        # topo-sort para que los nodos "Agregar otras formulas" los resuelvan.
        results: dict[str, pd.Series] = {}
        if seed_results:
            for _code, _s in seed_results.items():
                results[_code] = _s.reindex(universe_idx).fillna(0.0)
        errors: dict[str, str] = {}

        for code in self.topo_order:
            node = self.nodes[code]
            try:
                if self._is_domain_node(node):
                    s = self._eval_domain_node(
                        df, node, groupby_cols, universe_idx
                    )
                elif self._is_agg_node(node):
                    s = self._eval_arith(node["formula"], results, zero_series)
                    if isinstance(s, (int, float)):
                        s = pd.Series(s, index=universe_idx, dtype="float64")
                else:
                    continue

                if isinstance(s, pd.Series):
                    s = s.reindex(universe_idx).fillna(0.0)
                results[code] = s
            except Exception as e:  # noqa: BLE001
                errors[code] = f"{type(e).__name__}: {e}"
                results[code] = zero_series.copy()

        return results, errors

    # -- Nodo de tipo "Dominio de Odoo" --

    @staticmethod
    def _eval_domain_node(
        df: pd.DataFrame,
        node: dict[str, Any],
        groupby_cols: list[str],
        universe_idx: pd.Index,
    ) -> pd.Series:
        mask = odoo_domain.evaluate_domain(node["formula"], df)
        sign = -1.0 if node.get("subformula") == "-sum" else 1.0
        sub = df.loc[mask, groupby_cols + ["balance"]]
        if sub.empty:
            return pd.Series(0.0, index=universe_idx, dtype="float64")
        return sub.groupby(groupby_cols, dropna=False)["balance"].sum() * sign

    # -- Nodo de tipo "Agregar otras fórmulas" --

    def _eval_arith(
        self,
        formula: str,
        results: dict[str, pd.Series],
        zero_series: pd.Series,
    ) -> pd.Series | float:
        tree = ast.parse(formula, mode="eval")
        return self._eval_arith_node(tree.body, results, zero_series)

    def _eval_arith_node(
        self,
        node: ast.AST,
        results: dict[str, pd.Series],
        zero_series: pd.Series,
    ) -> pd.Series | float:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.UnaryOp):
            v = self._eval_arith_node(node.operand, results, zero_series)
            if isinstance(node.op, ast.USub):
                return -v
            if isinstance(node.op, ast.UAdd):
                return v
            raise ValueError(f"Unario no soportado: {type(node.op).__name__}")

        if isinstance(node, ast.BinOp):
            left = self._eval_arith_node(node.left, results, zero_series)
            right = self._eval_arith_node(node.right, results, zero_series)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return self._safe_div(left, right)
            raise ValueError(f"Binario no soportado: {type(node.op).__name__}")

        if isinstance(node, ast.Attribute):
            # NODE.balance / NODE.allocated_earnings / NODE.balance_domain ...
            if isinstance(node.value, ast.Name):
                key = node.value.id
                if key in results:
                    return results[key]
                comp = f"{key}.{node.attr}"
                if comp in results:
                    return results[comp]
                return zero_series.copy()
            return zero_series.copy()

        if isinstance(node, ast.Name):
            return results.get(node.id, zero_series.copy())

        raise ValueError(f"Nodo aritmetico no soportado: {type(node).__name__}")

    @staticmethod
    def _safe_div(left: Any, right: Any) -> Any:
        """Division que devuelve NaN ante 0/0 o x/0 en vez de inf o error."""
        if not isinstance(left, pd.Series) and not isinstance(right, pd.Series):
            if right == 0:
                return float("nan")
            return left / right
        res = left / right
        if isinstance(res, pd.Series):
            res = res.replace([np.inf, -np.inf], np.nan)
        return res

    # ----------------------------------------------------- Utilidades --

    def evaluable_codes(self) -> list[str]:
        return list(self.dag.keys())

    def get_concepto(self, code: str) -> str:
        node = self.nodes.get(code, {})
        return node.get("concepto", code)

    def get_nivel(self, code: str) -> int | None:
        node = self.nodes.get(code, {})
        return node.get("nivel")
