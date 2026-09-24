"""Consumidor de Kafka → Bronze en GCS por micro lotes, con nombres de objeto deterministas.

Bucle: consume, acumula los mensajes por (tópico, partición) y escribe UN objeto JSONL
por ventana de offsets lista en

    bronze/<fuente>/ingest_date=<hoy>/topico=<t>/particion=<p>/offsets=<inicio:012d>-<fin:012d>.jsonl

donde `fuente` es la fuente lógica del catálogo (`FUENTES`) asociada al tópico.
`topico` y `particion` NO van dentro del JSON: viven en la ruta y BigQuery los expone
como columnas de partición Hive. Cada línea del objeto es un JSON con exactamente:

    offset (int), kafka_ts (ISO 8601 UTC del timestamp del mensaje), clave (str),
    archivo, linea_num (int), sha256_archivo (headers del productor),
    raw (value decodificado), ingest_ts (ISO 8601 UTC de la escritura).

Ventanas deterministas. El rango de offsets de un objeto debe depender solo de los
offsets, nunca del orden o el ritmo de llegada; si no, una reentrega produciría otro
rango (otro nombre) y duplicaría Bronze. Por eso cada partición se corta en ventanas
alineadas de N = `--max-mensajes-lote` offsets (`offset // N`): la ventana k cubre
[k·N, (k+1)·N − 1]. Una ventana se escribe cuando está completa (llegó su último
offset, o ya hay mensajes de una ventana posterior) o, cada `--max-segundos-lote`,
cuando la partición alcanzó el final del log (marca de agua alta): entonces se
escribe la ventana parcial [k·N o el offset confirmado, último del log]. El nombre
usa el primer y el último offset presentes en la ventana.

Idempotencia (ADR-006b): los offsets se confirman (commit síncrono) SOLO después de
subir todos los objetos del lote. Si el proceso muere entre subir y confirmar, Kafka
reentrega desde el último offset confirmado y el consumidor reescribe el MISMO nombre
de objeto (mismo tópico, partición y rango) con el mismo contenido: cero duplicados en
Bronze. Republicar el mismo archivo se evita en el productor por manifiesto; si
alguien fuerza la republicación (`kafka_producer.py --forzar`), Bronze recibe líneas
nuevas con otro offset pero la misma terna (archivo, linea_num, sha256_archivo):
Staging deduplica por esa terna y Bronze conserva el histórico.

Límites conocidos: (1) `ingest_date` se fija una vez al arrancar (env INGEST_DATE o
fecha local de hoy); Airflow debe pasar INGEST_DATE para que una reentrega a
medianoche no cambie la ruta. (2) Si el proceso muere entre subir y confirmar una
ventana parcial (fin de log) y el productor sigue publicando en ese instante, la
reentrega puede abarcar más offsets; en este pipeline el productor termina antes de
que arranque el consumidor, así que no ocurre.

Terminación: cuando lleva `--idle-segundos` sin recibir mensajes y el lag de todas
las particiones asignadas es 0 (antes escribe las ventanas pendientes: están al final
del log), o al alcanzar `--max-tiempo` (tope de seguridad; lo pendiente sin confirmar
se reentrega en la siguiente corrida).

Modo de prueba (`--salida-local <dir>` o `--dry-run`/`INGEST_DRY_RUN=1`): escribe los
objetos bajo ese directorio local en lugar de GCS y no registra métricas.

Uso:
    python -m ingest.kafka_consumer_gcs                          # los dos tópicos
    python -m ingest.kafka_consumer_gcs --topicos transmetro.validaciones
    python -m ingest.kafka_consumer_gcs --bootstrap localhost:9092 --salida-local /tmp/bronze
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from confluent_kafka import (
    OFFSET_INVALID,
    TIMESTAMP_NOT_AVAILABLE,
    Consumer,
    KafkaError,
    KafkaException,
    TopicPartition,
)

from ingest import common
from ingest.common import fuentes_por_via

ETAPA = "ingesta_streaming_consumer"
CAPA = "bronze"
CAMPOS_ENVELOPE = ("offset", "kafka_ts", "clave", "archivo", "linea_num", "sha256_archivo", "raw", "ingest_ts")
TOPICO_A_FUENTE: dict[str, str] = {f.topico: f.fuente for f in fuentes_por_via("streaming") if f.topico}
ARCHIVO_A_FUENTE: dict[str, str] = {f.archivo: f.fuente for f in fuentes_por_via("streaming")}

Clave = tuple[str, int]  # (tópico, partición)


# ---------------------------------------------------------------------------
# Funciones puras (probadas sin Kafka ni GCS)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Mensaje:
    """Lo que el consumidor necesita de un mensaje de Kafka, desacoplado de la librería."""
    topico: str
    particion: int
    offset: int
    kafka_ts_ms: int | None
    clave: str | None
    headers: dict[str, str]
    raw: str


def decodificar_headers(headers: Iterable[tuple[str, bytes | str | None]] | None) -> dict[str, str]:
    """Headers de Kafka (lista de pares, valores en bytes) → dict de str. Un valor None queda ''."""
    salida: dict[str, str] = {}
    for clave, valor in headers or ():
        if valor is None:
            salida[clave] = ""
        elif isinstance(valor, bytes):
            salida[clave] = valor.decode("utf-8", errors="replace")
        else:
            salida[clave] = str(valor)
    return salida


def iso_utc_ms(ms: int | None) -> str | None:
    """Milisegundos desde época → ISO 8601 UTC con milisegundos; None si Kafka no trae timestamp."""
    if ms is None:
        return None
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat(timespec="milliseconds")


def construir_envelope(m: Mensaje, ingest_ts: str) -> dict[str, Any]:
    """Línea JSONL de Bronze: exactamente los 8 campos de CAMPOS_ENVELOPE, en ese orden."""
    linea_num = m.headers.get("linea_num")
    return {
        "offset": int(m.offset),
        "kafka_ts": iso_utc_ms(m.kafka_ts_ms),
        "clave": m.clave,
        "archivo": m.headers.get("archivo"),
        "linea_num": int(linea_num) if linea_num not in (None, "") else None,
        "sha256_archivo": m.headers.get("sha256_archivo"),
        "raw": m.raw,
        "ingest_ts": ingest_ts,
    }


def nombre_objeto(topico: str, particion: int, offset_inicio: int, offset_fin: int) -> str:
    """Sufijo determinista bajo bronze/<fuente>/ingest_date=.../ : tópico, partición y rango de offsets."""
    return f"topico={topico}/particion={particion}/offsets={offset_inicio:012d}-{offset_fin:012d}.jsonl"


def agrupar_lote(mensajes: Iterable[Mensaje]) -> dict[Clave, list[Mensaje]]:
    """Agrupa por (tópico, partición) y ordena cada grupo por offset (Kafka ya los entrega en orden)."""
    grupos: dict[Clave, list[Mensaje]] = defaultdict(list)
    for m in mensajes:
        grupos[(m.topico, m.particion)].append(m)
    return {k: sorted(v, key=lambda m: m.offset) for k, v in grupos.items()}


def ventanas_listas(mensajes: list[Mensaje], n: int, fin_log: int | None) -> tuple[list[list[Mensaje]], list[Mensaje]]:
    """Separa los mensajes (ordenados por offset) de UNA partición en ventanas listas y resto.

    La ventana k cubre los offsets [k·n, (k+1)·n − 1]. Está lista si contiene su último
    offset, si hay mensajes de una ventana posterior (con `read_committed` puede haber
    huecos por marcadores de transacción) o, para la última, si `fin_log` (marca de agua
    alta = último offset del log + 1) indica que ya se alcanzó el final. Todo lo demás
    espera en memoria. Así el rango de cada objeto depende solo de los offsets.
    """
    listas: list[list[Mensaje]] = []
    resto: list[Mensaje] = []
    por_ventana: dict[int, list[Mensaje]] = defaultdict(list)
    for m in mensajes:
        por_ventana[m.offset // n].append(m)
    if not por_ventana:
        return listas, resto
    ultima = max(por_ventana)
    for k in sorted(por_ventana):
        grupo = por_ventana[k]
        completa = grupo[-1].offset == (k + 1) * n - 1 or k < ultima
        al_final = fin_log is not None and grupo[-1].offset + 1 >= fin_log
        if completa or al_final:
            listas.append(grupo)
        else:
            resto.extend(grupo)
    return listas, resto


def serializar_grupo(mensajes: list[Mensaje], ingest_ts: str) -> list[str]:
    """Líneas JSONL de un objeto (una por mensaje, cada una con su salto de línea final)."""
    return [json.dumps(construir_envelope(m, ingest_ts), ensure_ascii=False) + "\n" for m in mensajes]


def fuente_de_topico(topico: str) -> str:
    try:
        return TOPICO_A_FUENTE[topico]
    except KeyError:
        raise SystemExit(f"Tópico sin fuente en el catálogo: {topico}. Conocidos: {sorted(TOPICO_A_FUENTE)}") from None


def mensaje_desde_kafka(msg) -> Mensaje:
    ts_tipo, ts_ms = msg.timestamp()
    clave = msg.key()
    return Mensaje(
        topico=msg.topic(),
        particion=msg.partition(),
        offset=msg.offset(),
        kafka_ts_ms=None if ts_tipo == TIMESTAMP_NOT_AVAILABLE else ts_ms,
        clave=clave.decode("utf-8", errors="replace") if isinstance(clave, bytes) else clave,
        headers=decodificar_headers(msg.headers()),
        raw=(msg.value() or b"").decode("utf-8", errors="replace"),
    )


# ---------------------------------------------------------------------------
# Destinos: GCS o directorio local (dry-run)
# ---------------------------------------------------------------------------
class DestinoGCS:
    def __init__(self, bucket_nombre: str):
        self.bucket = common.gcs_client().bucket(bucket_nombre)
        self.descripcion = f"gs://{bucket_nombre}"

    def escribir(self, ruta: str, contenido: str, metadata: dict) -> int:
        blob = common.subir_texto(self.bucket, contenido, ruta, metadata)
        return int(blob.size or len(contenido.encode("utf-8")))


class DestinoLocal:
    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.descripcion = str(raiz)

    def escribir(self, ruta: str, contenido: str, metadata: dict) -> int:
        destino = self.raiz / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        datos = contenido.encode("utf-8")
        destino.write_bytes(datos)
        return len(datos)


# ---------------------------------------------------------------------------
# Estadísticas
# ---------------------------------------------------------------------------
@dataclass
class EstadoParticion:
    offset_min: int | None = None
    offset_max: int | None = None
    mensajes: int = 0
    objetos: int = 0
    bytes: int = 0


@dataclass
class EstadoArchivo:
    filas: int = 0
    objetos: int = 0
    bytes: int = 0


class Estadisticas:
    def __init__(self) -> None:
        self.particiones: dict[Clave, EstadoParticion] = defaultdict(EstadoParticion)
        self.archivos: dict[str, EstadoArchivo] = defaultdict(EstadoArchivo)
        self.total_mensajes = 0
        self.total_objetos = 0

    def registrar_objeto(self, clave: Clave, mensajes: list[Mensaje], lineas: list[str], nbytes: int) -> None:
        p = self.particiones[clave]
        p.offset_min = mensajes[0].offset if p.offset_min is None else min(p.offset_min, mensajes[0].offset)
        p.offset_max = mensajes[-1].offset if p.offset_max is None else max(p.offset_max, mensajes[-1].offset)
        p.mensajes += len(mensajes)
        p.objetos += 1
        p.bytes += nbytes
        self.total_mensajes += len(mensajes)
        self.total_objetos += 1
        # Un objeto puede mezclar líneas de varios archivos: se reparte por el header `archivo`.
        vistos: set[str] = set()
        for m, linea in zip(mensajes, lineas):
            archivo = m.headers.get("archivo", "")
            a = self.archivos[archivo]
            a.filas += 1
            a.bytes += len(linea.encode("utf-8"))
            if archivo not in vistos:
                vistos.add(archivo)
                a.objetos += 1


# ---------------------------------------------------------------------------
# Consumidor
# ---------------------------------------------------------------------------
def config_consumidor(bootstrap: str, grupo: str) -> dict:
    return {
        "bootstrap.servers": bootstrap,
        "group.id": grupo,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
        "isolation.level": "read_committed",
        "max.poll.interval.ms": 600_000,   # subir un lote grande a GCS puede tardar
        "session.timeout.ms": 45_000,
    }


def marcas_altas(consumer: Consumer, claves: Iterable[Clave]) -> dict[Clave, int]:
    """Marca de agua alta (último offset + 1) por partición, consultada al broker."""
    return {(t, p): consumer.get_watermark_offsets(TopicPartition(t, p), timeout=10, cached=False)[1] for t, p in claves}


def lag_total(consumer: Consumer) -> int | None:
    """Suma de (offset alto − posición) en las particiones asignadas; None si aún no hay asignación."""
    asignadas = consumer.assignment()
    if not asignadas:
        return None
    total = 0
    posiciones = {(tp.topic, tp.partition): tp.offset for tp in consumer.position(asignadas)}
    confirmadas: dict[Clave, int] | None = None
    for tp in asignadas:
        bajo, alto = consumer.get_watermark_offsets(tp, timeout=10, cached=False)
        pos = posiciones.get((tp.topic, tp.partition), OFFSET_INVALID)
        if pos is None or pos < 0:
            # Sin mensajes consumidos en esta sesión: la posición efectiva es el offset confirmado.
            if confirmadas is None:
                confirmadas = {(c.topic, c.partition): c.offset for c in consumer.committed(asignadas, timeout=10)}
            pos = confirmadas.get((tp.topic, tp.partition), OFFSET_INVALID)
            if pos is None or pos < 0:
                pos = bajo  # nunca confirmado: auto.offset.reset=earliest
        total += max(0, alto - pos)
    return total


def escribir_lote(grupos: list[list[Mensaje]], destino, ingest_date: str, run_id: str, stats: Estadisticas) -> list[TopicPartition]:
    """Escribe un objeto por grupo (mensajes de una misma partición, ordenados por offset).

    Devuelve los offsets a confirmar: por partición, el último offset escrito + 1.
    """
    ingest_ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")
    a_confirmar: dict[Clave, int] = {}
    for mensajes in grupos:
        topico, particion = mensajes[0].topico, mensajes[0].particion
        ruta = common.ruta_bronze(fuente_de_topico(topico), ingest_date, nombre_objeto(topico, particion, mensajes[0].offset, mensajes[-1].offset))
        lineas = serializar_grupo(mensajes, ingest_ts)
        nbytes = destino.escribir(ruta, "".join(lineas), {
            "topico": topico, "particion": particion, "offset_inicio": mensajes[0].offset,
            "offset_fin": mensajes[-1].offset, "mensajes": len(mensajes), "run_id": run_id,
        })
        stats.registrar_objeto((topico, particion), mensajes, lineas, nbytes)
        print(f"  objeto {ruta} ({len(mensajes)} msgs, {nbytes} bytes)")
        a_confirmar[(topico, particion)] = max(a_confirmar.get((topico, particion), 0), mensajes[-1].offset + 1)
    return [TopicPartition(t, p, o) for (t, p), o in a_confirmar.items()]


def consumir(consumer: Consumer, topicos: list[str], destino, *, ingest_date: str, run_id: str, max_mensajes_lote: int,
             max_segundos_lote: float, idle_segundos: float, max_tiempo: float) -> Estadisticas:
    stats = Estadisticas()
    pendientes: dict[Clave, list[Mensaje]] = defaultdict(list)

    def al_revocar(_consumer, particiones):
        # Lo no confirmado de una partición revocada lo reentregará su nuevo dueño: se descarta aquí.
        for tp in particiones:
            if pendientes.pop((tp.topic, tp.partition), None):
                print(f"  partición revocada {tp.topic}/{tp.partition}: se descartan mensajes sin confirmar")

    consumer.subscribe(topicos, on_revoke=al_revocar)

    def escribir_y_confirmar(grupos: list[list[Mensaje]]) -> None:
        a_confirmar = escribir_lote(grupos, destino, ingest_date, run_id, stats)
        consumer.commit(offsets=a_confirmar, asynchronous=False)
        print(f"  commit {sum(len(g) for g in grupos)} mensajes, {len(grupos)} objeto(s), {len(a_confirmar)} partición(es)")

    def vaciar(usar_fin_log: bool) -> None:
        """Escribe las ventanas completas y, si `usar_fin_log`, también las parciales al final del log."""
        fines = marcas_altas(consumer, pendientes) if usar_fin_log else {}
        grupos: list[list[Mensaje]] = []
        for clave in list(pendientes):
            listas, resto = ventanas_listas(pendientes[clave], max_mensajes_lote, fines.get(clave))
            grupos.extend(listas)
            if resto:
                pendientes[clave] = resto
            else:
                del pendientes[clave]
        if grupos:
            escribir_y_confirmar(grupos)

    inicio = time.monotonic()
    ultimo_mensaje = inicio
    ultimo_corte = inicio
    motivo = "max-tiempo"

    while True:
        ahora = time.monotonic()
        if ahora - inicio >= max_tiempo:
            n = sum(len(v) for v in pendientes.values())
            if n:
                print(f"  max-tiempo: {n} mensajes sin confirmar se reentregarán en la siguiente corrida")
            break
        # Corte por tiempo: además de las ventanas completas, las parciales al final del log.
        if pendientes and ahora - ultimo_corte >= max_segundos_lote:
            vaciar(usar_fin_log=True)
            ultimo_corte = time.monotonic()
            continue
        # Terminación por inactividad: sin mensajes durante idle_segundos y lag 0.
        if ahora - ultimo_mensaje >= idle_segundos:
            lag = lag_total(consumer)
            if lag is None:
                print(f"  sin partición asignada tras {idle_segundos:.0f} s sin mensajes; se termina")
                motivo = "idle (sin asignación)"
                break
            if lag == 0:
                vaciar(usar_fin_log=True)  # lo pendiente está, por definición, al final del log
                motivo = "idle (lag 0)"
                break
            print(f"  idle pero lag={lag}; se sigue esperando")
            ultimo_mensaje = time.monotonic()

        msgs = consumer.consume(num_messages=500, timeout=1.0)
        for msg in msgs:
            err = msg.error()
            if err is not None:
                if err.code() == KafkaError._PARTITION_EOF:
                    continue
                if err.fatal():
                    raise KafkaException(err)
                print(f"  aviso de Kafka: {err}", file=sys.stderr)
                continue
            m = mensaje_desde_kafka(msg)
            pendientes[(m.topico, m.particion)].append(m)
            ultimo_mensaje = time.monotonic()
        if msgs:
            vaciar(usar_fin_log=False)  # ventanas completas: se escriben en cuanto se llenan

    print(f"fin del bucle: {motivo}, {time.monotonic() - inicio:.1f} s")
    return stats


def registrar_metricas(bq, stats: Estadisticas, run_id: str) -> None:
    for archivo, a in stats.archivos.items():
        fuente = ARCHIVO_A_FUENTE.get(archivo, archivo)
        for metrica, valor in (("filas", a.filas), ("objetos", a.objetos), ("bytes", a.bytes)):
            common.registrar_metrica(bq, ETAPA, metrica, valor, capa=CAPA, fuente=fuente, detalle=f"archivo={archivo}", run_id=run_id)


def imprimir_resumen(stats: Estadisticas) -> None:
    print("\ntópico | partición | offsets | mensajes | objetos | bytes")
    for (topico, particion), p in sorted(stats.particiones.items()):
        print(f"{topico} | {particion} | {p.offset_min}-{p.offset_max} | {p.mensajes} | {p.objetos} | {p.bytes}")
    print(f"total: {stats.total_mensajes} mensajes, {stats.total_objetos} objetos")
    for archivo, a in sorted(stats.archivos.items()):
        print(f"archivo {archivo}: {a.filas} filas en {a.objetos} objeto(s), {a.bytes} bytes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--topicos", nargs="*", default=sorted(TOPICO_A_FUENTE), help="tópicos a consumir (por defecto los dos streaming)")
    parser.add_argument("--bootstrap", default=common.KAFKA_BOOTSTRAP, help="bootstrap.servers (env KAFKA_BOOTSTRAP)")
    parser.add_argument("--grupo", default="bronze-writer", help="group.id del consumidor")
    parser.add_argument("--bucket", default=common.LAKE_BUCKET, help="bucket del lago (env LAKE_BUCKET)")
    parser.add_argument("--max-mensajes-lote", type=int, default=5000, help="tamaño N de la ventana de offsets por partición (mensajes por objeto)")
    parser.add_argument("--max-segundos-lote", type=float, default=5.0, help="cada cuánto se escriben las ventanas parciales al final del log")
    parser.add_argument("--idle-segundos", type=float, default=float(os.environ.get("IDLE_SEGUNDOS") or 20.0),
                        help="termina tras este tiempo sin mensajes y lag 0 (env IDLE_SEGUNDOS)")
    parser.add_argument("--max-tiempo", type=float, default=3600.0, help="tope de seguridad en segundos")
    parser.add_argument("--salida-local", type=Path, help="escribe en este directorio en vez de GCS (implica --dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="sin GCS ni métricas; requiere --salida-local. env INGEST_DRY_RUN=1")
    args = parser.parse_args(argv)

    dry_run = args.dry_run or os.environ.get("INGEST_DRY_RUN") == "1" or args.salida_local is not None
    if dry_run and args.salida_local is None:
        parser.error("--dry-run requiere --salida-local <dir>")
    if args.max_mensajes_lote < 1:
        parser.error("--max-mensajes-lote debe ser >= 1")
    for t in args.topicos:
        fuente_de_topico(t)

    run_id = common.run_id_actual()
    ingest_date = common.ingest_date_hoy()
    bq = None
    if dry_run:
        destino = DestinoLocal(args.salida_local)
    else:
        bq = common.bq_client()
        common.asegurar_tablas_ops(bq)
        destino = DestinoGCS(args.bucket)
    print(f"run_id={run_id} grupo={args.grupo} tópicos={args.topicos} destino={destino.descripcion} ingest_date={ingest_date}")

    consumer = Consumer(config_consumidor(args.bootstrap, args.grupo))
    try:
        stats = consumir(consumer, args.topicos, destino, ingest_date=ingest_date, run_id=run_id,
                         max_mensajes_lote=args.max_mensajes_lote, max_segundos_lote=args.max_segundos_lote,
                         idle_segundos=args.idle_segundos, max_tiempo=args.max_tiempo)
    finally:
        consumer.close()

    if not dry_run and stats.archivos:
        registrar_metricas(bq, stats, run_id)
    imprimir_resumen(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
