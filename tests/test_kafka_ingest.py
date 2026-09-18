"""Pruebas unitarias de la vía streaming (productor y consumidor) sin red, Kafka ni GCS.

Cubren las funciones puras: envelope JSON de Bronze, nombre determinista del objeto,
agrupación del lote por (tópico, partición), decodificación de headers, iteración de
líneas del CSV, y que el productor omite un archivo ya presente en el manifiesto.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # raíz del repo: `ingest` es importable sin instalar

from ingest import kafka_consumer_gcs as consumidor
from ingest import kafka_producer as productor
from ingest.common import FUENTES

SHA = "a" * 64


def mensaje(topico="transmetro.validaciones", particion=0, offset=0, archivo="transmetro_validaciones.csv",
            linea_num=1, raw="1,TC-00013132,TM-L6-01,L6,2026-06-01 04:50:57,1.00,TRANSBORDO", kafka_ts_ms=1_780_000_000_000):
    return consumidor.Mensaje(
        topico=topico, particion=particion, offset=offset, kafka_ts_ms=kafka_ts_ms, clave=archivo,
        headers={"archivo": archivo, "linea_num": str(linea_num), "sha256_archivo": SHA, "run_id": "r1"}, raw=raw,
    )


# ---------------------------------------------------------------------------
# Consumidor
# ---------------------------------------------------------------------------
def test_envelope_tiene_exactamente_los_ocho_campos():
    env = consumidor.construir_envelope(mensaje(offset=42, linea_num=7), "2026-09-20T12:00:00.000+00:00")
    assert tuple(env) == consumidor.CAMPOS_ENVELOPE
    assert env["offset"] == 42 and isinstance(env["offset"], int)
    assert env["linea_num"] == 7 and isinstance(env["linea_num"], int)
    assert env["kafka_ts"] == "2026-05-28T20:26:40.000+00:00"
    assert env["clave"] == "transmetro_validaciones.csv"
    assert env["archivo"] == "transmetro_validaciones.csv"
    assert env["sha256_archivo"] == SHA
    assert env["raw"].startswith("1,TC-00013132")
    assert env["ingest_ts"] == "2026-09-20T12:00:00.000+00:00"
    assert "topico" not in env and "particion" not in env
    json.loads(json.dumps(env))  # serializable


def test_envelope_sin_timestamp_ni_headers():
    m = consumidor.Mensaje("t", 0, 5, None, None, {}, "x")
    env = consumidor.construir_envelope(m, "ts")
    assert env["kafka_ts"] is None and env["linea_num"] is None and env["archivo"] is None and env["clave"] is None


def test_nombre_objeto_determinista_con_doce_digitos():
    nombre = consumidor.nombre_objeto("transmetro.validaciones", 2, 0, 4999)
    assert nombre == "topico=transmetro.validaciones/particion=2/offsets=000000000000-000000004999.jsonl"
    assert consumidor.nombre_objeto("t", 0, 123, 123) == consumidor.nombre_objeto("t", 0, 123, 123)
    assert consumidor.nombre_objeto("t", 0, 1, 2) != consumidor.nombre_objeto("t", 1, 1, 2)


def test_agrupar_lote_por_topico_y_particion_ordenado_por_offset():
    lote = [
        mensaje(particion=1, offset=11),
        mensaje(particion=0, offset=3),
        mensaje(topico="aerometro.boardings", particion=0, offset=7, archivo="aerometro_boardings.csv"),
        mensaje(particion=1, offset=10),
    ]
    grupos = consumidor.agrupar_lote(lote)
    assert set(grupos) == {("transmetro.validaciones", 1), ("transmetro.validaciones", 0), ("aerometro.boardings", 0)}
    assert [m.offset for m in grupos[("transmetro.validaciones", 1)]] == [10, 11]
    assert [m.offset for m in grupos[("transmetro.validaciones", 0)]] == [3]
    assert sum(len(v) for v in grupos.values()) == 4


def _offsets(ventanas):
    return [(v[0].offset, v[-1].offset) for v in ventanas]


def test_ventanas_listas_alineadas_a_multiplos_de_n():
    msgs = [mensaje(offset=o) for o in range(0, 2000)]
    listas, resto = consumidor.ventanas_listas(msgs, 1500, fin_log=None)
    assert _offsets(listas) == [(0, 1499)]           # ventana 0 completa
    assert [m.offset for m in resto] == list(range(1500, 2000))  # ventana 1 incompleta: espera
    listas, resto = consumidor.ventanas_listas(resto, 1500, fin_log=2000)
    assert _offsets(listas) == [(1500, 1999)] and resto == []     # al final del log: parcial


def test_ventanas_listas_no_dependen_del_orden_de_llegada():
    """Escenario que produjo duplicados en la primera versión: el rango debe salir de los offsets, no del lote."""
    n = 1500
    todo = [mensaje(offset=o) for o in range(2000)]
    # Llegada A: 1000 y luego 1000. Llegada B: 1500 y luego 500. Ambas deben dar los mismos objetos.
    def simular(tandas):
        objetos, pendientes = [], []
        for tanda in tandas:
            pendientes = sorted(pendientes + tanda, key=lambda m: m.offset)
            listas, pendientes = consumidor.ventanas_listas(pendientes, n, fin_log=None)
            objetos += _offsets(listas)
        listas, pendientes = consumidor.ventanas_listas(pendientes, n, fin_log=2000)
        return objetos + _offsets(listas)
    assert simular([todo[:1000], todo[1000:]]) == simular([todo[:1500], todo[1500:]]) == [(0, 1499), (1500, 1999)]


def test_ventanas_listas_reanuda_desde_offset_confirmado_y_tolera_huecos():
    # Reentrega desde el offset confirmado 1800 (ventana 1 = 1500..2999): el nombre empieza en 1800.
    msgs = [mensaje(offset=o) for o in range(1800, 3200)]
    listas, resto = consumidor.ventanas_listas(msgs, 1500, fin_log=None)
    assert _offsets(listas) == [(1800, 2999)] and [m.offset for m in resto] == list(range(3000, 3200))
    # Hueco en el último offset de la ventana (marcador de transacción): se cierra al ver la siguiente ventana.
    msgs = [mensaje(offset=o) for o in (0, 1, 3)]
    listas, resto = consumidor.ventanas_listas(msgs, 3, fin_log=None)
    assert _offsets(listas) == [(0, 1)] and [m.offset for m in resto] == [3]
    assert consumidor.ventanas_listas([], 3, None) == ([], [])


def test_serializar_grupo_una_linea_json_por_mensaje():
    lineas = consumidor.serializar_grupo([mensaje(offset=1), mensaje(offset=2)], "ts")
    assert len(lineas) == 2 and all(l.endswith("\n") for l in lineas)
    assert [json.loads(l)["offset"] for l in lineas] == [1, 2]


def test_decodificar_headers():
    headers = [("archivo", b"transmetro_validaciones.csv"), ("linea_num", b"12"), ("sha256_archivo", SHA.encode()), ("vacio", None)]
    assert consumidor.decodificar_headers(headers) == {
        "archivo": "transmetro_validaciones.csv", "linea_num": "12", "sha256_archivo": SHA, "vacio": "",
    }
    assert consumidor.decodificar_headers(None) == {}


def test_fuente_de_topico_usa_el_catalogo():
    assert consumidor.fuente_de_topico("transmetro.validaciones") == "transmetro_validaciones"
    assert consumidor.fuente_de_topico("aerometro.boardings") == "aerometro_boardings"
    with pytest.raises(SystemExit):
        consumidor.fuente_de_topico("no.existe")


def test_escribir_lote_en_destino_local_y_offsets_a_confirmar(tmp_path: Path):
    stats = consumidor.Estadisticas()
    lote = [mensaje(particion=0, offset=0), mensaje(particion=0, offset=1), mensaje(particion=2, offset=9)]
    grupos = list(consumidor.agrupar_lote(lote).values())
    a_confirmar = consumidor.escribir_lote(grupos, consumidor.DestinoLocal(tmp_path), "2026-09-20", "r1", stats)
    objetos = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.jsonl"))
    assert objetos == [
        "bronze/transmetro_validaciones/ingest_date=2026-09-20/topico=transmetro.validaciones/particion=0/offsets=000000000000-000000000001.jsonl",
        "bronze/transmetro_validaciones/ingest_date=2026-09-20/topico=transmetro.validaciones/particion=2/offsets=000000000009-000000000009.jsonl",
    ]
    assert {(tp.partition, tp.offset) for tp in a_confirmar} == {(0, 2), (2, 10)}
    assert stats.total_mensajes == 3 and stats.total_objetos == 2
    assert stats.archivos["transmetro_validaciones.csv"].filas == 3
    assert stats.archivos["transmetro_validaciones.csv"].objetos == 2


# ---------------------------------------------------------------------------
# Productor
# ---------------------------------------------------------------------------
def test_construir_headers():
    assert productor.construir_headers("a.csv", 3, SHA, "run-1") == [
        ("archivo", "a.csv"), ("linea_num", "3"), ("sha256_archivo", SHA), ("run_id", "run-1"),
    ]


def test_iterar_lineas_datos_salta_encabezado_y_vacias(tmp_path: Path):
    csv = tmp_path / "x.csv"
    csv.write_text("id,v\r\n1,a\r\n\r\n2,b\n", encoding="utf-8")
    assert list(productor.iterar_lineas_datos(csv)) == [(1, "1,a"), (2, "2,b")]


def test_resolver_fuentes_por_defecto_y_por_nombre():
    assert [f.archivo for f in productor.resolver_fuentes(None)] == ["transmetro_validaciones.csv", "aerometro_boardings.csv"]
    assert productor.resolver_fuentes(["aerometro_boardings"])[0].topico == "aerometro.boardings"
    with pytest.raises(SystemExit):
        productor.resolver_fuentes(["tm_estaciones.csv"])  # batch, no streaming


def test_productor_omite_archivo_presente_en_manifiesto(tmp_path: Path, monkeypatch):
    fuente = FUENTES["transmetro_validaciones.csv"]
    (tmp_path / fuente.archivo).write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    monkeypatch.setattr(productor.common, "manifiesto_tiene", lambda client, archivo, sha256, estados=None: True)
    monkeypatch.setattr(productor, "crear_topico_si_no_existe", lambda *a, **k: pytest.fail("no debe tocar Kafka"))
    monkeypatch.setattr(productor, "publicar_archivo", lambda *a, **k: pytest.fail("no debe publicar"))
    monkeypatch.setattr(productor.common, "registrar_manifiesto", lambda *a, **k: pytest.fail("no debe escribir el manifiesto"))

    r = productor.procesar_fuente(fuente, bootstrap="x:1", productor=None, bq=object(), datos_dir=tmp_path,
                                  dry_run=False, forzar=False, particiones=3, run_id="r1")
    assert r["estado"] == "omitido" and r["filas"] == 2


def test_productor_forzar_publica_y_registra_detalle_forzado(tmp_path: Path, monkeypatch):
    fuente = FUENTES["aerometro_boardings.csv"]
    (tmp_path / fuente.archivo).write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    monkeypatch.setattr(productor.common, "manifiesto_tiene", lambda *a, **k: pytest.fail("con --forzar no se consulta"))
    monkeypatch.setattr(productor, "crear_topico_si_no_existe", lambda *a, **k: False)
    entrega = productor.EstadoEntrega(entregados=2, particiones={1})
    monkeypatch.setattr(productor, "publicar_archivo", lambda *a, **k: entrega)
    filas_manifiesto = []
    monkeypatch.setattr(productor.common, "registrar_manifiesto", lambda client, fila: filas_manifiesto.append(fila))
    monkeypatch.setattr(productor.common, "registrar_metrica", lambda *a, **k: None)

    r = productor.procesar_fuente(fuente, bootstrap="x:1", productor=None, bq=object(), datos_dir=tmp_path,
                                  dry_run=False, forzar=True, particiones=3, run_id="r1")
    assert r["estado"] == "publicado" and r["filas"] == 2
    assert len(filas_manifiesto) == 1
    assert filas_manifiesto[0]["estado"] == "publicado" and filas_manifiesto[0]["filas_bronze"] is None
    assert filas_manifiesto[0]["detalle"].startswith("forzado; tópico=aerometro.boardings, partición(es)=1")
