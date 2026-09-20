"""DAG `red_metropolitana`: pipeline completo Bronze → Staging → Silver/Cuarentena → Gold → Features.

Corre en la VM (Airflow 3.3, LocalExecutor). Todas las tareas de shell se ejecutan en el
contenedor del scheduler con cwd=/opt/airflow, donde están montados `ingest/`, `dbt/`,
`tests/`, `scripts/` y `datos_red/` (ver vm/docker-compose.yml).

Este módulo NO abre clientes de red ni de BigQuery al parsearse: las métricas de duración se
registran en callbacks que importan `ingest.common` de forma perezosa.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, TaskGroup

log = logging.getLogger(__name__)

DAG_ID = "red_metropolitana"
CWD = "/opt/airflow"
PYTHON = "python"

# ---------------------------------------------------------------------------
# Plantillas comunes. Un DAG disparado por API/UI en Airflow 3 puede no tener
# `logical_date` (es opcional): en ese caso `ds`/`ts` no existen en el contexto y, con
# `StrictUndefined`, renderizarlos fallaría. Por eso llevan respaldo:
#   - INGEST_DATE vacío → ingest.common.ingest_date_hoy() usa la fecha local (America/Guatemala).
#   - run_ts → `run_after` del DagRun (siempre presente).
# ---------------------------------------------------------------------------
TPL_INGEST_DATE = "{{ ds if dag_run.logical_date else '' }}"
TPL_RUN_TS = "{{ ts if dag_run.logical_date else dag_run.run_after.isoformat() }}"

ENV_COMUN = {
    "RUN_ID": "{{ run_id }}",
    "INGEST_DATE": TPL_INGEST_DATE,
    "PYTHONPATH": CWD,
    "ESCALA": "{{ params.escala }}",  # vacío = escala oficial del generador (0.08)
}

DBT_VARS = '{"run_id": "{{ run_id }}", "run_ts": "' + TPL_RUN_TS + '"}'


def _dbt(cmd: str) -> str:
    """Comando dbt con cwd fijo, sin colores y con run_id/run_ts como vars."""
    return f"cd {CWD}/dbt && dbt {cmd} --no-use-colors --vars '{DBT_VARS}'"


# ---------------------------------------------------------------------------
# Métricas de duración por tarea (ops.run_metrics). Se ejecutan en el proceso de la tarea
# (task runner del SDK) al terminar; un fallo aquí nunca tumba la tarea.
# ---------------------------------------------------------------------------
def _duracion_segundos(ti) -> float | None:
    """`RuntimeTaskInstance` (Airflow 3) no expone `duration`: se deriva de start/end_date."""
    duracion = getattr(ti, "duration", None)
    if duracion is not None:
        return float(duracion)
    inicio, fin = getattr(ti, "start_date", None), getattr(ti, "end_date", None)
    if inicio is None:
        return None
    fin = fin or datetime.now(timezone.utc)
    return (fin - inicio).total_seconds()


def _registrar_duracion(context, detalle: str) -> None:
    try:
        from ingest import common  # importación perezosa: nada de BigQuery al parsear el DAG

        ti = context["task_instance"]
        valor = _duracion_segundos(ti)
        if valor is None:
            log.warning("Sin start_date en %s; no se registra duración", ti.task_id)
            return
        run_id = context.get("run_id") or getattr(ti, "run_id", None)
        common.registrar_metrica(common.bq_client(), etapa=ti.task_id, metrica="duracion_s", valor=valor,
                                 run_id=run_id, detalle=detalle)
        common.flush_ops()  # carga inmediata: el proceso de la tarea puede terminar sin ejecutar atexit
        log.info("Métrica duracion_s=%.1f registrada para %s (%s)", valor, ti.task_id, detalle)
    except Exception:  # noqa: BLE001 — registrar métricas nunca debe alterar el estado de la tarea
        log.exception("No se pudo registrar la duración en ops.run_metrics")


def al_terminar_ok(context) -> None:
    _registrar_duracion(context, "success")


def al_fallar(context) -> None:
    _registrar_duracion(context, "failed")


DEFAULT_ARGS = {
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "on_success_callback": al_terminar_ok,
    "on_failure_callback": al_fallar,
}

DOC_MD = """
# Red Metropolitana — pipeline de punta a punta

Disparo **manual** (UI o `POST /api/v2/dags/red_metropolitana/dagRuns`); `schedule=None`.
Podría programarse `@daily` sin cambios: cada etapa es idempotente y `catchup=False`.
`max_active_runs=1` evita dos corridas simultáneas sobre las mismas tablas.

Parámetros: `escala` (vacío = escala oficial 0.08 del generador; otro valor regenera los datos
sin verificar hashes) e `idle_segundos` (el consumidor Kafka termina tras ese tiempo sin mensajes).

| Etapa | Qué hace | Por qué es idempotente |
|---|---|---|
| `generar_o_verificar_datos` | Genera los 9 archivos crudos si faltan y verifica su sha256 contra `ingest/expected_hashes.json`. | Solo genera si falta algo; la huella fija detecta cambios. |
| `ingesta_bronze.ingesta_batch` / `ingesta_cdc` | Sube catálogos, MetroRiel, Transurbano y el log CDC a `gs://<lake>/bronze/<fuente>/ingest_date=…`. | `ops.ingest_manifest`: un archivo con el mismo sha256 se marca `omitido`, no se vuelve a subir. |
| `ingesta_bronze.ingesta_streaming.kafka_productor` → `kafka_consumidor` | Publica Transmetro y Aerómetro en Kafka y el consumidor escribe objetos por ventana de offsets. | El productor omite archivos ya publicados; los objetos tienen nombre determinista por (tópico, partición, offsets). |
| `tablas_externas_bronze` | `CREATE OR REPLACE EXTERNAL TABLE` Hive sobre cada prefijo y verifica `COUNT(*)`. | DDL declarativo. |
| `conciliar_bronze` | filas del archivo (manifiesto) == filas de la tabla externa, por fuente. | Solo lee. |
| `publicar_clave_hmac` | Deriva los bloques HMAC desde Secret Manager a `ops_secrets.hmac_key` y verifica BigQuery == Python. | No hace nada si la versión del secreto ya está publicada. |
| `transformacion_dbt.*` | `deps` → `seed --full-refresh` → staging → silver+quarantine → gold → features → `docs generate`. | Materialización `table` (recreación completa) y `var('fecha_referencia')` fija: nunca `CURRENT_DATE`. |
| `pruebas_python` | `pytest tests`: linaje de Gold, sin fecha del sistema, ingesta, este DAG. | Solo lee. |
| `registrar_metricas` | `ops.run_metrics`: filas y bytes por tabla y por capa + `estado=1`. | Añade filas etiquetadas con el `run_id`. |
| `registrar_fallo` | Si cualquier tarea falla (`one_failed`) registra `estado=0` para la corrida. | Ídem. |

Cada tarea registra además `duracion_s` (callbacks de éxito/fallo). Reintentos: 2 con espera
exponencial desde 2 min. La demo de idempotencia (`make demo-idempotencia`) dispara el DAG dos
veces y compara `ingest/conteos_capas.py` entre ambas corridas.
"""


def _bash(task_id: str, comando: str, **kwargs) -> BashOperator:
    return BashOperator(task_id=task_id, bash_command=comando, cwd=CWD, env=ENV_COMUN, append_env=True, **kwargs)


with DAG(
    dag_id=DAG_ID,
    description="Pipeline de la Agencia Metropolitana de Transporte: ingesta a Bronze, dbt por capas, pruebas y métricas",
    schedule=None,  # manual / API; podría ser "@daily"
    start_date=datetime(2026, 9, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["red-metropolitana"],
    doc_md=DOC_MD,
    params={"escala": "", "idle_segundos": 30},
) as dag:
    generar_o_verificar_datos = _bash("generar_o_verificar_datos", f"{PYTHON} ingest/generar_o_verificar.py")

    with TaskGroup(group_id="ingesta_bronze", tooltip="Tres vías de ingesta a Bronze en paralelo") as ingesta_bronze:
        ingesta_batch = _bash("ingesta_batch", f"{PYTHON} ingest/batch_to_gcs.py --via batch")
        ingesta_cdc = _bash("ingesta_cdc", f"{PYTHON} ingest/batch_to_gcs.py --via cdc")
        with TaskGroup(group_id="ingesta_streaming", tooltip="Kafka: productor y consumidor a GCS") as ingesta_streaming:
            kafka_productor = _bash("kafka_productor", f"{PYTHON} -m ingest.kafka_producer")
            kafka_consumidor = _bash(
                "kafka_consumidor",
                f"{PYTHON} -m ingest.kafka_consumer_gcs --idle-segundos {{{{ params.idle_segundos }}}}",
            )
            kafka_productor >> kafka_consumidor

    tablas_externas_bronze = _bash("tablas_externas_bronze", f"{PYTHON} ingest/bronze_external_tables.py --verificar --estricto")
    conciliar_bronze = _bash("conciliar_bronze", f"{PYTHON} ingest/conteos_bronze.py")
    publicar_clave_hmac = _bash("publicar_clave_hmac", f"{PYTHON} -m ingest.hmac_key_to_bq --verificar")

    with TaskGroup(group_id="transformacion_dbt", tooltip="dbt por capas (secuencial)") as transformacion_dbt:
        # `dbt build` con una selección vacía (p. ej. sin modelos gold todavía) termina con
        # código 0 y el aviso "Nothing to do" (verificado con dbt-core 1.12.5): no hace falta `|| true`.
        dbt_deps = _bash("dbt_deps", _dbt("deps"))
        dbt_seed = _bash("dbt_seed", _dbt("seed --full-refresh"))
        dbt_staging = _bash("dbt_staging", _dbt("build --select tag:staging"))
        dbt_silver = _bash("dbt_silver", _dbt("build --select tag:silver tag:quarantine"))
        dbt_gold = _bash("dbt_gold", _dbt("build --select tag:gold"))
        dbt_features = _bash("dbt_features", _dbt("build --select tag:features"))
        dbt_docs = _bash("dbt_docs", _dbt("docs generate"))
        dbt_deps >> dbt_seed >> dbt_staging >> dbt_silver >> dbt_gold >> dbt_features >> dbt_docs

    pruebas_python = _bash("pruebas_python", f"{PYTHON} -m pytest -q tests")
    registrar_metricas = _bash("registrar_metricas", f"{PYTHON} -m ingest.run_metrics --estado 1")
    registrar_fallo = _bash(
        "registrar_fallo",
        f"{PYTHON} -m ingest.run_metrics --solo-estado 0",
        trigger_rule="one_failed",
    )

    # Grafo
    generar_o_verificar_datos >> [ingesta_batch, ingesta_cdc, kafka_productor, publicar_clave_hmac]
    [ingesta_batch, ingesta_cdc, kafka_consumidor] >> tablas_externas_bronze >> conciliar_bronze
    [conciliar_bronze, publicar_clave_hmac] >> dbt_deps
    dbt_docs >> pruebas_python >> registrar_metricas

    # registrar_fallo observa a todas las demás tareas: se ejecuta si cualquiera falla.
    for tarea in dag.tasks:
        if tarea.task_id not in (registrar_fallo.task_id,):
            tarea >> registrar_fallo
