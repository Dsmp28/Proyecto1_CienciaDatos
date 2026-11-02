"""Pruebas del paquete ml/ (fase 1) con datos sintéticos, sin red."""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
import pytest

from ml import config as cfg
from ml.baselines import BaselineConstante, BaselineUnaFeature
from ml.datos import AccesoProhibidoB, TOKEN_B_INTERNO, cargar_dataset, preparar_xy
from ml.entrenar import main as entrenar_main
from ml.folds import obtener_folds
from ml.lineales import coeficientes, entrenar_logisticas, top_coeficientes
from ml.metricas import evaluar, resumen_cv, tabla_markdown
from ml.persistencia import cargar_modelo, guardar_modelo
from ml.pipeline import construir_pipeline, construir_preprocesador

GRILLA = np.logspace(-3, 1, 3)


def sintetico(n_por_corte: int = 600, semilla: int = 7) -> pd.DataFrame:
    """Dataset sintético con el esquema de features.churn_dataset; el churn depende de dias_desde_ultimo y la actividad."""
    rng = np.random.default_rng(semilla)
    filas = []
    for corte, fecha in (("A", "2026-07-01"), ("B", "2026-07-31"), ("C", "2026-08-30")):
        n = n_por_corte
        d = {c: rng.gamma(2.0, 3.0, n) for c in cfg.FEATURES_NUM}
        d["dias_desde_ultimo"] = rng.integers(0, 28, n).astype(float)
        d["n_abordajes_28d"] = rng.integers(2, 60, n).astype(float)
        d["ratio_ult14_prev14"] = np.where(rng.random(n) < 0.1, np.nan, rng.gamma(2.0, 0.5, n))
        d["duracion_media_mr_min"] = np.where(rng.random(n) < 0.6, np.nan, rng.normal(30, 8, n))
        z = 0.12 * d["dias_desde_ultimo"] - 0.04 * d["n_abordajes_28d"] + rng.normal(0, 1, n) - 0.3
        etiqueta = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(float)
        d.update(
            unidad_id=[f"u{semilla}{corte}{i:05d}" for i in range(n)], fecha_corte=fecha, corte=corte,
            modo_principal=rng.choice(["TM", "TU", "MR", "AM"], n),
            zona_principal=np.where(rng.random(n) < 0.2, None, rng.choice(["Z1", "Z2", "Z3"], n)),
            perfil_padron_a_t=np.where(rng.random(n) < 0.5, None, rng.choice(["general", "estudiante"], n)),
            tiene_padron_a_t=rng.random(n) < 0.5,
            etiqueta=np.where(corte == "C", np.nan, etiqueta),
            fecha_referencia="2026-11-01", run_id="sintetico",
        )
        filas.append(pd.DataFrame(d))
    return pd.concat(filas, ignore_index=True)


@pytest.fixture(scope="module")
def csv_sintetico(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("datos") / "churn_dataset.csv"
    sintetico().to_csv(ruta, index=False)
    return ruta


@pytest.fixture(scope="module")
def datos_a(csv_sintetico):
    return preparar_xy(cargar_dataset(["A"], "csv", csv_sintetico))


def test_guardia_b(csv_sintetico):
    with pytest.raises(AccesoProhibidoB):
        cargar_dataset(["A", "B"], "csv", csv_sintetico)
    with pytest.raises(AccesoProhibidoB):
        cargar_dataset(["B"], "csv", csv_sintetico, _token_b=object())
    sin = cargar_dataset(["B"], "csv", csv_sintetico, sin_etiqueta=True)
    assert cfg.COLUMNA_ETIQUETA not in sin and set(sin["corte"]) == {"B"}
    con = cargar_dataset(["B"], "csv", csv_sintetico, _token_b=TOKEN_B_INTERNO)
    assert con[cfg.COLUMNA_ETIQUETA].notna().all()
    assert cargar_dataset(["A", "C"], "csv", csv_sintetico)["corte"].nunique() == 2


def test_preparar_xy(datos_a):
    X, y, ids = datos_a
    assert list(X.columns) == cfg.FEATURES and set(y) == {0, 1} and ids.is_unique
    with pytest.raises(ValueError):
        preparar_xy(pd.DataFrame({"unidad_id": ["a"]}))


def test_folds_estables_y_reutilizados(datos_a, tmp_path):
    X, y, ids = datos_a
    ruta = tmp_path / "folds_A.csv"
    f1 = obtener_folds(ids, y, ruta)
    assert ruta.exists() and set(f1) == set(range(cfg.N_FOLDS))
    # orden de filas distinto: mismos folds por unidad
    perm = np.random.default_rng(0).permutation(len(ids))
    f2 = obtener_folds(ids.iloc[perm], y.iloc[perm], ruta)
    assert (pd.Series(f1, index=ids)[ids.iloc[perm]].to_numpy() == f2).all()
    # recalcular desde cero (sin archivo) da lo mismo: el cálculo no depende del orden
    f3 = obtener_folds(ids.iloc[perm], y.iloc[perm], tmp_path / "otro.csv")
    assert (f2 == f3).all()
    # estratificación
    tasas = [y[f1 == k].mean() for k in range(cfg.N_FOLDS)]
    assert max(tasas) - min(tasas) < 0.02
    # unidades distintas: se rechaza
    with pytest.raises(ValueError):
        obtener_folds(ids.iloc[:-1], y.iloc[:-1], ruta)


def test_preprocesador_serializable(datos_a, tmp_path):
    X, y, _ = datos_a
    pipe = construir_preprocesador().fit(X)
    joblib.dump(pipe, tmp_path / "pre.joblib")
    Z1, Z2 = pipe.transform(X), joblib.load(tmp_path / "pre.joblib").transform(X)
    assert not np.isnan(Z1).any() and np.allclose(Z1, Z2)
    nombres = pipe.get_feature_names_out()
    assert len(nombres) == Z1.shape[1] and "tiene_padron_a_t" in nombres and "modo_principal_TM" in nombres
    # categoría nueva en predicción no rompe
    X2 = X.head(5).copy()
    X2["modo_principal"] = "NUEVO"
    assert pipe.transform(X2).shape[1] == Z1.shape[1]


def test_baselines(datos_a):
    X, y, _ = datos_a
    p = BaselineConstante().fit(X, y).predict_proba(X)[:, 1]
    assert np.allclose(p, y.mean())
    assert evaluar(y, p)["ap"] == pytest.approx(y.mean())
    s = BaselineUnaFeature().fit(X, y).predict_proba(X)[:, 1]
    assert s.min() > 0 and s.max() <= 1
    assert evaluar(y, s)["ap"] > y.mean()  # dias_desde_ultimo es informativa en el sintético
    # monotonía: más días sin viajar, mayor puntaje
    a, b = X["dias_desde_ultimo"].to_numpy(), s
    assert np.corrcoef(a, b)[0, 1] > 0.95


def test_metricas():
    r = resumen_cv([{"ap": 0.2, "roc_auc": 0.6, "brier": 0.1}, {"ap": 0.4, "roc_auc": 0.8, "brier": 0.3}])
    assert r["ap_media"] == pytest.approx(0.3) and r["ap_sd"] == pytest.approx(np.std([0.2, 0.4], ddof=1))
    t = tabla_markdown([{"a": "x", "b": 1.0}], ["a", "b"])
    assert t.splitlines()[0] == "| a | b |" and "1.0000" in t


def test_logisticas_y_coeficientes(datos_a, tmp_path):
    X, y, ids = datos_a
    folds = obtener_folds(ids, y, tmp_path / "f.csv")
    tiempos = {}
    res, modelos, oof = entrenar_logisticas(X, y, folds, lambdas=GRILLA, n_jobs=1, tiempos=tiempos)
    assert set(res["castigo"]) == {"L2", "L1", "ElasticNet"} and len(res) == 3 * len(GRILLA)
    assert res.groupby("castigo")["es_optimo"].sum().eq(1).all()
    assert tiempos["cv_s"] > 0 and tiempos["ajuste_final_s"] > 0
    for c, sub in res.groupby("castigo"):
        opt = sub[sub["es_optimo"]].iloc[0]
        assert opt["ap_val_media"] == sub["ap_val_media"].max()
        assert opt["ap_val_media"] > y.mean()
        assert len(oof[c]) == len(y)
    coef = coeficientes(modelos["L2"])
    assert len(coef) == len(modelos["L2"][:-1].get_feature_names_out()) and coef["feature"].notna().all()
    hacia, protec = top_coeficientes(coef)
    assert len(hacia) == 5 and hacia["feature"].iloc[0] == "dias_desde_ultimo" and hacia["coeficiente"].iloc[0] > 0
    assert protec["coeficiente"].iloc[0] <= protec["coeficiente"].iloc[-1]


def test_persistencia(datos_a, tmp_path):
    X, y, ids = datos_a
    pipe = construir_pipeline(BaselineConstante()).fit(X, y)
    ruta = guardar_modelo(pipe, {"metricas_cv": {"ap": 0.5}}, directorio=tmp_path)
    assert (tmp_path / "ACTUAL").read_text().strip() == ruta.name
    modelo, meta = cargar_modelo(directorio=tmp_path)
    assert meta["umbral"] is None and meta["features"] == cfg.FEATURES and len(meta["sha256_joblib"]) == 64
    assert np.allclose(modelo.predict_proba(X)[:, 1], pipe.predict_proba(X)[:, 1])
    meta["versiones"]["scikit-learn"] = "0.0.0"
    ruta.with_suffix(".json").write_text(json.dumps(meta))
    with pytest.raises(RuntimeError, match="scikit-learn"):
        cargar_modelo(ruta)


def test_entrenar_fase1_csv_punta_a_punta(csv_sintetico, tmp_path):
    salida, arte = tmp_path / "evidencia", tmp_path / "artefactos"
    r = entrenar_main(["--fase", "1", "--origen", "csv", "--ruta-csv", str(csv_sintetico), "--salida-dir", str(salida),
                       "--artefactos-dir", str(arte), "--n-lambdas", "3"])
    for f in ("fase1_modelos.md", "fase1_lambda.md", "fase1_coeficientes.md", "fase1_tiempos.md", "figuras/ap_vs_lambda.png"):
        assert (salida / f).stat().st_size > 0, f
    assert (arte / "folds_A.csv").exists() and (arte / "fase1_resultados.json").exists()
    assert len(list(arte.glob("oof_A_*.csv"))) == 5
    tabla = (salida / "fase1_modelos.md").read_text()
    assert "Baseline constante" in tabla and "Baseline una feature" in tabla and tabla.count("Logística") == 3
    datos = json.loads((arte / "fase1_resultados.json").read_text())
    assert datos["semilla"] == 2026 and datos["versiones"]["scikit-learn"] and {"carga_s", "cv_s", "ajuste_final_s"} <= set(datos["tiempos_s"])
    m = r["metricas_cv"]
    assert m["baseline_constante"]["ap_media"] == pytest.approx(r["tasa_positiva_A"], abs=0.03)
    assert m["logistica_l2"]["ap_media"] > m["baseline_constante"]["ap_media"]
    # segunda corrida: reutiliza los folds y reproduce exactamente las métricas
    r2 = entrenar_main(["--fase", "1", "--origen", "csv", "--ruta-csv", str(csv_sintetico), "--salida-dir", str(salida),
                        "--artefactos-dir", str(arte), "--n-lambdas", "3"])
    assert r2["metricas_cv"] == m
