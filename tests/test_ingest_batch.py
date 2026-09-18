"""Pruebas unitarias de la ingesta batch/CDC a Bronze. Sin red: no tocan GCP.

Cubren las funciones puras de ingest/common.py, ingest/generar_o_verificar.py,
ingest/batch_to_gcs.py y ingest/bronze_external_tables.py.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ingest import batch_to_gcs, bronze_external_tables, common, generar_o_verificar  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def csv_pequeno(tmp_path):
    p = tmp_path / "mini.csv"
    p.write_bytes(b"a,b\n1,2\n3,4\n\n5,6\n")  # encabezado + 3 filas de datos + una línea vacía
    return p


@pytest.fixture
def jsonl_pequeno(tmp_path):
    p = tmp_path / "mini.jsonl"
    p.write_bytes(b'{"x": 1}\n{"x": "a\\"b"}\n\n{"x": null}\n')  # 3 documentos + línea vacía
    return p


@pytest.fixture
def huellas_esperadas():
    return {
        "a.csv": {"sha256": "aa", "filas_datos": 10, "bytes": 100},
        "b.csv": {"sha256": "bb", "filas_datos": 20, "bytes": 200},
    }


# ---------------------------------------------------------------------------
# common: sha256, conteo, rutas
# ---------------------------------------------------------------------------
def test_sha256_archivo_coincide_con_hashlib(csv_pequeno):
    esperado = hashlib.sha256(csv_pequeno.read_bytes()).hexdigest()
    assert common.sha256_archivo(csv_pequeno) == esperado
    assert common.sha256_archivo(csv_pequeno, bloque=2) == esperado  # independiente del tamaño de bloque


def test_contar_filas_csv_descuenta_encabezado_e_ignora_vacias(csv_pequeno):
    assert common.contar_filas(csv_pequeno, "csv") == 3


def test_contar_filas_jsonl_no_descuenta_nada(jsonl_pequeno):
    assert common.contar_filas(jsonl_pequeno, "jsonl") == 3


def test_ruta_bronze_es_hive_y_determinista():
    assert common.ruta_bronze("tm_estaciones", "2026-09-20", "tm_estaciones.csv") == \
        "bronze/tm_estaciones/ingest_date=2026-09-20/tm_estaciones.csv"


def test_catalogo_tiene_9_fuentes_y_7_batch_cdc():
    assert len(common.FUENTES) == 9
    assert len(common.fuentes_por_via("batch")) + len(common.fuentes_por_via("cdc")) == 7
    assert len(common.fuentes_por_via("streaming")) == 2


def test_expected_hashes_cubre_las_9_fuentes():
    huellas = json.loads((REPO / "ingest" / "expected_hashes.json").read_text())["archivos"]
    assert set(huellas) == set(common.FUENTES)
    for v in huellas.values():
        assert len(v["sha256"]) == 64 and v["filas_datos"] > 0 and v["bytes"] > 0


# ---------------------------------------------------------------------------
# generar_o_verificar: comparación de huellas y escala
# ---------------------------------------------------------------------------
def test_comparar_hashes_todo_verificado(huellas_esperadas):
    filas = generar_o_verificar.comparar_hashes(huellas_esperadas, huellas_esperadas)
    assert [f["archivo"] for f in filas] == ["a.csv", "b.csv"]
    assert all(f["verificado"] for f in filas)


def test_comparar_hashes_detecta_sha_filas_y_ausentes(huellas_esperadas):
    calculado = {
        "a.csv": {"sha256": "zz", "filas_datos": 10, "bytes": 100},   # sha distinto
        "b.csv": {"sha256": "bb", "filas_datos": 21, "bytes": 200},   # filas distintas
        "c.csv": {"sha256": "cc", "filas_datos": 1, "bytes": 1},      # sin huella esperada
    }
    filas = {f["archivo"]: f for f in generar_o_verificar.comparar_hashes(huellas_esperadas, calculado)}
    assert filas["a.csv"]["detalle"] == "sha256 distinto"
    assert filas["b.csv"]["detalle"] == "filas distintas"
    assert filas["c.csv"]["detalle"] == "sin huella esperada"
    faltante = generar_o_verificar.comparar_hashes(huellas_esperadas, {})
    assert all(f["detalle"] == "archivo ausente" for f in faltante)


def test_escala_personalizada():
    assert generar_o_verificar.escala_personalizada(None) is None
    assert generar_o_verificar.escala_personalizada("") is None
    assert generar_o_verificar.escala_personalizada("0.08") is None
    assert generar_o_verificar.escala_personalizada("0.5") == "0.5"
    with pytest.raises(ValueError):
        generar_o_verificar.escala_personalizada("mucho")


def test_sustituir_escala_en_el_generador_real():
    codigo = generar_o_verificar.GENERADOR.read_text(encoding="utf-8")
    nuevo = generar_o_verificar.sustituir_escala(codigo, "0.5")
    assert "ESCALA        = 0.5 " in nuevo and "= 0.08 " not in nuevo
    with pytest.raises(ValueError):
        generar_o_verificar.sustituir_escala("x = 1\n", "0.5")


def test_directorio_trabajo_generador(tmp_path):
    assert generar_o_verificar.directorio_trabajo_generador(tmp_path / "datos_red") == tmp_path
    with pytest.raises(SystemExit):
        generar_o_verificar.directorio_trabajo_generador(tmp_path / "otro")


def test_calcular_huellas_solo_archivos_presentes(tmp_path, monkeypatch):
    (tmp_path / "tm_estaciones.csv").write_bytes(b"h\n1\n2\n")
    huellas = generar_o_verificar.calcular_huellas(tmp_path)
    assert set(huellas) == {"tm_estaciones.csv"}
    assert huellas["tm_estaciones.csv"]["filas_datos"] == 2
    assert generar_o_verificar.archivos_faltantes(tmp_path) == [n for n in common.FUENTES if n != "tm_estaciones.csv"]


# ---------------------------------------------------------------------------
# batch_to_gcs: decisión de idempotencia y verificación de copia
# ---------------------------------------------------------------------------
def test_decidir_accion_omitido_vs_subir():
    assert batch_to_gcs.decidir_accion(True) == ("omitido", "sha256 ya ingerido")
    assert batch_to_gcs.decidir_accion(False) == ("subir", None)


def test_verificar_copia(csv_pequeno):
    md5 = batch_to_gcs.md5_base64(csv_pequeno)
    n = csv_pequeno.stat().st_size
    batch_to_gcs.verificar_copia(n, md5, n, md5)          # igual: no lanza
    batch_to_gcs.verificar_copia(n, md5, n, None)         # GCS sin md5 (objeto compuesto): solo tamaño
    with pytest.raises(RuntimeError):
        batch_to_gcs.verificar_copia(n, md5, n + 1, md5)
    with pytest.raises(RuntimeError):
        batch_to_gcs.verificar_copia(n, md5, n, "otro==")


def test_seleccionar_fuentes():
    todas = batch_to_gcs.seleccionar_fuentes("todas", None)
    assert len(todas) == 7 and {f.via for f in todas} == {"batch", "cdc"}
    assert [f.fuente for f in batch_to_gcs.seleccionar_fuentes("cdc", None)] == ["cdc_padron_usuarios"]
    assert batch_to_gcs.seleccionar_fuentes("batch", "metroriel_viajes.jsonl")[0].fuente == "metroriel_viajes"
    with pytest.raises(SystemExit):
        batch_to_gcs.seleccionar_fuentes("batch", "transmetro_validaciones")  # es streaming


def test_ingerir_fuente_omitido_no_sube(tmp_path, monkeypatch):
    """Con el sha256 ya en el manifiesto no se llama a subir_archivo y se registra 'omitido'."""
    fuente = common.FUENTES["tm_estaciones.csv"]
    (tmp_path / fuente.archivo).write_bytes(b"h\n1\n2\n")
    registros, metricas = [], []
    monkeypatch.setattr(common, "manifiesto_tiene", lambda *a, **k: True)
    monkeypatch.setattr(common, "registrar_manifiesto", lambda bq, fila: registros.append(fila))
    monkeypatch.setattr(common, "registrar_metrica", lambda *a, **k: metricas.append(a[2]))
    monkeypatch.setattr(common, "subir_archivo", lambda *a, **k: pytest.fail("no debe subir"))
    r = batch_to_gcs.ingerir_fuente(fuente, bq=None, bucket=None, datos_dir=tmp_path,
                                    ingest_date="2026-09-20", run_id="t")
    assert r["estado"] == "omitido" and r["objeto"] is None
    assert registros[0]["estado"] == "omitido" and registros[0]["detalle"] == "sha256 ya ingerido"
    assert registros[0]["filas_origen"] == 2
    assert sorted(metricas) == ["bytes", "duracion_s", "filas"]


def test_ingerir_fuente_completado_sube_y_verifica(tmp_path, monkeypatch):
    fuente = common.FUENTES["cdc_padron_usuarios.csv"]
    p = tmp_path / fuente.archivo
    p.write_bytes(b"h\n1\n2\n3\n")

    class BlobFalso:
        size = p.stat().st_size
        md5_hash = batch_to_gcs.md5_base64(p)

    class BucketFalso:
        name = "lake"

    registros = []
    monkeypatch.setattr(common, "manifiesto_tiene", lambda *a, **k: False)
    monkeypatch.setattr(common, "registrar_manifiesto", lambda bq, fila: registros.append(fila))
    monkeypatch.setattr(common, "registrar_metrica", lambda *a, **k: None)
    monkeypatch.setattr(common, "subir_archivo", lambda bucket, path, destino, metadata=None: BlobFalso())
    r = batch_to_gcs.ingerir_fuente(fuente, bq=None, bucket=BucketFalso(), datos_dir=tmp_path,
                                    ingest_date="2026-09-20", run_id="t")
    assert r["estado"] == "completado"
    assert r["objeto"] == "gs://lake/bronze/cdc_padron_usuarios/ingest_date=2026-09-20/cdc_padron_usuarios.csv"
    assert registros[0]["estado"] == "completado"
    assert registros[0]["filas_bronze"] == registros[0]["filas_origen"] == 3
    assert registros[0]["objetos_bronze"] == 1 and registros[0]["bytes_bronze"] == BlobFalso.size


# ---------------------------------------------------------------------------
# bronze_external_tables: plantilla DDL
# ---------------------------------------------------------------------------
def test_plantilla_ddl_renderiza_y_contiene_9_tablas():
    sql = bronze_external_tables.sql_renderizado("proy", "cubo")
    assert "{" not in sql and "}" not in sql
    sentencias = bronze_external_tables.dividir_sentencias(sql)
    assert len(sentencias) == 9
    tablas = {bronze_external_tables.nombre_tabla(s) for s in sentencias}
    assert tablas == {f"proy.bronze.{f.fuente}" for f in common.FUENTES.values()}
    for s in sentencias:
        assert s.startswith("CREATE OR REPLACE EXTERNAL TABLE")
        assert "gs://cubo/bronze/" in s and "hive_partition_uri_prefix" in s


def test_plantilla_ddl_opciones_por_via():
    por_tabla = {bronze_external_tables.nombre_tabla(s): s
                 for s in bronze_external_tables.dividir_sentencias(bronze_external_tables.sql_renderizado("p", "b"))}
    for f in common.FUENTES.values():
        s = por_tabla[f"p.bronze.{f.fuente}"]
        if f.via == "streaming":
            assert "NEWLINE_DELIMITED_JSON" in s and "topico STRING" in s and "particion INT64" in s
            assert "linea_num INT64" in s and "sha256_archivo STRING" in s
        else:
            assert "format = 'CSV'" in s and "quote = ''" in s and "field_delimiter = '\\t'" in s
            assert "raw STRING" in s and "ingest_date DATE" in s
            assert f"skip_leading_rows = {1 if f.formato == 'csv' else 0}" in s


def test_renderizar_falla_si_quedan_marcadores():
    with pytest.raises(ValueError):
        bronze_external_tables.renderizar("x {project} {bucket}", "{project}", "b")
