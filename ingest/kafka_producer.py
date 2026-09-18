"""Productor de Kafka: publica un CSV de operación línea por línea (vía streaming).

Fuentes: las del catálogo `FUENTES` con `via == "streaming"` (Transmetro y Aerómetro).
Por cada archivo:

1. Calcula sha256 y filas de datos (`ingest/common.py`).
2. Idempotencia (ADR-006a): si `ops.ingest_manifest` ya tiene (archivo, sha256) en
   estado `publicado` o `completado`, imprime "omitido" y NO publica nada.
3. Si no está: crea el tópico con AdminClient (3 particiones, replicación 1; si ya
   existe se ignora) y publica cada línea de datos, sin encabezado y sin salto de
   línea final, como `value` UTF-8. `key = archivo`: todas las líneas de un archivo
   caen en la misma partición, con lo que Kafka preserva el orden del archivo.
   Headers por mensaje: `archivo`, `linea_num` (1 = primera fila de datos),
   `sha256_archivo`, `run_id`.
4. `flush()` y registro en el manifiesto con estado `publicado` (filas_bronze NULL:
   lo confirma el consumidor al escribir en GCS) y métricas en `ops.run_metrics`.

Configuración del productor: `enable.idempotence` (sin duplicados por reintentos
del propio productor), `acks=all`, `linger.ms=20`, lotes grandes y compresión lz4.

Republicación forzada (`--forzar`): salta la comprobación del manifiesto y registra
estado `publicado` con detalle `forzado`. Bronze recibirá nuevas líneas con otro
offset pero con la misma terna (archivo, linea_num, sha256_archivo): Staging
deduplica por esa terna y Bronze conserva el histórico (ver kafka_consumer_gcs.py).

Modo de prueba (`--dry-run` o `INGEST_DRY_RUN=1`): no consulta ni escribe el
manifiesto ni las métricas (asume que el archivo no está ingerido); solo Kafka.

Uso:
    python -m ingest.kafka_producer                       # las dos fuentes streaming
    python -m ingest.kafka_producer --fuente transmetro_validaciones.csv
    python -m ingest.kafka_producer --bootstrap localhost:9092 --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from confluent_kafka import KafkaError, KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from ingest import common
from ingest.common import FUENTES, Fuente, fuentes_por_via

PARTICIONES_POR_DEFECTO = 3
ETAPA = "ingesta_streaming_producer"


# ---------------------------------------------------------------------------
# Funciones puras (probadas sin Kafka)
# ---------------------------------------------------------------------------
def construir_headers(archivo: str, linea_num: int, sha256: str, run_id: str) -> list[tuple[str, str]]:
    """Headers de un mensaje. Kafka los transporta como bytes; aquí van como str UTF-8."""
    return [
        ("archivo", archivo),
        ("linea_num", str(linea_num)),
        ("sha256_archivo", sha256),
        ("run_id", run_id),
    ]


def iterar_lineas_datos(path: Path) -> Iterator[tuple[int, str]]:
    """(linea_num, línea) de cada fila de datos: salta el encabezado y las líneas vacías.

    `linea_num` empieza en 1 en la primera fila de datos; cuenta solo filas no vacías,
    igual que `common.contar_filas`, para que ambos conteos coincidan.
    """
    with path.open("r", encoding="utf-8", newline="") as f:
        next(f, None)  # encabezado
        n = 0
        for linea in f:
            linea = linea.rstrip("\r\n")
            if not linea.strip():
                continue
            n += 1
            yield n, linea


def resolver_fuentes(nombres: list[str] | None) -> list[Fuente]:
    """Acepta nombres de archivo o de fuente lógica; sin argumentos, las dos streaming."""
    if not nombres:
        return fuentes_por_via("streaming")
    por_fuente = {f.fuente: f for f in FUENTES.values()}
    salida: list[Fuente] = []
    for nombre in nombres:
        f = FUENTES.get(nombre) or por_fuente.get(nombre)
        if f is None:
            raise SystemExit(f"Fuente desconocida: {nombre}. Opciones: {sorted(FUENTES)}")
        if f.via != "streaming" or not f.topico:
            raise SystemExit(f"{f.archivo} no es una fuente streaming (vía {f.via})")
        salida.append(f)
    return salida


def config_productor(bootstrap: str) -> dict:
    return {
        "bootstrap.servers": bootstrap,
        "enable.idempotence": True,
        "acks": "all",
        "linger.ms": 20,
        "batch.size": 1_000_000,
        "queue.buffering.max.messages": 200_000,
        "queue.buffering.max.kbytes": 262_144,
        "compression.type": "lz4",
    }


# ---------------------------------------------------------------------------
# Kafka
# ---------------------------------------------------------------------------
@dataclass
class EstadoEntrega:
    """Acumula lo que reportan los callbacks de entrega."""
    entregados: int = 0
    particiones: set[int] = field(default_factory=set)
    errores: list[str] = field(default_factory=list)

    def callback(self, err, msg) -> None:
        if err is not None:
            self.errores.append(str(err))
            return
        self.entregados += 1
        self.particiones.add(msg.partition())


def crear_topico_si_no_existe(bootstrap: str, topico: str, particiones: int = PARTICIONES_POR_DEFECTO) -> bool:
    """Crea el tópico (replicación 1). Devuelve True si lo creó, False si ya existía."""
    admin = AdminClient({"bootstrap.servers": bootstrap})
    futuros = admin.create_topics([NewTopic(topico, num_partitions=particiones, replication_factor=1)], operation_timeout=30)
    try:
        futuros[topico].result()
        return True
    except KafkaException as e:
        if e.args[0].code() == KafkaError.TOPIC_ALREADY_EXISTS:
            return False
        raise


def publicar_archivo(productor: Producer, fuente: Fuente, path: Path, sha256: str, run_id: str) -> EstadoEntrega:
    """Publica las filas de datos de `path` en `fuente.topico` y espera la entrega de todas."""
    estado = EstadoEntrega()
    clave = fuente.archivo.encode("utf-8")
    for linea_num, linea in iterar_lineas_datos(path):
        headers = construir_headers(fuente.archivo, linea_num, sha256, run_id)
        valor = linea.encode("utf-8")
        while True:
            try:
                productor.produce(fuente.topico, value=valor, key=clave, headers=headers, on_delivery=estado.callback)
                break
            except BufferError:
                # Cola local llena: atender callbacks (vacía la cola) y reintentar.
                productor.poll(0.5)
        productor.poll(0)
    pendientes = productor.flush(timeout=300)
    if pendientes:
        estado.errores.append(f"{pendientes} mensajes sin confirmar tras flush()")
    return estado


# ---------------------------------------------------------------------------
# Orquestación por archivo
# ---------------------------------------------------------------------------
def procesar_fuente(fuente: Fuente, *, bootstrap: str, productor: Producer, bq, datos_dir: Path,
                    dry_run: bool, forzar: bool, particiones: int, run_id: str) -> dict:
    path = datos_dir / fuente.archivo
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}")
    sha = common.sha256_archivo(path)
    filas = common.contar_filas(path, fuente.formato)

    if not dry_run and not forzar and common.manifiesto_tiene(bq, fuente.archivo, sha):
        print(f"omitido  {fuente.archivo}: sha256={sha[:12]}… ya publicado (manifiesto)")
        return {"archivo": fuente.archivo, "estado": "omitido", "filas": filas, "topico": fuente.topico, "segundos": 0.0}

    creado = crear_topico_si_no_existe(bootstrap, fuente.topico, particiones)
    print(f"tópico   {fuente.topico}: {'creado' if creado else 'ya existía'} ({particiones} particiones)")

    t0 = time.perf_counter()
    entrega = publicar_archivo(productor, fuente, path, sha, run_id)
    segundos = time.perf_counter() - t0
    if entrega.errores:
        raise RuntimeError(f"{fuente.archivo}: {len(entrega.errores)} errores de entrega; primero: {entrega.errores[0]}")
    if entrega.entregados != filas:
        raise RuntimeError(f"{fuente.archivo}: entregados {entrega.entregados} != filas de datos {filas}")

    particiones_txt = ",".join(str(p) for p in sorted(entrega.particiones))
    detalle = f"tópico={fuente.topico}, partición(es)={particiones_txt}"
    if forzar:
        detalle = f"forzado; {detalle}"

    if not dry_run:
        common.registrar_manifiesto(bq, {
            "archivo": fuente.archivo,
            "fuente": fuente.fuente,
            "via": fuente.via,
            "sha256": sha,
            "filas_origen": filas,
            "filas_bronze": None,
            "objetos_bronze": None,
            "bytes_bronze": None,
            "estado": "publicado",
            "detalle": detalle,
            "run_id": run_id,
        })
        common.registrar_metrica(bq, ETAPA, "filas", entrega.entregados, fuente=fuente.fuente, detalle=detalle, run_id=run_id)
        common.registrar_metrica(bq, ETAPA, "duracion_s", segundos, fuente=fuente.fuente, detalle=detalle, run_id=run_id)

    return {"archivo": fuente.archivo, "estado": "publicado", "filas": entrega.entregados,
            "topico": fuente.topico, "segundos": segundos, "particiones": particiones_txt}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fuente", nargs="*", help="archivo(s) o fuente(s) lógica(s); por defecto las dos streaming")
    parser.add_argument("--bootstrap", default=common.KAFKA_BOOTSTRAP, help="bootstrap.servers (env KAFKA_BOOTSTRAP)")
    parser.add_argument("--datos-dir", type=Path, default=common.DATOS_DIR, help="directorio de los CSV (env DATOS_DIR)")
    parser.add_argument("--particiones", type=int, default=PARTICIONES_POR_DEFECTO, help="particiones al crear el tópico")
    parser.add_argument("--forzar", action="store_true", help="republicar aunque el manifiesto ya tenga el archivo")
    parser.add_argument("--dry-run", action="store_true", help="sin manifiesto ni métricas (solo Kafka); env INGEST_DRY_RUN=1")
    args = parser.parse_args(argv)

    dry_run = args.dry_run or os.environ.get("INGEST_DRY_RUN") == "1"
    run_id = common.run_id_actual()
    fuentes = resolver_fuentes(args.fuente)

    bq = None
    if not dry_run:
        bq = common.bq_client()
        common.asegurar_tablas_ops(bq)

    productor = Producer(config_productor(args.bootstrap))
    print(f"run_id={run_id} bootstrap={args.bootstrap} dry_run={dry_run} forzar={args.forzar}")

    resultados = []
    for fuente in fuentes:
        resultados.append(procesar_fuente(
            fuente, bootstrap=args.bootstrap, productor=productor, bq=bq, datos_dir=args.datos_dir,
            dry_run=dry_run, forzar=args.forzar, particiones=args.particiones, run_id=run_id,
        ))

    print("\narchivo | filas publicadas | tópico | segundos | msgs/s")
    for r in resultados:
        if r["estado"] == "omitido":
            print(f"{r['archivo']} | omitido ({r['filas']} filas ya publicadas) | {r['topico']} | - | -")
            continue
        tasa = r["filas"] / r["segundos"] if r["segundos"] > 0 else 0.0
        print(f"{r['archivo']} | {r['filas']} | {r['topico']} (part. {r['particiones']}) | {r['segundos']:.2f} | {tasa:,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
