"""Landing de los datos crudos en GCS: `gs://<lake>/landing/datos_red/<version>/`.

Es la copia de referencia de los 9 archivos entregados (no se versionan en git). La VM y
Airflow la descargan de aquí en lugar de depender de un generador.

Uso:
    python -m ingest.landing subir --origen docs/P2_datos_red/datos_red --version v2
    python -m ingest.landing descargar --version v2 --destino datos_red [--todo]

`subir` es idempotente: un blob existente con el mismo sha256 (metadata) no se vuelve a subir.
Además escribe `MANIFEST.json` {version, generado_ts, archivos:{nombre:{sha256, filas_datos, bytes}}}.
`descargar` baja solo los archivos cuyo sha256 local no coincide con el MANIFEST (o que faltan) y
verifica el sha256 tras descargar.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ingest import common  # noqa: E402
from ingest.common import FUENTES, LAKE_BUCKET, contar_filas, sha256_archivo  # noqa: E402

PREFIJO = "landing/datos_red"
MANIFEST = "MANIFEST.json"
PATRON_VERSION = re.compile(r"^[a-z0-9_-]{1,40}$")


# ---------------------------------------------------------------------------
# Funciones puras (probadas en tests/test_landing.py, sin red)
# ---------------------------------------------------------------------------
def validar_version(version: str) -> str:
    if not PATRON_VERSION.match(version or ""):
        raise ValueError(f"version={version!r} inválida (usa ^[a-z0-9_-]{{1,40}}$)")
    return version


def prefijo_version(version: str) -> str:
    return f"{PREFIJO}/{validar_version(version)}"


def ruta_blob(version: str, archivo: str) -> str:
    return f"{prefijo_version(version)}/{archivo}"


def construir_manifest(version: str, huellas: dict[str, dict], generado_ts: str | None = None) -> dict:
    return {
        "version": version,
        "generado_ts": generado_ts or dt.datetime.now(dt.timezone.utc).isoformat(),
        "archivos": {n: {"sha256": h["sha256"], "filas_datos": h["filas_datos"], "bytes": h["bytes"]}
                     for n, h in sorted(huellas.items())},
    }


def decidir_subida(sha_local: str, sha_remoto: str | None) -> bool:
    """True si hay que subir: el blob no existe o su sha256 (metadata) difiere."""
    return sha_remoto is None or sha_remoto != sha_local


def nombres_permitidos(manifest: dict) -> list[str]:
    """Nombres del manifest que pertenecen al catálogo FUENTES.

    El MANIFEST llega del bucket (dato externo): solo se aceptan los 9 nombres del catálogo, sin
    separadores de ruta ni `..`, para que ningún manifest manipulado escriba fuera de `destino`.
    """
    salida = []
    for n in sorted(manifest.get("archivos", {})):
        if n in FUENTES and "/" not in n and "\\" not in n and ".." not in n and n == Path(n).name:
            salida.append(n)
    return salida


def archivos_a_descargar(manifest: dict, sha_locales: dict[str, str | None]) -> list[str]:
    """Archivos del catálogo presentes en el manifest cuyo sha256 local falta o no coincide (orden alfabético)."""
    return [n for n in nombres_permitidos(manifest)
            if sha_locales.get(n) != manifest["archivos"][n]["sha256"]]


# ---------------------------------------------------------------------------
# Efectos
# ---------------------------------------------------------------------------
def _bucket():
    return common.gcs_client().bucket(LAKE_BUCKET)


def subir(origen: Path, version: str) -> dict:
    """Copia los 9 archivos de FUENTES a landing y escribe el MANIFEST. Devuelve el manifest."""
    origen = Path(origen)
    faltan = [n for n in FUENTES if not (origen / n).exists()]
    if faltan:
        raise SystemExit(f"Faltan archivos en {origen}: {faltan}")
    bucket = _bucket()
    huellas: dict[str, dict] = {}
    for nombre, fuente in FUENTES.items():
        p = origen / nombre
        sha = sha256_archivo(p)
        huellas[nombre] = {"sha256": sha, "filas_datos": contar_filas(p, fuente.formato),
                           "bytes": p.stat().st_size}
        blob = bucket.get_blob(ruta_blob(version, nombre))
        remoto = (blob.metadata or {}).get("sha256") if blob else None
        if blob is not None and blob.size == huellas[nombre]["bytes"] and not decidir_subida(sha, remoto):
            print(f"[landing] omitido (ya existe): {nombre}", file=sys.stderr)
            continue
        blob = bucket.blob(ruta_blob(version, nombre))
        blob.metadata = {"sha256": sha}
        blob.upload_from_filename(str(p))
        print(f"[landing] subido: {nombre} ({huellas[nombre]['bytes']} bytes)", file=sys.stderr)
    manifest = construir_manifest(version, huellas)
    bucket.blob(ruta_blob(version, MANIFEST)).upload_from_string(
        json.dumps(manifest, indent=2, ensure_ascii=False), content_type="application/json")
    print(f"[landing] MANIFEST escrito: gs://{LAKE_BUCKET}/{ruta_blob(version, MANIFEST)}", file=sys.stderr)
    return manifest


def leer_manifest(version: str) -> dict:
    blob = _bucket().blob(ruta_blob(version, MANIFEST))
    if not blob.exists():
        raise SystemExit(f"No existe gs://{LAKE_BUCKET}/{ruta_blob(version, MANIFEST)}; corre `make landing-subir`")
    return json.loads(blob.download_as_text())


def descargar(version: str, destino: Path, solo_faltantes: bool = True) -> list[str]:
    """Baja de landing los archivos cuyo sha256 local no coincide con el MANIFEST. Devuelve los bajados."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    manifest = leer_manifest(version)
    if solo_faltantes:
        locales = {n: (sha256_archivo(destino / n) if (destino / n).exists() else None)
                   for n in manifest["archivos"]}
        pendientes = archivos_a_descargar(manifest, locales)
    else:
        pendientes = nombres_permitidos(manifest)
    bucket = _bucket()
    for nombre in pendientes:
        final = destino / nombre
        tmp = destino / f".{nombre}.part"
        bucket.blob(ruta_blob(version, nombre)).download_to_filename(str(tmp))
        sha = sha256_archivo(tmp)
        esperado = manifest["archivos"][nombre]["sha256"]
        if sha != esperado:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"sha256 tras descargar {nombre}: {sha} != {esperado}")
        tmp.replace(final)
        print(f"[landing] descargado y verificado: {nombre}", file=sys.stderr)
    if not pendientes:
        print("[landing] nada que descargar: todo coincide con el MANIFEST", file=sys.stderr)
    return pendientes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("subir", help="sube los 9 archivos y el MANIFEST")
    s.add_argument("--origen", required=True, type=Path)
    s.add_argument("--version", default="v2")
    d = sub.add_parser("descargar", help="baja los archivos que falten o difieran")
    d.add_argument("--version", default="v2")
    d.add_argument("--destino", required=True, type=Path)
    d.add_argument("--todo", action="store_true", help="baja todo aunque coincida")
    args = ap.parse_args(argv)
    validar_version(args.version)
    if args.cmd == "subir":
        subir(args.origen, args.version)
    else:
        descargar(args.version, args.destino, solo_faltantes=not args.todo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
