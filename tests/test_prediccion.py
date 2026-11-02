"""Pruebas de predecir.py / ml.prediccion con un modelo sintético y features sintéticas (sin red)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import predecir  # noqa: E402
from ingest.common import FUENTES, sha256_archivo  # noqa: E402
from ml import config as cfg  # noqa: E402
from ml import prediccion as pr  # noqa: E402
from ml.persistencia import guardar_modelo  # noqa: E402
from ml.pipeline import construir_pipeline  # noqa: E402

FECHA = "2026-08-30"
UMBRAL_META = 0.4


def features_sinteticas(n: int = 200, semilla: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    d = {c: rng.gamma(2.0, 3.0, n) for c in cfg.FEATURES_NUM}
    d["dias_desde_ultimo"] = rng.integers(0, 28, n).astype(float)
    d["ratio_ult14_prev14"] = np.where(rng.random(n) < 0.1, np.nan, rng.gamma(2.0, 0.5, n))
    d.update(
        unidad_id=[f"u{i:05d}" for i in rng.permutation(n)], corte="C", fecha_corte=FECHA,
        modo_principal=rng.choice(["TM", "TU", "MR", "AM"], n),
        zona_principal=np.where(rng.random(n) < 0.2, None, rng.choice(["Z1", "Z2"], n)),
        perfil_padron_a_t=np.where(rng.random(n) < 0.5, None, rng.choice(["general", "estudiante"], n)),
        tiene_padron_a_t=rng.random(n) < 0.5,
        tarjetas=[f"T{i};U{i}" for i in range(n)], fecha_referencia="2026-11-01", run_id="sintetico",
    )
    return pd.DataFrame(d)


@pytest.fixture(scope="module")
def entorno(tmp_path_factory):
    base = tmp_path_factory.mktemp("pred")
    df = features_sinteticas()
    y = (df["dias_desde_ultimo"] + np.random.default_rng(1).normal(0, 5, len(df)) > 14).astype(int)
    pipe = construir_pipeline(LogisticRegression(max_iter=500)).fit(df[cfg.FEATURES], y)
    modelos = base / "modelos"
    ruta = guardar_modelo(pipe, {"umbral": UMBRAL_META}, directorio=modelos, version="9.9.9")
    csv = base / "features.csv"
    df.to_csv(csv, index=False)
    datos = base / "datos"
    datos.mkdir()
    for i, nombre in enumerate(FUENTES):
        (datos / nombre).write_text(f"contenido {i}\n")
    huellas = {n: sha256_archivo(datos / n) for n in FUENTES}
    return {"base": base, "modelos": modelos, "modelo": ruta, "csv": csv, "datos": datos, "huellas": huellas, "df": df}


def correr(entorno, salida, **kw):
    mensajes = []
    args = dict(datos=entorno["datos"], fecha_corte=FECHA, origen="csv", salida=salida, modelo=entorno["modelo"],
                features_csv=entorno["csv"], hashes_esperados=entorno["huellas"], out=mensajes.append)
    args.update(kw)
    return pr.ejecutar(**args), mensajes


def test_csv_columnas_orden_y_formato(entorno, tmp_path):
    salida = tmp_path / "p.csv"
    codigo, _ = correr(entorno, salida)
    assert codigo == 0
    crudo = salida.read_bytes()
    assert not crudo.startswith(b"\xef\xbb\xbf") and b"\r" not in crudo
    assert crudo.decode("utf-8").splitlines()[0] == "unidad_id,tarjetas,puntaje,contactar"
    df = pd.read_csv(salida, dtype={"unidad_id": str, "tarjetas": str})
    assert list(df.columns) == ["unidad_id", "tarjetas", "puntaje", "contactar"]
    assert len(df) == len(entorno["df"]) and df["unidad_id"].is_unique
    assert df["unidad_id"].tolist() == sorted(df["unidad_id"])
    assert set(df["contactar"]) <= {0, 1}
    # tarjetas viaja con su unidad
    esperado = entorno["df"].set_index("unidad_id")["tarjetas"]
    assert (df.set_index("unidad_id")["tarjetas"] == esperado.loc[df["unidad_id"]].to_numpy()).all()


def test_redondeo_a_seis_decimales(entorno, tmp_path):
    salida = tmp_path / "p.csv"
    correr(entorno, salida)
    texto = salida.read_text().splitlines()[1:]
    for fila in texto:
        decimales = fila.split(",")[-2].split(".")[1]
        assert len(decimales) == 6
    p = pd.read_csv(salida)["puntaje"]
    assert np.allclose(p, p.round(6), atol=1e-12)


def test_umbral_de_metadatos_y_argumento(entorno, tmp_path):
    a, b, c = tmp_path / "a.csv", tmp_path / "b.csv", tmp_path / "c.csv"
    correr(entorno, a)
    correr(entorno, b, umbral=0.0)
    correr(entorno, c, umbral=1.1)
    da, db, dc = (pd.read_csv(x) for x in (a, b, c))
    assert (da["contactar"] == (da["puntaje"] >= UMBRAL_META).astype(int)).all()
    assert db["contactar"].eq(1).all() and dc["contactar"].eq(0).all()
    assert 0 < da["contactar"].sum() < len(da)


def test_sha_distinto_codigo_2(entorno, tmp_path):
    malas = dict(entorno["huellas"], **{"tm_estaciones.csv": "0" * 64})
    salida = tmp_path / "p.csv"
    codigo, msgs = correr(entorno, salida, hashes_esperados=malas)
    assert codigo == 2 and not salida.exists()
    assert any("tm_estaciones.csv" in m for m in msgs)


def test_sin_verificar_avisa_y_continua(entorno, tmp_path):
    malas = dict(entorno["huellas"], **{"tm_estaciones.csv": "0" * 64})
    salida = tmp_path / "p.csv"
    codigo, msgs = correr(entorno, salida, hashes_esperados=malas, sin_verificar=True)
    assert codigo == 0 and salida.exists()
    assert any("AVISO" in m for m in msgs) and any("tm_estaciones.csv" in m for m in msgs)


def test_archivo_faltante_codigo_2(entorno, tmp_path):
    datos = tmp_path / "datos"
    datos.mkdir()
    (datos / "tm_estaciones.csv").write_text("x\n")
    codigo, msgs = correr(entorno, tmp_path / "p.csv", datos=datos)
    assert codigo == 2 and any("faltan archivos" in m for m in msgs)


def test_fecha_fuera_de_fechas_corte(entorno, tmp_path):
    codigo, msgs = correr(entorno, tmp_path / "p.csv", fecha_corte="2026-08-15")
    assert codigo == 2 and any("fechas_corte" in m for m in msgs)
    with pytest.raises(pr.ErrorUso):
        pr.validar_fecha_corte("30/08/2026")


def test_etiqueta_y_columnas_extra_se_ignoran(entorno, tmp_path):
    df = entorno["df"].copy()
    df["etiqueta"] = 1
    csv = tmp_path / "f.csv"
    df.to_csv(csv, index=False)
    s1, s2 = tmp_path / "1.csv", tmp_path / "2.csv"
    correr(entorno, s1)
    correr(entorno, s2, features_csv=csv)
    assert s1.read_bytes() == s2.read_bytes()


def test_consulta_features_parametrizada():
    sql = pr.consulta_features("_recorte")
    assert "@f" in sql and "EXCEPT (etiqueta)" in sql and "features_recorte.churn_dataset" in sql
    assert "silver_recorte.silver_unidad_tarjetas_corte" in sql and "USING (unidad_id, fecha_corte)" in sql
    with pytest.raises(pr.ErrorUso):
        pr.consulta_features("; DROP TABLE x")
    q = pr.consulta_manifiesto()
    assert "@estados" in q and "@archivos" in q and "ingest_ts DESC" in q


def test_comparar_huellas():
    assert pr.comparar_huellas({"a": "1", "b": "2"}, {"a": "1", "b": "2"}) == []
    assert [d["archivo"] for d in pr.comparar_huellas({"a": "1"}, {"a": "1", "b": "2", "c": "3"})] == ["b", "c"]


def test_cli_punta_a_punta(entorno, tmp_path):
    """predecir.py en modo csv: huellas falsas -> 2; con --sin-verificar -> 0 y CSV escrito."""
    salida = tmp_path / "cli.csv"
    base = ["--datos", str(entorno["datos"]), "--fecha-corte", FECHA, "--origen", "csv", "--salida", str(salida),
            "--modelo", str(entorno["modelo"]), "--features-csv", str(entorno["csv"])]
    assert predecir.main(base) == 2 and not salida.exists()
    assert predecir.main(base + ["--sin-verificar", "--umbral", "0.5"]) == 0
    assert len(pd.read_csv(salida)) == len(entorno["df"])
