"""Funciones puras de ingest/landing.py y resolución de origen/env en generar_o_verificar. Sin red."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ingest import generar_o_verificar as gv, landing  # noqa: E402


def test_ruta_blob_y_version():
    assert landing.ruta_blob("v2", "a.csv") == "landing/datos_red/v2/a.csv"
    for mala in ("", "V2", "v 2", "../x", "a" * 41):
        with pytest.raises(ValueError):
            landing.validar_version(mala)


def test_construir_manifest():
    m = landing.construir_manifest("v2", {"b.csv": {"sha256": "2", "filas_datos": 1, "bytes": 5, "x": 0},
                                          "a.csv": {"sha256": "1", "filas_datos": 2, "bytes": 6}}, "t")
    assert m["version"] == "v2" and m["generado_ts"] == "t"
    assert list(m["archivos"]) == ["a.csv", "b.csv"]
    assert m["archivos"]["b.csv"] == {"sha256": "2", "filas_datos": 1, "bytes": 5}


def test_decidir_subida():
    assert landing.decidir_subida("a", None) is True
    assert landing.decidir_subida("a", "b") is True
    assert landing.decidir_subida("a", "a") is False


def test_archivos_a_descargar_faltantes_y_distintos():
    man = {"archivos": {"a.csv": {"sha256": "1"}, "b.csv": {"sha256": "2"}, "c.csv": {"sha256": "3"}}}
    assert landing.archivos_a_descargar(man, {"a.csv": "1", "b.csv": "x", "c.csv": None}) == ["b.csv", "c.csv"]
    assert landing.archivos_a_descargar(man, {"a.csv": "1", "b.csv": "2", "c.csv": "3"}) == []
    assert landing.archivos_a_descargar(man, {}) == ["a.csv", "b.csv", "c.csv"]


def test_resolver_origen_y_version():
    assert gv.resolver_origen(None, None) == "landing"
    assert gv.resolver_origen(None, "Local") == "local"
    assert gv.resolver_origen("generador", "local") == "generador"
    with pytest.raises(ValueError):
        gv.resolver_origen("nube", None)
    assert gv.resolver_version(None, None) == "v2"
    assert gv.resolver_version(None, "v3") == "v3"
    assert gv.resolver_version("v4", "v3") == "v4"


@pytest.mark.parametrize("valor,esperado", [(None, True), ("", True), ("True", True), ("1", True),
                                            ("false", False), ("FALSE", False), ("0", False), ("No", False)])
def test_verificar_desde_env(valor, esperado):
    assert gv.verificar_desde_env(valor) is esperado


def test_huella_esperada_segun_origen():
    assert gv.huella_esperada_para("generador").name == "expected_hashes_p1.json"
    assert gv.huella_esperada_para("landing").name == "expected_hashes.json"
    assert gv.huella_esperada_para("local").name == "expected_hashes.json"
