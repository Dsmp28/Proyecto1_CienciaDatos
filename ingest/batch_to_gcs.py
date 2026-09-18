"""Ingesta batch y CDC a Bronze: copia byte a byte de cada archivo a GCS con idempotencia.

Uso:
    python ingest/batch_to_gcs.py [--via batch|cdc|todas] [--fuente <nombre>] [--json]

Para cada fuente de las vías pedidas (ADR-002 y ADR-006):
1. sha256 y filas de datos del archivo local.
2. Si `ops.ingest_manifest` ya tiene (archivo, sha256) en estado completado/publicado,
   se registra una fila "omitido" y NO se sube nada (Bronze se acumula sin duplicarse).
3. Si no, se sube a `bronze/<fuente>/ingest_date=YYYY-MM-DD/<archivo>` con metadata
   (sha256, run_id, filas_origen, via), se verifica tamaño y md5 contra el blob y se
   registra una fila "completado" con filas_bronze = filas_origen (copia byte a byte),
   objetos_bronze = 1 y bytes_bronze.
4. Métricas en `ops.run_metrics`: filas, bytes y duracion_s por fuente.

Con `--json` la tabla va a stderr y el resultado JSON a stdout (para XCom de Airflow).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ingest import common  # noqa: E402
from ingest.common import Fuente  # noqa: E402

VIAS_VALIDAS = ("batch", "cdc")


# ---------------------------------------------------------------------------
# Funciones puras (probadas en tests/test_ingest_batch.py)
# ---------------------------------------------------------------------------
def decidir_accion(en_manifiesto: bool) -> tuple[str, str | None]:
    """Decisión de idempotencia: ("omitido", detalle) si el sha256 ya fue ingerido; ("subir", None) si no."""
    if en_manifiesto:
        return "omitido", "sha256 ya ingerido"
    return "subir", None


def md5_base64(path: Path, bloque: int = 1 << 20) -> str:
    """md5 del archivo en base64, el mismo formato que GCS devuelve en `blob.md5_hash`."""
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(bloque), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode("ascii")


def verificar_copia(bytes_local: int, md5_local: str, bytes_blob: int | None, md5_blob: str | None) -> None:
    """Comprueba que el objeto en GCS es byte a byte igual al archivo local; lanza RuntimeError si no."""
    if bytes_blob != bytes_local:
        raise RuntimeError(f"Tamaño en GCS ({bytes_blob}) distinto del local ({bytes_local})")
    if md5_blob is not None and md5_blob != md5_local:
        raise RuntimeError(f"md5 en GCS ({md5_blob}) distinto del local ({md5_local})")


def seleccionar_fuentes(via: str, fuente: str | None) -> list[Fuente]:
    """Fuentes de las vías batch/cdc; `fuente` (nombre lógico o archivo) filtra a una sola."""
    vias = VIAS_VALIDAS if via == "todas" else (via,)
    seleccion = [f for v in vias for f in common.fuentes_por_via(v)]
    if fuente:
        seleccion = [f for f in seleccion if fuente in (f.fuente, f.archivo)]
        if not seleccion:
            raise SystemExit(f"Fuente {fuente!r} no existe en las vías {vias}")
    return seleccion


def formatear_tabla(filas: list[dict]) -> str:
    ancho = max(len(f["archivo"]) for f in filas) if filas else 10
    cab = f"{'archivo':<{ancho}} | {'filas_origen':>12} | {'filas_bronze':>12} | {'estado':<10} | objeto"
    out = [cab, "-" * len(cab)]
    for f in filas:
        fb = f["filas_bronze"] if f["filas_bronze"] is not None else "-"
        out.append(f"{f['archivo']:<{ancho}} | {f['filas_origen']:>12} | {fb:>12} | {f['estado']:<10} | {f['objeto'] or '-'}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Ingesta de una fuente
# ---------------------------------------------------------------------------
def ingerir_fuente(fuente: Fuente, bq, bucket, datos_dir: Path, ingest_date: str, run_id: str) -> dict:
    t0 = time.monotonic()
    path = datos_dir / fuente.archivo
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}; ejecuta ingest/generar_o_verificar.py")

    sha256 = common.sha256_archivo(path)
    filas_origen = common.contar_filas(path, fuente.formato)
    bytes_local = path.stat().st_size
    etapa = f"ingesta_{fuente.via}"
    destino = common.ruta_bronze(fuente.fuente, ingest_date, fuente.archivo)

    accion, detalle = decidir_accion(common.manifiesto_tiene(bq, fuente.archivo, sha256))
    base = {
        "archivo": fuente.archivo,
        "fuente": fuente.fuente,
        "via": fuente.via,
        "sha256": sha256,
        "filas_origen": filas_origen,
        "ingest_date": ingest_date,
        "run_id": run_id,
    }

    if accion == "omitido":
        common.registrar_manifiesto(bq, {**base, "estado": "omitido", "detalle": detalle})
        resultado = {**base, "estado": "omitido", "detalle": detalle, "filas_bronze": None,
                     "objeto": None, "bytes_bronze": 0}
    else:
        blob = common.subir_archivo(
            bucket, path, destino,
            metadata={"sha256": sha256, "run_id": run_id, "filas_origen": filas_origen, "via": fuente.via,
                      "archivo": fuente.archivo, "ingest_date": ingest_date},
        )
        verificar_copia(bytes_local, md5_base64(path), blob.size, blob.md5_hash)
        common.registrar_manifiesto(bq, {
            **base, "estado": "completado", "filas_bronze": filas_origen, "objetos_bronze": 1,
            "bytes_bronze": blob.size, "detalle": f"gs://{bucket.name}/{destino}",
        })
        resultado = {**base, "estado": "completado", "detalle": None, "filas_bronze": filas_origen,
                     "objeto": f"gs://{bucket.name}/{destino}", "bytes_bronze": blob.size}

    duracion = time.monotonic() - t0
    resultado["duracion_s"] = round(duracion, 3)
    for metrica, valor in (("filas", filas_origen), ("bytes", resultado["bytes_bronze"]), ("duracion_s", duracion)):
        common.registrar_metrica(bq, etapa, metrica, valor, capa="bronze", fuente=fuente.fuente,
                                 detalle=resultado["estado"], run_id=run_id)
    return resultado


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--via", choices=("batch", "cdc", "todas"), default="todas")
    ap.add_argument("--fuente", help="nombre lógico o archivo de una sola fuente")
    ap.add_argument("--json", action="store_true", help="resultado JSON en stdout (tabla a stderr)")
    args = ap.parse_args(argv)

    fuentes = seleccionar_fuentes(args.via, args.fuente)
    datos_dir = common.DATOS_DIR if common.DATOS_DIR.is_absolute() else REPO / common.DATOS_DIR
    ingest_date = common.ingest_date_hoy()
    run_id = common.run_id_actual()

    bq = common.bq_client()
    common.asegurar_tablas_ops(bq)
    bucket = common.gcs_client().bucket(common.LAKE_BUCKET)

    salida_tabla = sys.stderr if args.json else sys.stdout
    print(f"[batch] run_id={run_id} ingest_date={ingest_date} bucket={common.LAKE_BUCKET} fuentes={len(fuentes)}",
          file=salida_tabla)
    filas = []
    for f in fuentes:
        r = ingerir_fuente(f, bq, bucket, datos_dir, ingest_date, run_id)
        print(f"[batch] {f.archivo}: {r['estado']} ({r['duracion_s']} s)", file=salida_tabla)
        filas.append(r)

    print(formatear_tabla(filas), file=salida_tabla)
    if args.json:
        print(json.dumps({"run_id": run_id, "ingest_date": ingest_date, "fuentes": filas}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
