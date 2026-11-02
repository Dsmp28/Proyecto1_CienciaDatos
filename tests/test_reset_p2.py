"""Pruebas sin red de las funciones puras de scripts/reset_p2.py."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("reset_p2", Path(__file__).resolve().parents[1] / "scripts" / "reset_p2.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def test_confirmacion_exacta():
    assert r.token_confirmacion("p") == "BORRAR-p"
    assert r.confirmacion_valida("BORRAR-p", "p")
    for malo in (None, "", "borrar-p", "BORRAR-p ", "BORRAR-otro"):
        assert not r.confirmacion_valida(malo, "p")


def test_objetos_conserva_marcador_y_no_toca_landing():
    nombres = ["bronze/", "bronze/a/ingest_date=2026-01-01/x.csv", "landing/v2/x.csv", "bronze/b/y.jsonl", "bronze"]
    assert r.objetos_a_borrar(nombres) == ["bronze/a/ingest_date=2026-01-01/x.csv", "bronze/b/y.jsonl"]


def test_datasets_a_limpiar():
    ids = ["ops_secrets", "gold", "silver", "x_recorte", "ops", "otro", "bronze"]
    assert r.datasets_a_limpiar(ids) == ["bronze", "silver", "gold", "ops", "x_recorte"]
    assert "ops_secrets" not in r.datasets_a_limpiar(ids)


def test_parsear_topicos():
    salida = "WARNING: algo\ntransmetro.validaciones\n\n aerometro.boardings \n__consumer_offsets\n"
    assert r.parsear_topicos(salida) == ["__consumer_offsets", "aerometro.boardings", "transmetro.validaciones"]
    assert r.topicos_pendientes(r.parsear_topicos(salida), ["aerometro.boardings", "zzz"]) == ["aerometro.boardings"]


def test_topicos_de_fuentes():
    from ingest import common
    assert r.topicos_de_fuentes(common.FUENTES) == ["aerometro.boardings", "transmetro.validaciones"]


def test_markdown_dry_run():
    md = r.markdown_reset("dry-run", "p", "ts", {"objetos_bronze": 1200, "tablas": {"gold": 3}, "topicos": 2}, None, [], [])
    assert "1,200" in md and "dry-run" in md and "tablas en `gold` | 3" in md
