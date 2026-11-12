"""El borrador ingenuo de la prueba de recorte (tag auditoria_recorte) vive en la carpeta de features y hereda su tag,
pero depende de los modelos de churn, que se construyen después: si entra al build de features, la carga desde un
entorno vacío falla. Estas pruebas fijan que el flujo lo excluye."""
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SELECCION = "--select tag:features --exclude tag:churn tag:auditoria_recorte"


def _leer(*candidatos: Path) -> str:
    """Primer archivo que exista; en el contenedor de Airflow solo se montan algunas rutas del repositorio."""
    for ruta in candidatos:
        if ruta.exists():
            return ruta.read_text(encoding="utf-8")
    pytest.skip(f"no está montado ninguno de: {[str(c) for c in candidatos]}")


def test_el_dag_excluye_la_auditoria_del_build_de_features():
    dag = "red_metropolitana_dag.py"
    assert SELECCION in _leer(REPO / "airflow" / "dags" / dag, REPO / "dags" / dag)


def test_el_makefile_excluye_la_auditoria_del_build_de_features():
    assert SELECCION in _leer(REPO / "Makefile")


def test_el_borrador_ingenuo_no_lleva_el_tag_churn():
    proyecto = (REPO / "dbt" / "dbt_project.yml").read_text(encoding="utf-8")
    bloque = proyecto[proyecto.index("auditoria:"):]
    assert '+tags: ["auditoria_recorte"]' in bloque
