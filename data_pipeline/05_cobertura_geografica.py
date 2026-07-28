"""
05_cobertura_geografica.py
--------------------------
Mapa de cobertura geografica del dataset particionado, todos los anios.

La unidad real en Odoo es la SOCIEDAD (company_id / company_name), no el pais.
Cada company_name lleva el pais en su nombre, asi que lo usamos como fuente de
verdad y lo cruzamos contra la columna `pais`.

Genera output/cobertura/COBERTURA.md con 4 secciones:
  1. Tabla pais x anio (desde la columna pais).
  2. Inventario de sociedades (company_id).
  3. Extraccion de pais desde company_name + discrepancias.
  4. Resumen y paises del grupo ausentes.

Uso:
    python 05_cobertura_geografica.py
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds

HERE = Path(__file__).resolve().parent
DATASET_PATH = HERE / "data" / "raw" / "apuntes_contables_particionado"
OUT_DIR = HERE / "output" / "cobertura"

# Paises del grupo + alias. Clave = nombre canonico; valor = lista de variantes
# a buscar dentro del company_name (normalizadas: minuscula, sin acento).
PAIS_ALIASES: dict[str, list[str]] = {
    "Mexico": ["mexico"],
    "Chile": ["chile"],
    "Colombia": ["colombia"],
    "Argentina": ["argentina"],
    "Peru": ["peru"],
    "Bolivia": ["bolivia"],
    "Uruguay": ["uruguay"],
    "Guatemala": ["guatemala"],
    "Costa Rica": ["costa rica"],
    "Ecuador": ["ecuador"],
    "Nicaragua": ["nicaragua"],
    "Honduras": ["honduras"],
    "Paraguay": ["paraguay"],
    "Panama": ["panama"],
    "El Salvador": ["el salvador", "salvador"],
    "Republica Dominicana": ["republica dominicana", "dominicana", "rep dominicana"],
    "Venezuela": ["venezuela"],
    "Brasil": ["brasil", "brazil"],
    "Estados Unidos": ["estados unidos", "united states", "usa", "u.s.a", "u.s."],
    "Espana": ["espana", "spain"],
    "Egipto": ["egipto", "egypt"],
}

# Universo esperado del grupo (nombres canonicos).
GRUPO_ESPERADO = list(PAIS_ALIASES.keys())

ANIOS = [2022, 2023, 2024, 2025, 2026]


# --------------------------------------------------------------- helpers ----

def _strip_accents(text: str) -> str:
    if not isinstance(text, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _norm(text) -> str:
    return _strip_accents(str(text)).lower().strip()


def _fmt_int(v) -> str:
    if pd.isna(v):
        return "0"
    return f"{int(v):,}".replace(",", ".")


def _fmt_money(v) -> str:
    if pd.isna(v):
        return "_NaN_"
    return f"{v:,.0f}".replace(",", ".")


def detect_pais(company_name: str) -> str | None:
    """Extrae el pais canonico del company_name; None si no se detecta."""
    norm = _norm(company_name)
    # Orden: priorizar nombres mas largos/especificos (Costa Rica antes que Rica, etc.)
    # Buscamos por longitud de alias descendente para evitar falsos cortos.
    candidatos: list[tuple[int, str]] = []
    for canonico, variantes in PAIS_ALIASES.items():
        for v in variantes:
            if v in norm:
                candidatos.append((len(v), canonico))
    if not candidatos:
        return None
    candidatos.sort(reverse=True)
    return candidatos[0][1]


def _md_table(headers: list[str], rows: list[list[str]],
              right_cols: set[int] | None = None) -> list[str]:
    right_cols = right_cols or set()
    lines = ["| " + " | ".join(headers) + " |"]
    sep = []
    for i in range(len(headers)):
        sep.append("---:" if i in right_cols else "---")
    lines.append("|" + "|".join(sep) + "|")
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    return lines


# ------------------------------------------------------------- secciones ----

def seccion_pais_x_anio(df: pd.DataFrame) -> list[str]:
    out = ["## 1. Tabla pais x anio (columna `pais`)\n",
           "Celdas = numero de filas (movimientos).\n"]
    pivot = (
        df.assign(_p=df["pais"].fillna("(nulo)"))
        .pivot_table(index="_p", columns="anio", values="balance",
                     aggfunc="size", fill_value=0)
    )
    for y in ANIOS:
        if y not in pivot.columns:
            pivot[y] = 0
    pivot = pivot[ANIOS]
    pivot["TOTAL"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("TOTAL", ascending=False)

    headers = ["pais"] + [str(y) for y in ANIOS] + ["TOTAL"]
    rows = []
    for p, r in pivot.iterrows():
        rows.append([str(p)] + [_fmt_int(r[y]) for y in ANIOS] + [_fmt_int(r["TOTAL"])])
    total_row = ["**TOTAL**"] + [_fmt_int(pivot[y].sum()) for y in ANIOS] + [_fmt_int(pivot["TOTAL"].sum())]
    rows.append(total_row)
    out += _md_table(headers, rows, right_cols=set(range(1, len(headers))))
    out.append("")
    return out


def build_sociedades(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["company_id", "company_name", "pais"], dropna=False)
    soc = g.agg(
        filas=("balance", "size"),
        balance_total=("balance", "sum"),
    ).reset_index()
    anios_por_soc = (
        df.groupby("company_id")["anio"]
        .apply(lambda s: ",".join(str(a) for a in sorted(s.unique())))
        .rename("anios")
    )
    soc = soc.merge(anios_por_soc, on="company_id", how="left")
    soc["pais_detectado"] = soc["company_name"].map(detect_pais)
    soc = soc.sort_values(
        ["pais", "company_name"],
        key=lambda col: col.map(lambda x: _norm(x) if pd.notna(x) else "")
    )
    return soc


def seccion_inventario(soc: pd.DataFrame) -> list[str]:
    out = ["## 2. Inventario de sociedades (una fila por company_id)\n"]
    headers = ["company_id", "company_name", "pais (col)", "pais_detectado",
               "anios con datos", "filas", "balance total"]
    rows = []
    for _, r in soc.iterrows():
        rows.append([
            str(int(r["company_id"])) if pd.notna(r["company_id"]) else "(nulo)",
            str(r["company_name"]) if pd.notna(r["company_name"]) else "(nulo)",
            str(r["pais"]) if pd.notna(r["pais"]) else "(nulo)",
            str(r["pais_detectado"]) if pd.notna(r["pais_detectado"]) else "(no detectado)",
            str(r["anios"]),
            _fmt_int(r["filas"]),
            _fmt_money(r["balance_total"]),
        ])
    out += _md_table(headers, rows, right_cols={5, 6})
    out.append("")
    return out


def seccion_cruce(soc: pd.DataFrame) -> list[str]:
    out = ["## 3. Cruce pais (columna) vs pais_detectado (company_name)\n"]

    # a) discrepancias: detectado != columna (ambos no nulos)
    mask_disc = (
        soc["pais_detectado"].notna()
        & soc["pais"].notna()
        & (soc["pais_detectado"].map(_norm) != soc["pais"].map(_norm))
    )
    out.append("### 3a. Discrepancias: el nombre dice un pais distinto al de la columna\n")
    disc = soc.loc[mask_disc]
    if disc.empty:
        out.append("_Ninguna. Donde ambos existen, concuerdan._\n")
    else:
        rows = [[str(int(r["company_id"])), str(r["company_name"]),
                 str(r["pais"]), str(r["pais_detectado"])] for _, r in disc.iterrows()]
        out += _md_table(["company_id", "company_name", "pais (col)", "pais_detectado"], rows)
        out.append("")

    # b) columna nula pero nombre tiene pais
    mask_colnull = soc["pais"].isna() & soc["pais_detectado"].notna()
    out.append("\n### 3b. Columna `pais` vacia pero el nombre SI tiene pais\n")
    cn = soc.loc[mask_colnull]
    if cn.empty:
        out.append("_Ninguna._\n")
    else:
        rows = [[str(int(r["company_id"])), str(r["company_name"]),
                 str(r["pais_detectado"])] for _, r in cn.iterrows()]
        out += _md_table(["company_id", "company_name", "pais_detectado"], rows)
        out.append("")

    # c) no se detecto pais en el nombre
    mask_nodet = soc["pais_detectado"].isna()
    out.append("\n### 3c. No se detecto ningun pais en el company_name (revisar a mano)\n")
    nd = soc.loc[mask_nodet]
    if nd.empty:
        out.append("_Ninguna: todos los nombres tienen un pais reconocible._\n")
    else:
        rows = [[str(int(r["company_id"])) if pd.notna(r["company_id"]) else "(nulo)",
                 str(r["company_name"]) if pd.notna(r["company_name"]) else "(nulo)",
                 str(r["pais"]) if pd.notna(r["pais"]) else "(nulo)"]
                for _, r in nd.iterrows()]
        out += _md_table(["company_id", "company_name", "pais (col)"], rows)
        out.append("")

    return out


def seccion_resumen(df: pd.DataFrame, soc: pd.DataFrame) -> list[str]:
    out = ["## 4. Resumen\n"]

    n_soc = soc["company_id"].nunique()
    paises_col = sorted(df["pais"].dropna().unique().tolist())
    paises_det = sorted(soc["pais_detectado"].dropna().unique().tolist())

    out.append(f"- **Sociedades (company_id) distintas:** {n_soc}")
    out.append(f"- **Paises segun columna `pais`:** {len(paises_col)} -> {paises_col}")
    out.append(f"- **Paises segun `pais_detectado` (del nombre):** {len(paises_det)} -> {paises_det}")
    out.append("")

    # Sociedades por pais detectado
    out.append("\n### 4a. Sociedades por pais_detectado\n")
    by_pais = (
        soc.dropna(subset=["pais_detectado"])
        .groupby("pais_detectado")
        .agg(n_sociedades=("company_id", "nunique"),
             filas=("filas", "sum"),
             balance=("balance_total", "sum"))
        .reset_index()
        .sort_values("n_sociedades", ascending=False)
    )
    rows = [[r["pais_detectado"], str(int(r["n_sociedades"])),
             _fmt_int(r["filas"]), _fmt_money(r["balance"])]
            for _, r in by_pais.iterrows()]
    out += _md_table(["pais_detectado", "# sociedades", "filas", "balance total"],
                     rows, right_cols={1, 2, 3})
    out.append("")

    # Paises del grupo ausentes. Un pais cuenta como PRESENTE si:
    #  - su nombre canonico o alguno de sus alias aparece (normalizado) en la
    #    columna pais, o
    #  - fue detectado en algun company_name (pais_detectado).
    presentes_col = set(_norm(p) for p in paises_col)
    presentes_det = set(_norm(p) for p in paises_det)
    ausentes = []
    for canonico in GRUPO_ESPERADO:
        formas = {_norm(canonico)} | {_norm(a) for a in PAIS_ALIASES[canonico]}
        esta = bool(formas & presentes_col) or _norm(canonico) in presentes_det
        if not esta:
            ausentes.append(canonico)
    out.append("\n### 4b. Paises del grupo esperado que NO aparecen (ni por columna ni por nombre)\n")
    if ausentes:
        for p in ausentes:
            out.append(f"- {p}")
    else:
        out.append("_Ninguno: todos los paises esperados aparecen._")
    out.append("")
    return out


# ----------------------------------------------------------------- main ----

def main() -> None:
    if not DATASET_PATH.exists():
        print(f"[ERROR] No existe {DATASET_PATH}. Corre 01_fetch_parquet.py.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Leyendo dataset Hive desde {DATASET_PATH}")
    dataset = ds.dataset(str(DATASET_PATH), partitioning="hive")
    df = dataset.to_table().to_pandas()
    if "account_type" in df.columns and "tipo_cuenta" not in df.columns:
        df = df.rename(columns={"account_type": "tipo_cuenta"})
    print(f"[INFO] Filas totales: {len(df):,}  Anios: {sorted(df['anio'].unique().tolist())}")

    soc = build_sociedades(df)
    print(f"[INFO] Sociedades distintas: {soc['company_id'].nunique()}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    parts: list[str] = []
    parts.append("# Cobertura geografica del dataset particionado\n")
    parts.append(f"**Dataset:** {DATASET_PATH.name}  ")
    parts.append(f"**Filas totales:** {len(df):,}  ")
    parts.append(f"**Anios:** {sorted(df['anio'].unique().tolist())}  \n")
    parts.append("---\n")
    parts += seccion_pais_x_anio(df)
    parts.append("\n---\n")
    parts += seccion_inventario(soc)
    parts.append("\n---\n")
    parts += seccion_cruce(soc)
    parts.append("\n---\n")
    parts += seccion_resumen(df, soc)

    out_path = OUT_DIR / "COBERTURA.md"
    out_path.write_text("\n".join(parts), encoding="utf-8")
    print(f"[OK] {out_path}")


if __name__ == "__main__":
    main()
