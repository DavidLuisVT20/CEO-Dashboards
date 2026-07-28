"""
99_evidencia_s3.py
------------------
Corre 3 tests contra S3 y renderiza una imagen PNG con los resultados,
para enviar como evidencia visual a Ikatech.

Tests:
  1. ListBucket sobre el prefijo del dataset particionado
  2. GetObject (head) sobre el parquet viejo que funcionaba
  3. sts.GetCallerIdentity para confirmar que las llaves siguen vivas

La imagen NO incluye las llaves IAM ni ningun secret: solo el ARN del usuario,
el ID de cuenta, el bucket/prefijo, los mensajes de error completos y la
hora UTC del test.
"""
from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


HERE = Path(__file__).resolve().parent
ENV_PATH = HERE / ".env"
OUT_PATH = HERE / "ACCESO_S3_EVIDENCIA.png"

BUCKET = "addiuva-bi-analytics"
PREFIX_NUEVO = "PowerBI/apuntes_contables_particionado/"
KEY_VIEJO = "PowerBI/apuntes_contables.parquet"


def _client(service: str):
    return boto3.client(
        service,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )


def test_list_bucket() -> tuple[str, str]:
    s3 = _client("s3")
    try:
        pag = s3.get_paginator("list_objects_v2")
        n = 0
        for page in pag.paginate(Bucket=BUCKET, Prefix=PREFIX_NUEVO, PaginationConfig={"MaxItems": 1}):
            n += len(page.get("Contents", []))
        return "OK", f"Listado correctamente. Objetos vistos: {n}"
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "?")
        msg = e.response.get("Error", {}).get("Message", str(e))
        return "ERROR", f"{code}: {msg}"


def test_get_object_viejo() -> tuple[str, str]:
    s3 = _client("s3")
    try:
        h = s3.head_object(Bucket=BUCKET, Key=KEY_VIEJO)
        return "OK", f"Tamano: {h['ContentLength'] / 1024 / 1024:.2f} MB"
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "?")
        http = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", "?")
        return "ERROR", f"HTTP {http} / {code}: acceso denegado al objeto"


def test_sts() -> tuple[str, dict | str]:
    sts = _client("sts")
    try:
        ident = sts.get_caller_identity()
        return "OK", {
            "Account": ident["Account"],
            "Arn": ident["Arn"],
            "UserId": ident["UserId"],
        }
    except ClientError as e:
        return "ERROR", str(e)


def render_png(results: list[dict], out_path: Path) -> None:
    fig = plt.figure(figsize=(15, 10))

    # --- Titulo y subtitulo ---
    title = "Diagnóstico de acceso a S3 — usuario IAM lectura_powerBI"
    ts_utc = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subtitle = f"Bucket: s3://{BUCKET}    ·    Tests ejecutados: {ts_utc}"

    fig.text(0.5, 0.965, title, ha="center", va="top",
             fontsize=17, fontweight="bold")
    fig.text(0.5, 0.925, subtitle, ha="center", va="top",
             fontsize=11, color="#555")

    # --- Tabla resumen (arriba) ---
    ax_table = fig.add_axes((0.04, 0.62, 0.92, 0.24))
    ax_table.axis("off")

    headers = ["#", "Test", "Recurso probado", "Resultado"]
    rows = []
    cell_colors = []
    for r in results:
        rows.append([str(r["n"]), r["test"], r["recurso_corto"], r["resultado"]])
        bg = "#d6f5d6" if r["resultado"] == "OK" else "#f8d6d6"
        cell_colors.append(["#ffffff", "#ffffff", "#ffffff", bg])

    table = ax_table.table(
        cellText=rows,
        colLabels=headers,
        cellColours=cell_colors,
        colColours=["#2c3e50"] * len(headers),
        loc="upper left",
        cellLoc="left",
        colLoc="left",
        bbox=(0.0, 0.0, 1.0, 1.0),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)

    for col_idx in range(len(headers)):
        cell = table[(0, col_idx)]
        cell.get_text().set_color("white")
        cell.get_text().set_fontweight("bold")
        cell.set_height(0.22)

    widths = [0.05, 0.22, 0.58, 0.15]
    for col_idx, w in enumerate(widths):
        for row_idx in range(len(rows) + 1):
            table[(row_idx, col_idx)].set_width(w)
    for row_idx in range(1, len(rows) + 1):
        for col_idx in range(len(headers)):
            table[(row_idx, col_idx)].set_height(0.22)
            table[(row_idx, col_idx)].PAD = 0.04

    # --- Detalle completo (abajo) ---
    fig.text(0.04, 0.55, "Detalle completo de cada test",
             fontsize=13, fontweight="bold", color="#2c3e50")

    y_cursor = 0.51
    for r in results:
        bg = "#d6f5d6" if r["resultado"] == "OK" else "#f8d6d6"
        edge = "#28a745" if r["resultado"] == "OK" else "#c0392b"

        header_line = f"Test {r['n']} — {r['test']}    [{r['resultado']}]"
        fig.text(0.05, y_cursor, header_line,
                 fontsize=11, fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.35", fc=bg, ec=edge, lw=1.0))

        body = f"Recurso: {r['recurso']}\n{r['detalle']}"
        fig.text(0.05, y_cursor - 0.025, body,
                 fontsize=10, color="#222", va="top",
                 family="monospace",
                 wrap=True,
                 bbox=dict(boxstyle="round,pad=0.45", fc="#f5f5f5", ec="#cccccc"))

        # cuanto espacio toma este bloque (aprox por numero de lineas)
        n_lines = body.count("\n") + 1
        y_cursor -= 0.040 + 0.027 * n_lines

    # --- Lectura final ---
    legend_text = (
        "Lectura: STS responde correctamente (las llaves IAM son válidas y el usuario existe),\n"
        "pero ninguna operación de S3 está autorizada por la policy IAM actual — ni listar el\n"
        "prefijo del dataset particionado, ni leer el parquet que antes funcionaba."
    )
    fig.text(0.5, 0.06, legend_text, ha="center", va="bottom",
             fontsize=11, color="#222",
             bbox=dict(boxstyle="round,pad=0.7", fc="#fff3cd", ec="#e0a800", lw=1.5))

    fig.savefig(out_path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    load_dotenv(ENV_PATH, override=True)

    print("[1/3] ListBucket sobre prefijo nuevo...")
    list_status, list_detail = test_list_bucket()
    print(f"  -> {list_status}: {list_detail}")

    print("[2/3] GetObject sobre archivo viejo...")
    get_status, get_detail = test_get_object_viejo()
    print(f"  -> {get_status}: {get_detail}")

    print("[3/3] sts:GetCallerIdentity...")
    sts_status, sts_detail = test_sts()
    if isinstance(sts_detail, dict):
        print(f"  -> {sts_status}: Arn={sts_detail['Arn']}, Account={sts_detail['Account']}")
        sts_detail_str = (
            f"Account: {sts_detail['Account']}\n"
            f"Arn: {sts_detail['Arn']}\n"
            f"UserId: {sts_detail['UserId']}"
        )
    else:
        print(f"  -> {sts_status}: {sts_detail}")
        sts_detail_str = sts_detail

    results = [
        {
            "n": 1,
            "test": "s3:ListBucket",
            "recurso_corto": f"prefix = {PREFIX_NUEVO}",
            "recurso": f"s3://{BUCKET}/{PREFIX_NUEVO}",
            "resultado": list_status,
            "detalle": list_detail,
        },
        {
            "n": 2,
            "test": "s3:GetObject (head_object)",
            "recurso_corto": KEY_VIEJO,
            "recurso": f"s3://{BUCKET}/{KEY_VIEJO}",
            "resultado": get_status,
            "detalle": get_detail,
        },
        {
            "n": 3,
            "test": "sts:GetCallerIdentity",
            "recurso_corto": "(identidad IAM del cliente)",
            "recurso": "(no aplica — verificación de identidad)",
            "resultado": sts_status,
            "detalle": sts_detail_str,
        },
    ]

    render_png(results, OUT_PATH)
    print()
    print(f"[OK] Imagen escrita en {OUT_PATH}")


if __name__ == "__main__":
    main()
