#!/usr/bin/env python3
"""Reset confirmado del pipeline para la carga desde cero del Proyecto 2.

Pasos (solo con `--confirmar BORRAR-<project_id>`; sin él, o con `--dry-run`, solo lista):
  1. Exporta `ops.run_metrics` e `ops.ingest_manifest` a docs/evidence/p1/*_<ts>.csv (si existen).
  2. Borra los objetos bajo `bronze/` del lago, salvo el marcador exacto `bronze/` (lo gestiona Terraform).
     Nunca toca `landing/`.
  3. Borra todas las TABLAS (también vistas y externas) de bronze, staging, silver, quarantine, gold,
     features, ops y de cualquier dataset `*_recorte`. No borra datasets ni nada de `ops_secrets`.
  4. En la VM (ssh por IAP): borra los tópicos de Kafka y el grupo `bronze-writer`, espera a que los
     tópicos desaparezcan y vacía /opt/red-metropolitana/datos_red/. Se omite con `--sin-vm`.
  5. Escribe docs/evidence/p2/reset_<ts>.md con conteos antes y después.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import shlex
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PROJECT_ID_DEFECTO = "cienciadatos-509301"
DATASETS_LIMPIABLES = ("bronze", "staging", "silver", "quarantine", "gold", "features", "ops")
DATASETS_PROTEGIDOS = ("ops_secrets",)
PREFIJO_BRONZE = "bronze/"
MARCADOR_BRONZE = "bronze/"
GRUPO_CONSUMIDOR = "bronze-writer"
VM_NOMBRE, VM_ZONA = "vm-pipeline", "us-central1-a"
VM_COMPOSE_DIR = "/opt/red-metropolitana/vm"
VM_DATOS_DIR = "/opt/red-metropolitana/datos_red"
KAFKA_BIN = "/opt/kafka/bin"
KAFKA_BOOTSTRAP = "localhost:9092"
ESPERA_TOPICOS_S = 60
TABLAS_A_EXPORTAR = ("run_metrics", "ingest_manifest")


# ---------------------------------------------------------------------------
# Funciones puras
# ---------------------------------------------------------------------------
def token_confirmacion(project_id: str) -> str:
    return f"BORRAR-{project_id}"


def confirmacion_valida(valor: str | None, project_id: str) -> bool:
    return valor is not None and valor == token_confirmacion(project_id)


def objetos_a_borrar(nombres: list[str]) -> list[str]:
    """Objetos bajo `bronze/` salvo el marcador exacto; ignora todo lo que no cuelgue de `bronze/` (p. ej. `landing/`)."""
    return [n for n in nombres if n.startswith(PREFIJO_BRONZE) and n != MARCADOR_BRONZE]


def datasets_a_limpiar(ids: list[str]) -> list[str]:
    """Datasets cuyas tablas se borran: la lista fija (si existen) y los que terminan en `_recorte`."""
    existentes = set(ids)
    fijos = [d for d in DATASETS_LIMPIABLES if d in existentes]
    recortes = sorted(d for d in existentes if d.endswith("_recorte") and d not in DATASETS_PROTEGIDOS)
    return fijos + recortes


def topicos_de_fuentes(fuentes: dict) -> list[str]:
    """Tópicos de Kafka declarados en el catálogo de fuentes (ingest.common.FUENTES)."""
    return sorted({f.topico for f in fuentes.values() if getattr(f, "topico", None)})


def parsear_topicos(salida: str) -> list[str]:
    """Salida de `kafka-topics.sh --list`: un tópico por línea; descarta vacíos, avisos y líneas con espacios."""
    out = []
    for linea in salida.splitlines():
        t = linea.strip()
        if t and " " not in t and not t.startswith(("WARNING", "SLF4J", "Error", "OpenJDK")):
            out.append(t)
    return sorted(out)


def topicos_pendientes(listados: list[str], objetivo: list[str]) -> list[str]:
    return sorted(set(listados) & set(objetivo))


def fmt_n(v) -> str:
    return "-" if v is None else f"{v:,}"


def markdown_reset(modo: str, project_id: str, ts: str, antes: dict, despues: dict | None, exportados: list[str],
                   notas: list[str]) -> str:
    def tabla_conteos(titulo: str, c: dict | None) -> list[str]:
        if c is None:
            return [f"### {titulo}", "", "No aplica (modo dry-run: no se modificó nada).", ""]
        out = [f"### {titulo}", "", "| concepto | cantidad |", "|---|---:|",
               f"| objetos en `bronze/` (sin el marcador) | {fmt_n(c.get('objetos_bronze'))} |"]
        for ds, n in sorted(c.get("tablas", {}).items()):
            out.append(f"| tablas en `{ds}` | {fmt_n(n)} |")
        out.append(f"| tópicos de Kafka | {fmt_n(c.get('topicos'))} |")
        return out + [""]

    out = [f"# Reset del Proyecto 2 ({modo})", "", f"Generado por `scripts/reset_p2.py` · proyecto `{project_id}` · {ts}", "",
           f"Modo: **{modo}**.", ""]
    out += tabla_conteos("Antes", antes)
    out += tabla_conteos("Después", despues)
    out += ["### Exportaciones previas", ""]
    out += [f"- `{e}`" for e in exportados] or ["- ninguna"]
    if notas:
        out += ["", "### Notas", ""] + [f"- {n}" for n in notas]
    out += ["", "Se conservan: el marcador `bronze/`, el prefijo `landing/`, los datasets y `ops_secrets`.", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Efectos (BigQuery, GCS, VM)
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    print(f"[reset] {msg}", flush=True)


def listar_tablas(bq, project_id: str, datasets: list[str]) -> dict[str, list[str]]:
    return {ds: sorted(t.table_id for t in bq.list_tables(f"{project_id}.{ds}")) for ds in datasets}


def exportar_ops(bq, project_id: str, ts: str, salida: Path, dry: bool) -> list[str]:
    from google.api_core.exceptions import NotFound
    hechos = []
    for tabla in TABLAS_A_EXPORTAR:
        destino = salida / f"{tabla}_{ts}.csv"
        try:
            t = bq.get_table(f"{project_id}.ops.{tabla}")
        except NotFound:
            log(f"ops.{tabla} no existe: nada que exportar")
            continue
        except Exception as exc:  # noqa: BLE001
            if not dry:
                raise
            log(f"AVISO (dry-run): no se pudo leer ops.{tabla}: {str(exc).splitlines()[0][:140]}")
            continue
        if dry:
            log(f"[dry-run] exportaría ops.{tabla} ({t.num_rows} filas) a {destino}")
            continue
        salida.mkdir(parents=True, exist_ok=True)
        campos = [c.name for c in t.schema]
        with destino.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(campos)
            n = 0
            for fila in bq.list_rows(t):  # tabledata.list: no crea jobs
                w.writerow([fila[c] for c in campos])
                n += 1
        log(f"exportado ops.{tabla} -> {destino} ({n} filas)")
        hechos.append(str(destino.relative_to(REPO)) if destino.is_relative_to(REPO) else str(destino))
    return hechos


def nombres_bronze(gcs, bucket: str) -> list[str]:
    return [b.name for b in gcs.bucket(bucket).list_blobs(prefix=PREFIJO_BRONZE)]


def borrar_objetos(gcs, bucket: str, nombres: list[str]) -> int:
    b = gcs.bucket(bucket)
    n = 0
    for i in range(0, len(nombres), 100):
        with gcs.batch():
            for nombre in nombres[i:i + 100]:
                b.blob(nombre).delete()
        n += len(nombres[i:i + 100])
    return n


def ssh(project_id: str, comando: str, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gcloud", "compute", "ssh", VM_NOMBRE, "--zone", VM_ZONA, "--project", project_id,
         "--tunnel-through-iap", "--quiet", "--command", comando],
        capture_output=True, text=True, timeout=timeout)


def kafka_exec(args: str) -> str:
    return f"cd {VM_COMPOSE_DIR} && sudo docker compose exec -T kafka {KAFKA_BIN}/{args}"


def listar_topicos_vm(project_id: str) -> list[str] | None:
    r = ssh(project_id, kafka_exec(f"kafka-topics.sh --bootstrap-server {KAFKA_BOOTSTRAP} --list"))
    if r.returncode != 0:
        log(f"no se pudo listar tópicos en la VM: {r.stderr.strip().splitlines()[-1:] or r.returncode}")
        return None
    return parsear_topicos(r.stdout)


def limpiar_vm(project_id: str, topicos: list[str]) -> list[str]:
    notas = []
    for t in topicos:
        r = ssh(project_id, kafka_exec(f"kafka-topics.sh --bootstrap-server {KAFKA_BOOTSTRAP} --delete --topic {shlex.quote(t)}"))
        log(f"borrar tópico {t}: {'ok' if r.returncode == 0 else 'ya no existía o falló (tolerado)'}")
    r = ssh(project_id, kafka_exec(f"kafka-consumer-groups.sh --bootstrap-server {KAFKA_BOOTSTRAP} --delete --group {GRUPO_CONSUMIDOR}"))
    log(f"borrar grupo {GRUPO_CONSUMIDOR}: {'ok' if r.returncode == 0 else 'no existía o falló (tolerado)'}")
    limite = time.time() + ESPERA_TOPICOS_S
    while True:
        listados = listar_topicos_vm(project_id)
        pend = topicos_pendientes(listados or [], topicos)
        if listados is not None and not pend:
            break
        if time.time() > limite:
            notas.append(f"los tópicos {pend} seguían listados tras {ESPERA_TOPICOS_S} s")
            log(f"AVISO: {notas[-1]}")
            break
        time.sleep(3)
    r = ssh(project_id, f"sudo find {VM_DATOS_DIR} -mindepth 1 -delete")
    if r.returncode == 0:
        log(f"vaciado {VM_DATOS_DIR}")
    else:
        notas.append(f"no se pudo vaciar {VM_DATOS_DIR}: {r.stderr.strip()[:200]}")
        log(f"AVISO: {notas[-1]}")
    return notas


def tomar_conteos(bq, gcs, project_id: str, bucket: str, datasets: list[str], con_vm: bool, tolerante: bool = False) -> dict:
    """Conteos de objetos, tablas y tópicos. En dry-run (`tolerante`) un error de permisos se informa y se sigue."""
    try:
        tablas = {ds: len(ts) for ds, ts in listar_tablas(bq, project_id, datasets).items()}
    except Exception as exc:  # noqa: BLE001
        if not tolerante:
            raise
        log(f"AVISO: no se pudieron listar tablas: {str(exc).splitlines()[0]}")
        tablas = {}
    top = None
    if con_vm:
        l = listar_topicos_vm(project_id)
        top = None if l is None else len(l)
    try:
        n_obj = len(objetos_a_borrar(nombres_bronze(gcs, bucket)))
    except Exception as exc:  # noqa: BLE001
        if not tolerante:
            raise
        log(f"AVISO: no se pudieron listar objetos de bronze/: {str(exc).splitlines()[0][:160]}")
        n_obj = None
    return {"objetos_bronze": n_obj, "tablas": tablas, "topicos": top}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirmar", help="debe ser exactamente BORRAR-<project_id>")
    ap.add_argument("--dry-run", action="store_true", help="solo lista; no borra ni exporta")
    ap.add_argument("--sin-vm", action="store_true", help="omite Kafka y los datos de la VM")
    ap.add_argument("--project", default=PROJECT_ID_DEFECTO)
    ap.add_argument("--salida-dir", type=Path, default=REPO / "docs" / "evidence" / "p2")
    ap.add_argument("--exportes-dir", type=Path, default=REPO / "docs" / "evidence" / "p1")
    args = ap.parse_args(argv)

    if args.confirmar is not None and not confirmacion_valida(args.confirmar, args.project):
        print(f"ERROR: --confirmar debe ser exactamente {token_confirmacion(args.project)}", file=sys.stderr)
        return 2
    real = confirmacion_valida(args.confirmar, args.project) and not args.dry_run
    modo = "real" if real else "dry-run"
    if not real and not args.dry_run:
        log("sin --confirmar: se ejecuta en modo dry-run")

    from ingest import common
    bq, gcs = common.bq_client(), common.gcs_client()
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    ids = [d.dataset_id for d in bq.list_datasets()]
    datasets = datasets_a_limpiar(ids)
    log(f"modo={modo} proyecto={args.project} bucket={common.LAKE_BUCKET} datasets={datasets}")
    topicos = topicos_de_fuentes(common.FUENTES)

    antes = tomar_conteos(bq, gcs, args.project, common.LAKE_BUCKET, datasets, not args.sin_vm, tolerante=not real)
    log(f"antes: {antes}")
    notas: list[str] = []

    exportados = exportar_ops(bq, args.project, ts, args.exportes_dir, dry=not real)

    try:
        objs = objetos_a_borrar(nombres_bronze(gcs, common.LAKE_BUCKET))
    except Exception:  # noqa: BLE001
        if real:
            raise
        objs = []
    if real:
        log(f"borrando {borrar_objetos(gcs, common.LAKE_BUCKET, objs)} objetos de bronze/")
    else:
        log(f"[dry-run] borraría {len(objs)} objetos de bronze/ (se conserva el marcador {MARCADOR_BRONZE})")

    try:
        por_dataset = listar_tablas(bq, args.project, datasets)
    except Exception:  # noqa: BLE001
        if real:
            raise
        por_dataset = {}
    for ds, tablas in por_dataset.items():
        if real:
            for t in tablas:
                bq.delete_table(f"{args.project}.{ds}.{t}", not_found_ok=True)
            log(f"{ds}: {len(tablas)} tablas borradas")
        else:
            log(f"[dry-run] {ds}: borraría {len(tablas)} tablas {tablas[:12]}{'...' if len(tablas) > 12 else ''}")

    if args.sin_vm:
        notas.append("VM omitida (--sin-vm)")
    elif real:
        notas += limpiar_vm(args.project, topicos)
    else:
        log(f"[dry-run] borraría tópicos {topicos}, grupo {GRUPO_CONSUMIDOR} y vaciaría {VM_DATOS_DIR}/*")

    despues = tomar_conteos(bq, gcs, args.project, common.LAKE_BUCKET, datasets, not args.sin_vm) if real else None
    if despues:
        log(f"después: {despues}")

    args.salida_dir.mkdir(parents=True, exist_ok=True)
    informe = args.salida_dir / f"reset_{ts}.md"
    informe.write_text(markdown_reset(modo, args.project, ts, antes, despues, exportados, notas), encoding="utf-8")
    log(f"informe: {informe}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
