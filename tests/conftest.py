import json
from pathlib import Path

import pytest

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
