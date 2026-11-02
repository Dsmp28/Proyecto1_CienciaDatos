"""Pruebas del paquete ml/ (fase 2) con datos sintéticos, sin red ni BigQuery."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from test_ml import sintetico  # generador sintético compartido con las pruebas de la fase 1

from ml import config as cfg
from ml import evaluar_b as eb
from ml.baselines import BaselineConstante
from ml.datos import cargar_dataset, preparar_xy
from ml.ensamble import entrenar_ensamble, entrenar_random_forest, importancia_permutacion, tabla_sesgo_varianza
from ml.entrenar import main as entrenar_main
from ml.folds import obtener_folds
from ml.persistencia import guardar_modelo
from ml.pipeline import construir_pipeline
from ml.segmentos import escribir_informe, segmentar
from ml.umbral import curva_ganancia, elegir_umbral, figura_curva_ganancia, ganancia, nota_calibracion, umbral_teorico

GRILLA_MINI = {"learning_rate": [0.1], "max_iter": [20, 40], "max_leaf_nodes": [7], "l2_regularization": [0.0, 1.0]}


@pytest.fixture(scope="module")
def csv_sintetico(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("datos2") / "churn_dataset.csv"
    sintetico(n_por_corte=500).to_csv(ruta, index=False)
    return ruta


@pytest.fixture(scope="module")
def datos_a(csv_sintetico, tmp_path_factory):
    X, y, ids = preparar_xy(cargar_dataset(["A"], "csv", csv_sintetico))
    folds = obtener_folds(ids, y, tmp_path_factory.mktemp("folds2") / "folds_A.csv")
    return X, y.to_numpy(), folds


# ---- umbral ----

def test_ganancia_y_umbral_teorico_a_mano():
    assert umbral_teorico() == pytest.approx(1 / 3)
    y = np.array([1, 0, 1, 0, 1])
    p = np.array([0.9, 0.8, 0.5, 0.2, 0.1])
    # u=0.5 contacta 3: TP=2, FP=1 -> 15*2 - 5*3 = 15
    assert ganancia(y, p, 0.5) == pytest.approx(15.0)
    assert ganancia(y, p, 0.0) == pytest.approx(15 * 3 - 5 * 5)
    assert ganancia(y, p, 1.0) == 0.0  # nadie con p >= 1


def test_curva_monotona_y_elegir_umbral():
    rng = np.random.default_rng(0)
    p = rng.random(2000)
    y = (rng.random(2000) < p).astype(int)  # calibrada
    c = curva_ganancia(y, p)
    assert len(c) == 201 and list(c.columns) == ["umbral", "contactados", "tp", "fp", "precision", "recall", "ganancia_q"]
    assert (np.diff(c["contactados"]) <= 0).all() and c["contactados"].iloc[0] == 2000
    assert (c["tp"] + c["fp"] == c["contactados"]).all()
    assert c["ganancia_q"].iloc[0] == pytest.approx(ganancia(y, p, 0.0))
    u = elegir_umbral(c)
    assert c["ganancia_q"].max() == pytest.approx(ganancia(y, p, u))
    assert abs(u - 1 / 3) < 0.1  # calibrado: el óptimo empírico cae cerca del teórico
    # empate: se queda con el mayor umbral
    plana = pd.DataFrame({"umbral": [0.0, 0.5, 1.0], "ganancia_q": [0.0, 7.0, 7.0]})
    assert elegir_umbral(plana) == 1.0


def test_figura_y_calibracion(tmp_path):
    rng = np.random.default_rng(1)
    p = rng.random(1500)
    y = (rng.random(1500) < p ** 2).astype(int)  # mal calibrada a propósito
    c = curva_ganancia(y, p)
    u = elegir_umbral(c)
    assert figura_curva_ganancia(c, u, tmp_path / "f" / "g.png").stat().st_size > 0
    r = nota_calibracion(y, p, 0.9, tmp_path / "calibracion.md")
    texto = (tmp_path / "calibracion.md").read_text()
    assert r["aviso_desvio"] and "Constancia" in texto and len(r["calibracion_deciles"]) == 10
    r2 = nota_calibracion(y, p, 0.35, tmp_path / "c2.md")
    assert not r2["aviso_desvio"] and "Constancia" not in (tmp_path / "c2.md").read_text()


# ---- ensamble ----

def test_ensamble_oof_mejor_config_e_importancia(datos_a):
    X, y, folds = datos_a
    tiempos = {}
    res, modelo, oof, pipes = entrenar_ensamble(X, y, folds, grilla=GRILLA_MINI, tiempos=tiempos)
    assert len(res) == 4 and res["es_optimo"].sum() == 1 and len(pipes) == cfg.N_FOLDS
    assert res[res["es_optimo"]]["ap_val_media"].iloc[0] == res["ap_val_media"].max()
    assert len(oof) == len(y) and ((oof >= 0) & (oof <= 1)).all() and (oof > 0).any()
    assert res["ap_val_media"].max() > y.mean() and (res["ap_train_media"] >= res["ap_val_media"] - 1e-9).all()
    assert tiempos["hgb_cv_s"] > 0
    assert modelo.predict_proba(X).shape == (len(y), 2)
    imp = importancia_permutacion(pipes, X, y, folds, n_repeats=2, top=10)
    assert len(imp) == 10 and set(imp.columns) == {"feature", "importancia_media", "sd"}
    assert imp["feature"].isin(cfg.FEATURES).all()
    assert imp["importancia_media"].is_monotonic_decreasing
    assert imp["feature"].iloc[0] in ("dias_desde_ultimo", "n_abordajes_28d")  # las que generan el churn sintético
    # determinista
    res2, _, oof2, _ = entrenar_ensamble(X, y, folds, grilla=GRILLA_MINI)
    assert np.allclose(oof, oof2) and res.equals(res2)


def test_random_forest(datos_a, monkeypatch):
    import ml.ensamble as ens
    monkeypatch.setattr(ens, "_rf", lambda: ens.RandomForestClassifier(n_estimators=15, min_samples_leaf=5,
                                                                       random_state=cfg.SEMILLA, n_jobs=1))
    X, y, folds = datos_a
    fila, modelo, oof = entrenar_random_forest(X, y, folds)
    assert fila["ap_val_media"] > y.mean() and len(oof) == len(y) and modelo.predict_proba(X).shape[1] == 2


def test_tabla_sesgo_varianza():
    t = tabla_sesgo_varianza({
        "sobreajustado": {"ap_train": 0.95, "ap_val": 0.60},
        "limitado": {"ap_train": 0.31, "ap_val": 0.30},
        "bueno": {"ap_train": 0.66, "ap_val": 0.62},
    }, tasa=0.25)
    d = dict(zip(t["modelo"], t["diagnostico"]))
    assert d == {"sobreajustado": "varianza alta", "limitado": "sesgo alto", "bueno": "equilibrado"}
    assert t.set_index("modelo").loc["sobreajustado", "brecha"] == pytest.approx(0.35)


# ---- segmentos ----

def test_segmentos(datos_a, tmp_path):
    X, y, _ = datos_a
    r = segmentar(X, y, ks=range(2, 5), n_init=2, max_muestra=300)
    assert r["k_elegido"] in (2, 3, 4) and list(r["tabla_k"]["k"]) == [2, 3, 4]
    assert r["tabla_k"]["inercia"].is_monotonic_decreasing and r["n_muestra_silueta"] == 300
    seg = r["tabla_segmentos"]
    assert len(seg) == r["k_elegido"] and seg["tamano"].sum() == len(y) and seg["nombre_sugerido"].is_unique
    assert len(r["discriminantes"]) == 8 and set(r["discriminantes"]) <= set(cfg.FEATURES_NUM)
    assert seg["tasa_abandono"].between(0, 1).all() and r["pca"].shape == (len(y), 2)
    escribir_informe(r, tmp_path, float(y.mean()))
    for f in ("segmentos.md", "segmentos_k.md", "acciones.md", "figuras/codo.png", "figuras/silueta.png",
              "figuras/pca_segmentos.png"):
        assert (tmp_path / f).stat().st_size > 0, f
    assert (tmp_path / "acciones.md").read_text().count("(propuesta)") >= 2 * r["k_elegido"]
    # no usa la etiqueta para agrupar
    r_sin = segmentar(X, None, ks=range(2, 5), n_init=2, max_muestra=300)
    assert (r_sin["etiquetas"] == r["etiquetas"]).all()


# ---- evaluar_b ----

@pytest.fixture()
def entorno_b(csv_sintetico, datos_a, tmp_path):
    X, y, _ = datos_a
    pipe = construir_pipeline(BaselineConstante()).fit(X, y)
    modelos = tmp_path / "modelos"
    ruta = guardar_modelo(pipe, {"umbral": 0.4, "metricas_cv": {"ap_media": 0.3}}, directorio=modelos)
    base = ["--origen", "csv", "--ruta-csv", str(csv_sintetico), "--salida-dir", str(tmp_path / "ev"),
            "--artefactos-dir", str(tmp_path / "art"), "--bitacora", str(tmp_path / "docs" / "BITACORA.md"),
            "--modelos-dir", str(modelos)]
    return base, ruta, tmp_path


def test_evaluar_b_aborta_sin_modelo_y_con_arbol_sucio(entorno_b, monkeypatch):
    base, ruta, tmp = entorno_b
    with pytest.raises(SystemExit):  # modelo inexistente
        eb.main(base + ["--permitir-sucio", "--modelo", str(tmp / "no_existe.joblib")])
    assert not (tmp / "art" / "evaluacion_b.json").exists()
    monkeypatch.setattr(eb, "arbol_sucio", lambda: [" M ml/algo.py"])
    with pytest.raises(SystemExit):
        eb.main(base)
    assert not (tmp / "art" / "evaluacion_b.json").exists()


def test_evaluar_b_una_sola_vez(entorno_b, datos_a):
    base, ruta, tmp = entorno_b
    r = eb.main(base + ["--permitir-sucio", "--modelo", "ACTUAL"])
    j = json.loads((tmp / "art" / "evaluacion_b.json").read_text())
    assert j["estado"] == "completada" and j["sha256_modelo"] == r["sha256_modelo"] and len(j["sha256_modelo"]) == 64
    assert j["umbral"] == 0.4 and j["inicio_ts"] and {"ap", "roc_auc", "brier"} <= set(j["metricas"])
    c = j["confusion"]
    assert c["tn"] + c["fp"] + c["fn"] + c["tp"] == j["n"] == 500
    # el baseline constante (p = tasa de A) con u=0.4 contacta a todos o a nadie: la ganancia coincide con la cuenta
    assert j["ganancia_q"] == pytest.approx(15 * c["tp"] - 5 * (c["tp"] + c["fp"]))
    assert j["ganancia_q_por_1000"] == pytest.approx(j["ganancia_q"] / 500 * 1000)
    bit = (tmp / "docs" / "BITACORA.md").read_text()
    assert bit.count(eb.MARCADOR) == 1 and j["sha256_modelo"] in bit
    assert (tmp / "ev" / "test_b.md").stat().st_size > 0
    # segunda llamada: aborta y no modifica nada
    antes = (tmp / "art" / "evaluacion_b.json").read_text()
    with pytest.raises(SystemExit):
        eb.main(base + ["--permitir-sucio"])
    assert (tmp / "art" / "evaluacion_b.json").read_text() == antes
    # solo el marcador en la bitácora también bloquea
    (tmp / "art" / "evaluacion_b.json").unlink()
    with pytest.raises(SystemExit):
        eb.main(base + ["--permitir-sucio"])
    # --forzar vacío no sirve; con justificación deja segunda entrada visible
    with pytest.raises(SystemExit):
        eb.main(base + ["--permitir-sucio", "--forzar", "  "])
    eb.main(base + ["--permitir-sucio", "--forzar", "reentrenado por error de datos"])
    bit = (tmp / "docs" / "BITACORA.md").read_text()
    assert bit.count(eb.MARCADOR) == 2 and "reentrenado por error de datos" in bit and "REPETIDA" in bit


def test_evaluar_b_no_reentrena_ni_usa_otro_corte(entorno_b, csv_sintetico, monkeypatch):
    base, ruta, tmp = entorno_b
    vistos = {}
    original = eb.cargar_dataset

    def espia(cortes, *a, **k):
        vistos["cortes"] = list(cortes)
        return original(cortes, *a, **k)
    monkeypatch.setattr(eb, "cargar_dataset", espia)
    eb.main(base + ["--permitir-sucio"])
    assert vistos["cortes"] == ["B"]


# ---- fase 2 de punta a punta ----

def test_entrenar_fase2_csv_punta_a_punta(csv_sintetico, tmp_path):
    salida, arte = tmp_path / "evidencia", tmp_path / "artefactos"
    args = ["--fase", "2", "--origen", "csv", "--ruta-csv", str(csv_sintetico), "--salida-dir", str(salida),
            "--artefactos-dir", str(arte), "--n-lambdas", "3", "--grilla-hgb", "reducida", "--n-repeats-perm", "2"]
    r = entrenar_main(args)  # el RF (400 árboles) se prueba aparte, con menos árboles
    for f in ("fase2_modelos.md", "fase2_sesgo_varianza.md", "fase2_importancias.md", "fase2_decision.md", "umbral.md",
              "calibracion.md", "fase2_tiempos.md", "figuras/ganancia_vs_umbral.png"):
        assert (salida / f).stat().st_size > 0, f
    assert (arte / "fase2_resultados.json").exists() and (arte / "modelos" / "ACTUAL").exists()
    tabla = (salida / "fase2_modelos.md").read_text()
    assert "HistGradientBoosting" in tabla and "Baseline constante" in tabla and "AP train" in tabla
    assert "15·" in (salida / "umbral.md").read_text() and "Por redactar" in (salida / "fase2_decision.md").read_text()
    m = r["metricas_cv"]
    assert m["hgb"]["ap_media"] > m["baseline_constante"]["ap_media"]
    assert r["modelo_final"] == max(("logistica_l2", "logistica_l1", "logistica_elasticnet", "hgb"),
                                    key=lambda c: m[c]["ap_media"])
    from ml.persistencia import cargar_modelo
    modelo, meta = cargar_modelo(directorio=arte / "modelos")
    assert meta["umbral"] == pytest.approx(r["u_estrella"]) and meta["modelo"] == r["modelo_final"]
    X, y, _ = preparar_xy(cargar_dataset(["A"], "csv", csv_sintetico))
    assert modelo.predict_proba(X).shape == (len(y), 2)
    # reutiliza la fase 1 y reproduce exactamente
    assert r["fase1_reutilizada"] is False
    r2 = entrenar_main(args + ["--modelo-final", "logistica_l2"])
    assert r2["fase1_reutilizada"] is True and r2["modelo_final"] == "logistica_l2"
    assert r2["metricas_cv"] == r["metricas_cv"]
