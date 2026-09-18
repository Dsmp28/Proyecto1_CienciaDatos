"""Deriva las claves internas de HMAC-SHA256 desde la sal secreta y las publica en BigQuery.

Implementa ADR-007. BigQuery no tiene función HMAC, pero
    HMAC(K, m) = SHA256( (K' ⊕ opad) || SHA256( (K' ⊕ ipad) || m ) )
con K' = sal rellenada con ceros a 64 bytes. Los dos bloques (K' ⊕ ipad) y (K' ⊕ opad) se calculan
aquí, en Python, leyendo la sal de Secret Manager con la cuenta de servicio de la VM, y se escriben
en la tabla restringida `ops_secrets.hmac_key`. El macro `hmac_sha256()` de dbt los toma con una
subconsulta escalar, de modo que la sal nunca aparece en el texto de las consultas ni en el historial
de jobs de BigQuery. Idempotente: si la tabla ya tiene la versión vigente del secreto, no hace nada.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import hmac
import sys

from google.api_core.exceptions import NotFound
from google.cloud import bigquery, secretmanager

from ingest.common import PROJECT_ID, REGION, bq_client

SECRET_ID = "hmac-salt"
TABLE_ID = f"{PROJECT_ID}.ops_secrets.hmac_key"
SCHEMA = [
    bigquery.SchemaField("key_id", "STRING", mode="REQUIRED", description="Nombre del secreto de origen"),
    bigquery.SchemaField("version", "STRING", mode="REQUIRED", description="Versión del secreto en Secret Manager"),
    bigquery.SchemaField("k_ipad", "BYTES", mode="REQUIRED", description="(K' XOR ipad), 64 bytes"),
    bigquery.SchemaField("k_opad", "BYTES", mode="REQUIRED", description="(K' XOR opad), 64 bytes"),
    bigquery.SchemaField("huella", "STRING", mode="REQUIRED", description="sha256(sal) truncado: identifica la sal sin revelarla"),
    bigquery.SchemaField("creado_ts", "TIMESTAMP", mode="REQUIRED"),
]


def derivar_bloques(sal: bytes) -> tuple[bytes, bytes]:
    """Bloques internos de HMAC (RFC 2104) para SHA-256 (bloque de 64 bytes)."""
    if len(sal) > 64:
        sal = hashlib.sha256(sal).digest()
    k = sal.ljust(64, b"\x00")
    k_ipad = bytes(b ^ 0x36 for b in k)
    k_opad = bytes(b ^ 0x5C for b in k)
    return k_ipad, k_opad


def hmac_python(sal: bytes, mensaje: bytes) -> str:
    """Referencia para verificar el macro de dbt."""
    return hmac.new(sal, mensaje, hashlib.sha256).hexdigest()


def leer_sal() -> tuple[bytes, str]:
    cliente = secretmanager.SecretManagerServiceClient()
    nombre = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/latest"
    resp = cliente.access_secret_version(request={"name": nombre})
    version = resp.name.rsplit("/", 1)[-1]
    datos = resp.payload.data
    # Terraform guarda la sal como base64 de 32 bytes aleatorios; se usa el binario decodificado.
    try:
        sal = base64.b64decode(datos, validate=True)
    except Exception:
        sal = datos
    return sal, version


def asegurar_tabla(client: bigquery.Client) -> None:
    try:
        client.get_table(TABLE_ID)
    except NotFound:
        tabla = bigquery.Table(TABLE_ID, schema=SCHEMA)
        tabla.description = "Claves derivadas de la sal HMAC (ADR-007). Acceso restringido a la SA del pipeline."
        client.create_table(tabla)


def version_publicada(client: bigquery.Client) -> str | None:
    sql = f"SELECT version FROM `{TABLE_ID}` WHERE key_id = @k ORDER BY creado_ts DESC LIMIT 1"
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("k", "STRING", SECRET_ID)])
    filas = list(client.query(sql, job_config=cfg).result())
    return filas[0].version if filas else None


def publicar(client: bigquery.Client, sal: bytes, version: str) -> None:
    k_ipad, k_opad = derivar_bloques(sal)
    fila = {
        "key_id": SECRET_ID,
        "version": version,
        "k_ipad": base64.b64encode(k_ipad).decode(),
        "k_opad": base64.b64encode(k_opad).decode(),
        "huella": hashlib.sha256(sal).hexdigest()[:16],
        "creado_ts": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    # Se reemplaza el contenido completo: una sola clave vigente (idempotente).
    job = client.load_table_from_json(
        [fila], TABLE_ID,
        job_config=bigquery.LoadJobConfig(schema=SCHEMA, write_disposition="WRITE_TRUNCATE"),
    )
    job.result()


def verificar(client: bigquery.Client, sal: bytes, mensaje: str = "TM|TC-00000001") -> bool:
    """Compara HMAC calculado por BigQuery (misma fórmula del macro) con el de Python."""
    sql = f"""
        SELECT TO_HEX(SHA256(CONCAT(k.k_opad, SHA256(CONCAT(k.k_ipad, CAST(@m AS BYTES)))))) AS h
        FROM `{TABLE_ID}` k WHERE k.key_id = @k
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("m", "STRING", mensaje),
        bigquery.ScalarQueryParameter("k", "STRING", SECRET_ID),
    ])
    h_bq = next(iter(client.query(sql, job_config=cfg).result())).h
    return h_bq == hmac_python(sal, mensaje.encode())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--forzar", action="store_true", help="republica aunque la versión ya esté")
    ap.add_argument("--verificar", action="store_true", help="comprueba HMAC BigQuery == HMAC Python")
    args = ap.parse_args(argv)

    client = bq_client()
    asegurar_tabla(client)
    sal, version = leer_sal()
    actual = version_publicada(client)
    if actual == version and not args.forzar:
        print(f"ops_secrets.hmac_key ya tiene la versión {version} del secreto {SECRET_ID}: sin cambios.")
    else:
        publicar(client, sal, version)
        print(f"Publicada la versión {version} del secreto {SECRET_ID} en {TABLE_ID} (huella {hashlib.sha256(sal).hexdigest()[:16]}).")
    if args.verificar:
        ok = verificar(client, sal)
        print("Verificación HMAC BigQuery == Python:", "OK" if ok else "FALLA")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
