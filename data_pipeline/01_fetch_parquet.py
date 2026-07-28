"""
01_fetch_parquet.py
-------------------
Descarga el parquet de apuntes contables desde S3 y lo guarda en
data_pipeline/data/raw/. Lee credenciales de data_pipeline/.env.

Uso:
    python 01_fetch_parquet.py                # usa S3_PARQUET_URI tal como esta en .env
    python 01_fetch_parquet.py --year 2019    # sustituye el sufijo _AAAA por _2019 en la URI
    python 01_fetch_parquet.py --year 2020    # idem para 2020, etc.

Cuando se pasa --year, se reemplaza el patron _NNNN (4 digitos) en el basename del
S3_PARQUET_URI por el ano dado. Si la URI no tiene un patron _NNNN, se inserta antes
del .parquet (ej: apuntes_contables.parquet -> apuntes_contables_2020.parquet).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import boto3
import pandas as pd
import pyarrow.parquet as pq
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    PartialCredentialsError,
)
from dotenv import load_dotenv


HERE = Path(__file__).resolve().parent
ENV_PATH = HERE / ".env"
RAW_DIR = HERE / "data" / "raw"


def _exit_error(msg: str, hint: str | None = None, code: int = 1) -> None:
    print(f"\n[ERROR] {msg}", file=sys.stderr)
    if hint:
        print(f"[HINT]  {hint}", file=sys.stderr)
    sys.exit(code)


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        _exit_error(
            f"S3_PARQUET_URI invalido: {uri!r}",
            "Debe tener el formato s3://bucket/key.parquet",
        )
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


def _apply_year(uri: str, year: int) -> str:
    """Sustituye/inserta el sufijo de ano en la URI.

    apuntes_contables_2019.parquet  + year=2020 -> apuntes_contables_2020.parquet
    apuntes_contables.parquet       + year=2020 -> apuntes_contables_2020.parquet
    """
    base, sep, ext = uri.rpartition(".")
    if not sep:
        return uri
    new_base = re.sub(r"_\d{4}$", f"_{year}", base)
    if new_base == base:
        new_base = f"{base}_{year}"
    return f"{new_base}.{ext}"


def _download_prefix(s3, bucket: str, prefix: str) -> None:
    """Descarga TODOS los objetos bajo un prefijo (dataset Hive) preservando
    la estructura de carpetas en data/raw/<ultimo-segmento-del-prefijo>/."""
    import concurrent.futures as cf

    seg = prefix.rstrip("/").split("/")[-1]
    dest_root = RAW_DIR / seg
    dest_root.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Modo PREFIJO (Hive). Destino: {dest_root}")

    paginator = s3.get_paginator("list_objects_v2")
    objs: list[tuple[str, int]] = []
    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for o in page.get("Contents", []):
                if o["Key"].endswith(".parquet"):
                    objs.append((o["Key"], o["Size"]))
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        _exit_error(
            f"No se pudo listar el prefijo ({code}): {e}",
            "El IAM necesita s3:ListBucket con Condition s3:prefix sobre este prefijo.",
        )

    if not objs:
        _exit_error(f"El prefijo no tiene objetos .parquet: s3://{bucket}/{prefix}")

    total_mb = sum(s for _, s in objs) / (1024 * 1024)
    print(f"[INFO] {len(objs)} archivos, {total_mb:,.2f} MB en total.")

    def _one(item: tuple[str, int]) -> str:
        k, size = item
        rel = k[len(prefix):]
        out = dest_root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        # skip-if-exists: si ya esta y coincide el tamano, no re-bajar
        if out.exists() and out.stat().st_size == size:
            return f"  [skip] {rel} ({size/1024/1024:.2f} MB, ya existe)"
        s3.download_file(bucket, k, str(out))
        return f"  [ok]   {rel} ({size/1024/1024:.2f} MB)"

    # Descarga en paralelo (4 hilos): util porque hay archivos grandes.
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for msg in ex.map(_one, objs):
            print(msg, flush=True)

    print(f"\n[OK] Dataset particionado en {dest_root}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga el parquet de apuntes contables desde S3.")
    parser.add_argument("--year", type=int, default=None,
                        help="Anio (4 digitos). Sustituye el sufijo _AAAA del S3_PARQUET_URI.")
    args = parser.parse_args()

    print(f"[INFO] Cargando .env desde {ENV_PATH}")
    if not ENV_PATH.exists():
        _exit_error(
            f"No existe {ENV_PATH}",
            "Crea el archivo .env con AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION y S3_PARQUET_URI.",
        )
    load_dotenv(ENV_PATH, override=True)

    access_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1").strip() or "us-east-1"
    s3_uri = os.getenv("S3_PARQUET_URI", "").strip()

    if not access_key or not secret_key:
        _exit_error(
            "Credenciales AWS vacias en .env",
            "Pega los valores de AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY en data_pipeline/.env.",
        )
    if not s3_uri:
        _exit_error(
            "S3_PARQUET_URI vacio en .env",
            "Define S3_PARQUET_URI=s3://addiuva-bi-analytics/PowerBI/apuntes_contables.parquet en .env.",
        )

    if args.year is not None:
        s3_uri = _apply_year(s3_uri, args.year)
        print(f"[INFO] --year={args.year} -> URI ajustada: {s3_uri}")

    bucket, key = _parse_s3_uri(s3_uri)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Region        : {region}")
    print(f"[INFO] Bucket        : {bucket}")
    print(f"[INFO] Key/Prefix    : {key}")

    s3 = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )

    # Modo PREFIJO (dataset particionado tipo Hive): la URI termina en '/'.
    if key.endswith("/"):
        _download_prefix(s3, bucket, key)
        return

    out_path = RAW_DIR / Path(key).name
    print(f"[INFO] Destino local : {out_path}")

    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        size_mb = head["ContentLength"] / (1024 * 1024)
        print(f"[INFO] Objeto S3 OK. Tamano: {size_mb:,.2f} MB")
    except NoCredentialsError:
        _exit_error("No se encontraron credenciales AWS.", "Revisa data_pipeline/.env.")
    except PartialCredentialsError as e:
        _exit_error(f"Credenciales AWS incompletas: {e}", "Revisa data_pipeline/.env.")
    except EndpointConnectionError as e:
        _exit_error(
            f"No se pudo conectar al endpoint S3: {e}",
            f"Verifica conectividad y que la region '{region}' es correcta.",
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        if code in {"403", "AccessDenied"}:
            _exit_error(
                f"Acceso denegado a s3://{bucket}/{key}",
                "El usuario IAM no tiene permisos s3:GetObject sobre ese objeto. Pidele a TI ajustar la policy.",
            )
        if code in {"404", "NoSuchKey"}:
            _exit_error(
                f"El objeto no existe: s3://{bucket}/{key}",
                "Verifica con Ikatech la ruta exacta del parquet en el bucket.",
            )
        if code in {"NoSuchBucket"}:
            _exit_error(
                f"El bucket no existe: {bucket}",
                "Verifica el nombre del bucket y la region.",
            )
        _exit_error(f"ClientError ({code}): {e}", "Revisa permisos IAM y region.")

    try:
        print("[INFO] Descargando objeto...")
        s3.download_file(bucket, key, str(out_path))
    except ClientError as e:
        _exit_error(f"Fallo al descargar: {e}", "Reintenta; si persiste, revisa permisos.")

    try:
        pf = pq.ParquetFile(out_path)
        n_rows = pf.metadata.num_rows
        n_cols = pf.metadata.num_columns
        schema_names = list(pf.schema_arrow.names)
    except Exception as e:
        _exit_error(
            f"El archivo se descargo pero pyarrow no pudo abrirlo: {e}",
            f"Inspecciona manualmente {out_path}.",
        )

    print("\n========== RESUMEN ==========")
    print(f"  Archivo local : {out_path}")
    print(f"  Filas         : {n_rows:,}")
    print(f"  Columnas      : {n_cols}")
    print(f"  Schema        : {schema_names}")
    print("=============================")

    df_head = pd.read_parquet(out_path).head(3)
    print("\n[INFO] Primeras 3 filas (truncado):")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(df_head)


if __name__ == "__main__":
    main()
