"""Pruebas sin red de las funciones de formato de ingest/evidencia_p2.py."""
import json

from ingest import common, evidencia_p2 as ev


def test_cargar_esperados(tmp_path):
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"archivos": {"a.csv": {"filas_datos": 1234, "sha256": "x"}}}))
    assert ev.cargar_esperados(p) == {"a.csv": 1234}


def test_fila_conteo_y_markdown():
    f1 = common.FUENTES["tm_estaciones.csv"]
    f2 = common.FUENTES["transmetro_validaciones.csv"]
    filas = [ev.fila_conteo(f1, 104, 104), ev.fila_conteo(f2, 363221, 363221, 363221)]
    assert all(f["ok"] for f in filas)
    md = ev.conteos_a_markdown(filas, "r1", "ts")
    assert "| archivo | vía | filas esperadas (LEEME) | filas cargadas (Bronze) | diferencia | ok |" in md
    assert "363,221 (distintas: 363,221)" in md and "**363,325**" in md and "OK" in md


def test_diferencia_y_duplicados():
    f2 = common.FUENTES["transmetro_validaciones.csv"]
    assert not ev.fila_conteo(f2, 10, 9, 9)["ok"]
    dup = ev.fila_conteo(f2, 10, 10, 8)
    assert not dup["ok"] and "2 duplicado" in dup["nota"]
    assert not ev.fila_conteo(f2, 10, None, error="x")["ok"]


def test_ultimas_duraciones_toma_ultima_success_ordenada():
    filas = [
        {"etapa": "b", "valor": 5, "ts": "2026-01-01T00:02", "detalle": "success"},
        {"etapa": "a", "valor": 1, "ts": "2026-01-01T00:00", "detalle": "failed"},
        {"etapa": "a", "valor": 2, "ts": "2026-01-01T00:01", "detalle": "success"},
        {"etapa": "a", "valor": 3, "ts": "2026-01-01T00:03", "detalle": "success"},
    ]
    assert ev.ultimas_duraciones(filas) == [("b", 5.0), ("a", 3.0)]


def test_tiempos_markdown_y_reloj():
    assert ev.reloj_dagrun("2026-01-01T00:00:00Z", "2026-01-01T00:10:30+00:00") == 630.0
    assert ev.reloj_dagrun(None, "x") is None
    md = ev.tiempos_a_markdown([("a", 1000.0), ("b", 2.5)], 1200.0, "r", "ts")
    assert "| a | 1,000.0 |" in md and "TOTAL (suma de tareas)** | **1,002.5" in md and "TOTAL (reloj del DagRun)" in md
    assert "reloj" not in ev.tiempos_a_markdown([], None, "r", "ts")
