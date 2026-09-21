import json
import os
import tempfile
from pathlib import Path

import pytest

# Airflow 3 entrega a los procesos de tarea la cadena `airflow-db-not-allowed:///` (las tareas no deben tocar la base
# de metadatos). Cuando `pruebas_python` corre dentro del DAG, importar el DAG con esa cadena falla al parsearla, así
# que se sustituye por un SQLite temporal ANTES de que cualquier prueba importe Airflow. Fuera de Airflow no afecta.
_conn = os.environ.get("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN", "")
if not _conn or "://" not in _conn or _conn.startswith("airflow-db-not-allowed"):
    os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"] = f"sqlite:///{tempfile.gettempdir()}/red_metropolitana_test_dag.db"
os.environ.setdefault("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")

REPO = Path(__file__).resolve().parents[1]
DBT_DIR = REPO / "dbt"
MANIFEST = DBT_DIR / "target" / "manifest.json"


@pytest.fixture(scope="session")
def manifest():
    """manifest.json de dbt. Se genera con `dbt parse`/`dbt build`; sin él las pruebas de linaje se omiten."""
    if not MANIFEST.exists():
        pytest.skip(f"No existe {MANIFEST}; ejecuta `dbt parse` primero")
    with MANIFEST.open() as f:
        return json.load(f)


@pytest.fixture(scope="session")
def dbt_dir():
    return DBT_DIR
