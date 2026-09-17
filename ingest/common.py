"""Utilidades compartidas por las tres vías de ingesta.

- Configuración por variables de entorno (ver .env.example).
- Catálogo de fuentes: archivo → fuente lógica → vía de ingesta.
- sha256 y conteo de filas de datos (sin encabezado) de un archivo.
- Manifiesto `ops.ingest_manifest` en BigQuery: una fila por (archivo, sha256, vía)
  ya ingerido. Es la base de la idempotencia de Bronze: un archivo cuyo sha256 ya
  está en el manifiesto no se vuelve a copiar ni a publicar.
- Subida a GCS con nombre determinista bajo bronze/<fuente>/ingest_date=YYYY-MM-DD/.

Autenticación: Application Default Credentials (laptop) o la cuenta de servicio
adjunta a la VM. Nunca llaves JSON.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import os
import uuid
from pathlib import Path
from typing import Iterable

from google.api_core.exceptions import NotFound
from google.cloud import bigquery, storage

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
PROJECT_ID = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "cienciadatos-509301"
REGION = os.environ.get("GCP_REGION", "us-central1")
LAKE_BUCKET = os.environ.get("LAKE_BUCKET", f"{PROJECT_ID}-lake")
DATOS_DIR = Path(os.environ.get("DATOS_DIR", "datos_red"))
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
OPS_DATASET = "ops"
BRONZE_DATASET = "bronze"
MANIFEST_TABLE = f"{PROJECT_ID}.{OPS_DATASET}.ingest_manifest"
RUN_METRICS_TABLE = f"{PROJECT_ID}.{OPS_DATASET}.run_metrics"
TZ_LOCAL = dt.timezone(dt.timedelta(hours=-6), name="America/Guatemala")  # sin horario de verano


def run_id_actual() -> str:
    """Identificador de corrida: lo fija Airflow por RUN_ID; si no, uno nuevo."""
    return os.environ.get("RUN_ID") or f"manual-{dt.datetime.now(TZ_LOCAL):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"


def ingest_date_hoy() -> str:
    """Partición de Bronze: fecha local de ingesta (America/Guatemala)."""
    return os.environ.get("INGEST_DATE") or dt.datetime.now(TZ_LOCAL).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Catálogo de fuentes (esquemas verificados en docs/generar_red_metropolitana.py)
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Fuente:
    archivo: str          # nombre del archivo en datos_red/
    fuente: str           # nombre lógico (carpeta en bronze/ y tabla externa)
    via: str              # batch | streaming | cdc
    operador: str         # TM | TU | MR | AM | AGENCIA
    formato: str          # csv | jsonl
    topico: str | None = None  # solo streaming


FUENTES: dict[str, Fuente] = {
    f.archivo: f
    for f in [
        # Catálogos (batch)
        Fuente("tm_estaciones.csv", "tm_estaciones", "batch", "TM", "csv"),
        Fuente("tu_paradas.csv", "tu_paradas", "batch", "TU", "csv"),
        Fuente("mr_estaciones.csv", "mr_estaciones", "batch", "MR", "csv"),
        Fuente("am_estaciones.csv", "am_estaciones", "batch", "AM", "csv"),
        # Operación por batch: MetroRiel (viaje cerrado) y Transurbano (ADR-003)
        Fuente("metroriel_viajes.jsonl", "metroriel_viajes", "batch", "MR", "jsonl"),
        Fuente("transurbano_transacciones.csv", "transurbano_transacciones", "batch", "TU", "csv"),
        # Operación por streaming (Kafka): Transmetro y Aerómetro
        Fuente("transmetro_validaciones.csv", "transmetro_validaciones", "streaming", "TM", "csv", "transmetro.validaciones"),
        Fuente("aerometro_boardings.csv", "aerometro_boardings", "streaming", "AM", "csv", "aerometro.boardings"),
        # CDC: log de cambios del padrón
        Fuente("cdc_padron_usuarios.csv", "cdc_padron_usuarios", "cdc", "AGENCIA", "csv"),
    ]
}


def fuentes_por_via(via: str) -> list[Fuente]:
    return [f for f in FUENTES.values() if f.via == via]


# ---------------------------------------------------------------------------
# Archivos: hash y conteo
# ---------------------------------------------------------------------------
def sha256_archivo(path: Path, bloque: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(bloque), b""):
            h.update(chunk)
    return h.hexdigest()


def contar_filas(path: Path, formato: str) -> int:
    """Filas de datos: líneas no vacías, menos el encabezado si es CSV."""
    with path.open("rb") as f:
        n = sum(1 for linea in f if linea.strip())
    return n - 1 if formato == "csv" else n


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------
def bq_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID, location=REGION)


def gcs_client() -> storage.Client:
    return storage.Client(project=PROJECT_ID)


# ---------------------------------------------------------------------------
# Manifiesto de ingesta (ops.ingest_manifest)
# ---------------------------------------------------------------------------
MANIFEST_SCHEMA = [
    bigquery.SchemaField("archivo", "STRING", mode="REQUIRED", description="Nombre del archivo crudo"),
    bigquery.SchemaField("fuente", "STRING", mode="REQUIRED", description="Fuente lógica (carpeta en bronze/)"),
    bigquery.SchemaField("via", "STRING", mode="REQUIRED", description="batch | streaming | cdc"),
    bigquery.SchemaField("sha256", "STRING", mode="REQUIRED", description="sha256 del archivo de origen"),
    bigquery.SchemaField("filas_origen", "INTEGER", mode="REQUIRED", description="Filas de datos en el archivo (sin encabezado)"),
    bigquery.SchemaField("filas_bronze", "INTEGER", mode="NULLABLE", description="Filas escritas en Bronze (se confirma tras la escritura)"),
    bigquery.SchemaField("objetos_bronze", "INTEGER", mode="NULLABLE", description="Objetos escritos en GCS"),
    bigquery.SchemaField("bytes_bronze", "INTEGER", mode="NULLABLE", description="Bytes escritos en GCS"),
    bigquery.SchemaField("ingest_date", "DATE", mode="REQUIRED", description="Partición de Bronze"),
    bigquery.SchemaField("ingest_ts", "TIMESTAMP", mode="REQUIRED", description="Marca de tiempo de la ingesta"),
    bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("estado", "STRING", mode="REQUIRED", description="completado | publicado | omitido"),
    bigquery.SchemaField("detalle", "STRING", mode="NULLABLE"),
]

RUN_METRICS_SCHEMA = [
    bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("etapa", "STRING", mode="REQUIRED", description="p. ej. ingesta_batch, ingesta_streaming, dbt_silver"),
    bigquery.SchemaField("capa", "STRING", mode="NULLABLE", description="bronze | staging | silver | quarantine | gold | features"),
    bigquery.SchemaField("fuente", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("metrica", "STRING", mode="REQUIRED", description="filas | bytes | duracion_s | objetos"),
    bigquery.SchemaField("valor", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("ts", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("detalle", "STRING", mode="NULLABLE"),
]


def asegurar_tablas_ops(client: bigquery.Client | None = None) -> None:
    """Crea ops.ingest_manifest y ops.run_metrics si no existen (idempotente)."""
    client = client or bq_client()
    for table_id, schema in ((MANIFEST_TABLE, MANIFEST_SCHEMA), (RUN_METRICS_TABLE, RUN_METRICS_SCHEMA)):
        try:
            client.get_table(table_id)
        except NotFound:
            tabla = bigquery.Table(table_id, schema=schema)
            tabla.description = "Tabla operativa del pipeline (creada por ingest/common.py)."
            client.create_table(tabla)


def manifiesto_tiene(client: bigquery.Client, archivo: str, sha256: str, estados: Iterable[str] = ("completado", "publicado")) -> bool:
    """¿Este archivo con este sha256 ya fue ingerido por completo?"""
    consulta = f"""
        SELECT COUNT(*) AS n
        FROM `{MANIFEST_TABLE}`
        WHERE archivo = @archivo AND sha256 = @sha256 AND estado IN UNNEST(@estados)
    """
    job = client.query(
        consulta,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("archivo", "STRING", archivo),
                bigquery.ScalarQueryParameter("sha256", "STRING", sha256),
                bigquery.ArrayQueryParameter("estados", "STRING", list(estados)),
            ]
        ),
    )
    return next(iter(job.result())).n > 0


def registrar_manifiesto(client: bigquery.Client, fila: dict) -> None:
    """Inserta una fila en el manifiesto (carga por job, no streaming: sin costo y sin buffer)."""
    fila = {**fila}
    fila.setdefault("ingest_ts", dt.datetime.now(dt.timezone.utc).isoformat())
    fila.setdefault("run_id", run_id_actual())
    fila.setdefault("ingest_date", ingest_date_hoy())
    job = client.load_table_from_json(
        [fila],
        MANIFEST_TABLE,
        job_config=bigquery.LoadJobConfig(schema=MANIFEST_SCHEMA, write_disposition="WRITE_APPEND"),
    )
    job.result()


def registrar_metrica(client: bigquery.Client, etapa: str, metrica: str, valor: float, *, capa: str | None = None,
                      fuente: str | None = None, detalle: str | None = None, run_id: str | None = None) -> None:
    fila = {
        "run_id": run_id or run_id_actual(),
        "etapa": etapa,
        "capa": capa,
        "fuente": fuente,
        "metrica": metrica,
        "valor": float(valor),
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "detalle": detalle,
    }
    job = client.load_table_from_json(
        [fila], RUN_METRICS_TABLE,
        job_config=bigquery.LoadJobConfig(schema=RUN_METRICS_SCHEMA, write_disposition="WRITE_APPEND"),
    )
    job.result()


# ---------------------------------------------------------------------------
# GCS: rutas deterministas de Bronze
# ---------------------------------------------------------------------------
def ruta_bronze(fuente: str, ingest_date: str, nombre_objeto: str) -> str:
    """bronze/<fuente>/ingest_date=YYYY-MM-DD/<nombre_objeto> (partición estilo Hive)."""
    return f"bronze/{fuente}/ingest_date={ingest_date}/{nombre_objeto}"


def subir_archivo(bucket: storage.Bucket, path: Path, destino: str, metadata: dict | None = None) -> storage.Blob:
    blob = bucket.blob(destino)
    if metadata:
        blob.metadata = {k: str(v) for k, v in metadata.items()}
    blob.upload_from_filename(str(path), content_type="text/plain; charset=utf-8")
    blob.reload()
    return blob


def subir_texto(bucket: storage.Bucket, contenido: str, destino: str, metadata: dict | None = None) -> storage.Blob:
    blob = bucket.blob(destino)
    if metadata:
        blob.metadata = {k: str(v) for k, v in metadata.items()}
    blob.upload_from_string(contenido, content_type="application/x-ndjson; charset=utf-8")
    blob.reload()
    return blob
