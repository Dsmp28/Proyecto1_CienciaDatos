"""Pruebas del DAG `red_metropolitana` y de las funciones puras de run_metrics / conteos_capas.

- Las pruebas del DAG requieren Airflow instalado (contenedor de la VM): en el .venv local se omiten
  con `pytest.importorskip("airflow")`.
- Las pruebas de comparación de instantáneas y de construcción de métricas no tocan la red.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ingest import conteos_capas, run_metrics  # noqa: E402

# Laptop: <repo>/airflow/dags/…; contenedor de la VM: /opt/airflow/dags/… (montaje de vm/docker-compose.yml).
DAG_PATH = next(
    (p for p in (REPO / "airflow" / "dags" / "red_metropolitana_dag.py", REPO / "dags" / "red_metropolitana_dag.py") if p.exists()),
    REPO / "airflow" / "dags" / "red_metropolitana_dag.py",
)

TAREAS_ESPERADAS = {
    "generar_o_verificar_datos",
    "ingesta_bronze.ingesta_batch",
    "ingesta_bronze.ingesta_cdc",
    "ingesta_bronze.ingesta_streaming.kafka_productor",
    "ingesta_bronze.ingesta_streaming.kafka_consumidor",
    "tablas_externas_bronze",
    "conciliar_bronze",
    "publicar_clave_hmac",
    "transformacion_dbt.dbt_deps",
    "transformacion_dbt.dbt_seed",
    "transformacion_dbt.dbt_staging",
    "transformacion_dbt.dbt_silver",
    "transformacion_dbt.dbt_gold",
    "transformacion_dbt.dbt_features",
    "transformacion_dbt.dbt_docs",
    "pruebas_python",
    "registrar_metricas",
    "registrar_fallo",
}


# ---------------------------------------------------------------------------
# DAG (solo con Airflow instalado)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def dag():
    # "airflow.sdk" y no "airflow": la carpeta airflow/ del repo es importable como paquete de
    # espacio de nombres desde la raíz y haría pasar el importorskip sin Airflow instalado.
    pytest.importorskip("airflow.sdk")
    # El entorno (conexión SQLite temporal) lo prepara tests/conftest.py antes de importar Airflow.
    spec = importlib.util.spec_from_file_location("red_metropolitana_dag", DAG_PATH)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.dag


def test_dag_id_y_configuracion(dag):
    assert dag.dag_id == "red_metropolitana"
    assert dag.schedule is None
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert "red-metropolitana" in dag.tags
    assert dict(dag.params) == {"escala": "", "idle_segundos": 30}


def test_dag_sin_ciclos(dag):
    dag.check_cycle()  # lanza AirflowDagCycleException si hay ciclo (Airflow 3: método del DAG)


def test_tareas_esperadas(dag):
    assert set(dag.task_ids) == TAREAS_ESPERADAS


def test_reintentos_y_callbacks(dag):
    for tarea in dag.tasks:
        assert tarea.retries == 2, tarea.task_id
        assert tarea.retry_exponential_backoff is True, tarea.task_id
        assert tarea.on_success_callback and tarea.on_failure_callback, tarea.task_id


def test_dependencias_clave(dag):
    assert "transformacion_dbt.dbt_silver" in dag.get_task("transformacion_dbt.dbt_gold").upstream_task_ids
    assert "pruebas_python" in dag.get_task("registrar_metricas").upstream_task_ids
    assert dag.get_task("tablas_externas_bronze").upstream_task_ids == {
        "ingesta_bronze.ingesta_batch", "ingesta_bronze.ingesta_cdc", "ingesta_bronze.ingesta_streaming.kafka_consumidor",
    }
    assert dag.get_task("transformacion_dbt.dbt_deps").upstream_task_ids == {"conciliar_bronze", "publicar_clave_hmac"}
    fallo = dag.get_task("registrar_fallo")
    assert fallo.trigger_rule == "one_failed"  # TriggerRule es un str-Enum: compara por valor
    assert fallo.upstream_task_ids == TAREAS_ESPERADAS - {"registrar_fallo"}
    assert dag.get_task("registrar_metricas").trigger_rule == "all_success"


def test_entorno_de_las_tareas_bash(dag):
    for tarea in dag.tasks:
        assert tarea.cwd == "/opt/airflow", tarea.task_id
        assert tarea.append_env is True, tarea.task_id
        assert tarea.env["RUN_ID"] == "{{ run_id }}"
        assert tarea.env["PYTHONPATH"] == "/opt/airflow"
        assert "ESCALA" in tarea.env and "INGEST_DATE" in tarea.env
    assert "--select tag:gold" in dag.get_task("transformacion_dbt.dbt_gold").bash_command
    consumidor = dag.get_task("ingesta_bronze.ingesta_streaming.kafka_consumidor")
    # Los params llegan por entorno, nunca interpolados en el comando (inyección de shell).
    assert consumidor.env["IDLE_SEGUNDOS"] == "{{ params.idle_segundos }}"
    assert "params." not in consumidor.bash_command


# ---------------------------------------------------------------------------
# conteos_capas: comparación de instantáneas (sin red)
# ---------------------------------------------------------------------------
def _snapshot(**cambios):
    base = {
        "generado_ts": "2026-09-21T00:00:00+00:00",
        "proyecto": "p",
        "bucket": "b",
        "tablas": {"bronze.tm_estaciones": 104, "silver.dim_estacion": 468, "staging.stg_tm_estaciones": 104},
        "gcs_bronze": {"objetos": 122, "bytes": 309266388,
                       "por_fuente": {"tm_estaciones": {"objetos": 1, "bytes": 7387}}},
    }
    base.update(cambios)
    return base


def test_snapshots_identicos_sin_diferencias():
    a, b = _snapshot(), _snapshot(generado_ts="2026-09-21T01:00:00+00:00")  # la hora no cuenta
    assert conteos_capas.comparar_snapshots(a, b) == []
    md = conteos_capas.markdown_comparacion(a, b, [])
    assert "RESULTADO: IDÉNTICOS" in md and "| silver.dim_estacion | 468 | 468 | sí |" in md


def test_snapshot_detecta_conteo_distinto():
    b = _snapshot(tablas={**_snapshot()["tablas"], "silver.dim_estacion": 470})
    difs = conteos_capas.comparar_snapshots(_snapshot(), b)
    assert difs == [{"clave": "silver.dim_estacion", "a": 468, "b": 470, "tipo": "tabla"}]
    assert "RESULTADO: DIFERENTES" in conteos_capas.markdown_comparacion(_snapshot(), b, difs)


def test_snapshot_detecta_tabla_ausente_en_cualquiera_de_los_dos():
    sin_silver = _snapshot(tablas={"bronze.tm_estaciones": 104, "staging.stg_tm_estaciones": 104})
    difs = conteos_capas.comparar_snapshots(_snapshot(), sin_silver)
    assert difs == [{"clave": "silver.dim_estacion", "a": 468, "b": None, "tipo": "tabla"}]
    difs_inv = conteos_capas.comparar_snapshots(sin_silver, _snapshot())
    assert difs_inv[0]["a"] is None and difs_inv[0]["b"] == 468


def test_snapshot_detecta_objetos_nuevos_en_bronze():
    b = _snapshot(gcs_bronze={"objetos": 123, "bytes": 309266388 + 10,
                              "por_fuente": {"tm_estaciones": {"objetos": 2, "bytes": 7397}}})
    claves = [d["clave"] for d in conteos_capas.comparar_snapshots(_snapshot(), b)]
    assert claves == ["gcs:bronze/ (objetos)", "gcs:bronze/ (bytes)",
                      "gcs:bronze/tm_estaciones/ (objetos)", "gcs:bronze/tm_estaciones/ (bytes)"]


def test_markdown_snapshot_lista_todas_las_capas():
    md = conteos_capas.a_markdown(_snapshot())
    for capa in conteos_capas.CAPAS:
        assert f"**{capa}**" in md
    assert "_(sin tablas)_" in md  # gold/features vacías se muestran explícitamente


# ---------------------------------------------------------------------------
# run_metrics: construcción de métricas (sin red)
# ---------------------------------------------------------------------------
def test_construir_metricas_por_tabla_y_por_capa():
    conteos = {
        "bronze": {"tm_estaciones": {"filas": 104, "bytes": 7387}, "tu_paradas": {"filas": 328, "bytes": 13189}},
        "silver": {"dim_estacion": {"filas": 468, "bytes": 1000}},
    }
    filas = run_metrics.construir_metricas("run-x", conteos, "2026-09-21T00:00:00+00:00", estado=1)
    por = {(f["capa"], f["fuente"], f["metrica"]): f["valor"] for f in filas}
    assert por[("bronze", "tm_estaciones", "filas")] == 104.0
    assert por[("bronze", None, "filas_capa")] == 432.0
    assert por[("bronze", None, "bytes_capa")] == 20576.0
    assert por[("silver", None, "filas_capa")] == 468.0
    assert por[("gold", None, "filas_capa")] == 0.0 and por[("features", None, "bytes_capa")] == 0.0
    assert por[(None, None, "estado")] == 1.0
    assert all(f["run_id"] == "run-x" and f["etapa"] == "registrar_metricas" for f in filas)
    assert set(filas[0]) == {"run_id", "etapa", "capa", "fuente", "metrica", "valor", "ts", "detalle"}
    # Sin estado: no hay fila 'estado'; conteos vacíos: solo agregados en 0
    sin = run_metrics.construir_metricas("r", {}, "ts")
    assert {f["metrica"] for f in sin} == {"filas_capa", "bytes_capa"} and len(sin) == 2 * len(conteos_capas.CAPAS)


def test_markdown_run_metrics():
    md = run_metrics.a_markdown("run-x", {"staging": {"stg_a": {"filas": 5, "bytes": None}}}, "ts")
    assert "## staging — 1 tablas, 5 filas, 0 bytes" in md and "| stg_a | 5 | — |" in md
    assert "## gold — 0 tablas" in md
