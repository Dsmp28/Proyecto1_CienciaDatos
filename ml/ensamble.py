"""Ensambles de árboles (HistGradientBoosting y RandomForest) con los mismos folds de A, importancia por permutación
y diagnóstico sesgo-varianza."""
from __future__ import annotations

import itertools
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score

from ml import config as cfg
from ml.pipeline import construir_pipeline

GRILLA_HGB = {
    "learning_rate": [0.05, 0.1],
    "max_iter": [200, 400],
    "max_leaf_nodes": [15, 31],
    "l2_regularization": [0.0, 1.0],
}

# Umbrales del diagnóstico sesgo-varianza (AP en [0, 1]); documentados en fase2_sesgo_varianza.md.
UMBRAL_BRECHA_ALTA = 0.10     # AP train - AP val >= 0.10  -> varianza alta (sobreajuste)
UMBRAL_BRECHA_PEQUENA = 0.05  # brecha < 0.05 se considera "pequeña"
UMBRAL_MEJORA_BAJA = 0.10     # AP val - tasa positiva < 0.10 se considera "AP de validación baja" (poco sobre el azar)


def _hgb(**params) -> HistGradientBoostingClassifier:
    # early_stopping=False: la selección de max_iter es explícita (grilla) y no usa datos de validación internos.
    return HistGradientBoostingClassifier(random_state=cfg.SEMILLA, early_stopping=False, **params)


def _rf() -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=400, min_samples_leaf=5, random_state=cfg.SEMILLA, n_jobs=-1)


def _pipeline(modelo):
    """Pipeline con el preprocesador común, forzado a salida densa (los árboles de sklearn/HGB no usan matrices dispersas)."""
    pipe = construir_pipeline(modelo)
    pipe.named_steps["pre"].set_params(sparse_threshold=0.0)
    return pipe


def _cv(fabrica, X, y, folds, guardar_pipelines: bool = False):
    """CV con los folds dados. Devuelve (ap_val por fold, ap_train por fold, oof, pipelines por fold o None)."""
    ks = sorted(set(folds.tolist()))
    ap_val, ap_tr, pipes = [], [], []
    oof = np.zeros(len(y))
    for k in ks:
        tr, va = folds != k, folds == k
        pipe = _pipeline(fabrica()).fit(X[tr], y[tr])
        p_va = pipe.predict_proba(X[va])[:, 1]
        oof[va] = p_va
        ap_val.append(average_precision_score(y[va], p_va))
        ap_tr.append(average_precision_score(y[tr], pipe.predict_proba(X[tr])[:, 1]))
        if guardar_pipelines:
            pipes.append(pipe)
    return np.array(ap_val), np.array(ap_tr), oof, (pipes if guardar_pipelines else None)


def _sd(v) -> float:
    return float(np.std(v, ddof=1)) if len(v) > 1 else 0.0


def entrenar_ensamble(X, y, folds, grilla: dict | None = None, tiempos: dict | None = None):
    """HistGradientBoosting con grilla evaluada en los mismos folds. Devuelve (resultados, modelo, oof, pipelines):

    - resultados: DataFrame (una fila por configuración: parámetros, ap_val_media, ap_val_sd, ap_train_media,
      es_optimo). Mejor = mayor AP de validación media (empate: la primera de la grilla, la más simple).
    - modelo: Pipeline con la mejor configuración reentrenado en todo A.
    - oof: probabilidades fuera de muestra (alineadas con X) de la mejor configuración.
    - pipelines: lista de Pipelines por fold (entrenados en sus 4 folds de entrenamiento), para la importancia.
    """
    t0 = time.perf_counter()
    grilla = GRILLA_HGB if grilla is None else grilla
    X = X.reset_index(drop=True)
    y = np.asarray(y)
    folds = np.asarray(folds)
    nombres = list(grilla)
    filas = []
    for valores in itertools.product(*(grilla[n] for n in nombres)):
        params = dict(zip(nombres, valores))
        ap_val, ap_tr, _, _ = _cv(lambda: _hgb(**params), X, y, folds)
        filas.append({**params, "ap_val_media": float(ap_val.mean()), "ap_val_sd": _sd(ap_val),
                      "ap_train_media": float(ap_tr.mean())})
    res = pd.DataFrame(filas)
    res["es_optimo"] = False
    i_mejor = int(res["ap_val_media"].idxmax())  # idxmax devuelve la primera en empate
    res.loc[i_mejor, "es_optimo"] = True
    mejor = {n: res.loc[i_mejor, n].item() for n in nombres}
    t1 = time.perf_counter()
    _, _, oof, pipes = _cv(lambda: _hgb(**mejor), X, y, folds, guardar_pipelines=True)
    modelo = _pipeline(_hgb(**mejor)).fit(X, y)
    if tiempos is not None:
        tiempos["hgb_cv_s"] = t1 - t0
        tiempos["hgb_oof_y_ajuste_final_s"] = time.perf_counter() - t1
    return res, modelo, oof, pipes


def entrenar_random_forest(X, y, folds, tiempos: dict | None = None):
    """RandomForest (400 árboles, min_samples_leaf=5), sin grilla. Devuelve (fila_resultados, modelo, oof)."""
    t0 = time.perf_counter()
    X = X.reset_index(drop=True)
    y = np.asarray(y)
    folds = np.asarray(folds)
    ap_val, ap_tr, oof, _ = _cv(_rf, X, y, folds)
    t1 = time.perf_counter()
    modelo = _pipeline(_rf()).fit(X, y)
    if tiempos is not None:
        tiempos["rf_cv_s"] = t1 - t0
        tiempos["rf_ajuste_final_s"] = time.perf_counter() - t1
    fila = {"n_estimators": 400, "min_samples_leaf": 5, "ap_val_media": float(ap_val.mean()),
            "ap_val_sd": _sd(ap_val), "ap_train_media": float(ap_tr.mean())}
    return fila, modelo, oof


def importancia_permutacion(pipeline_por_fold, X, y, folds, n_repeats: int = 10, top: int = 10) -> pd.DataFrame:
    """Importancia por permutación en el fold de VALIDACIÓN de cada pliegue (scoring AP; se permutan las columnas
    originales, antes del preprocesamiento), promediada entre folds. Devuelve las `top` features con mayor caída de
    AP: (feature, importancia_media, sd). `sd` = desviación entre folds de la importancia de cada fold."""
    X = X.reset_index(drop=True)
    y = np.asarray(y)
    folds = np.asarray(folds)
    ks = sorted(set(folds.tolist()))
    if len(pipeline_por_fold) != len(ks):
        raise ValueError("se espera un pipeline por fold")
    por_fold = []
    for k, pipe in zip(ks, pipeline_por_fold):
        va = folds == k
        r = permutation_importance(pipe, X[va], y[va], scoring="average_precision", n_repeats=n_repeats,
                                   random_state=cfg.SEMILLA, n_jobs=1)
        por_fold.append(r.importances_mean)
    m = np.vstack(por_fold)
    out = pd.DataFrame({"feature": list(X.columns), "importancia_media": m.mean(axis=0),
                        "sd": m.std(axis=0, ddof=1) if len(ks) > 1 else 0.0})
    return out.sort_values("importancia_media", ascending=False, kind="stable").head(top).reset_index(drop=True)


def etiqueta_sesgo_varianza(ap_train: float, ap_val: float, tasa: float) -> str:
    brecha = ap_train - ap_val
    if brecha >= UMBRAL_BRECHA_ALTA:
        return "varianza alta"
    if (ap_val - tasa) < UMBRAL_MEJORA_BAJA and brecha < UMBRAL_BRECHA_PEQUENA:
        return "sesgo alto"
    return "equilibrado"


def tabla_sesgo_varianza(resultados_por_modelo: dict, tasa: float | None = None) -> pd.DataFrame:
    """`resultados_por_modelo`: {nombre: {'ap_train': x, 'ap_val': y}} (acepta también ap_train_media/ap_val_media).
    `tasa` = tasa positiva de A (AP del baseline constante); si falta se toma de la clave 'tasa' del propio modelo o 0.

    Reglas (umbrales en las constantes del módulo):
    - 'varianza alta': brecha = AP train - AP val >= 0.10.
    - 'sesgo alto': brecha < 0.05 y AP val - tasa < 0.10 (el modelo rinde poco por encima del azar tanto en train
      como en val: no aprende lo suficiente).
    - 'equilibrado': el resto.
    """
    filas = []
    for nombre, d in resultados_por_modelo.items():
        tr = d.get("ap_train", d.get("ap_train_media"))
        va = d.get("ap_val", d.get("ap_val_media"))
        t = d.get("tasa", tasa if tasa is not None else 0.0)
        filas.append({"modelo": nombre, "ap_train": float(tr), "ap_val": float(va), "brecha": float(tr - va),
                      "diagnostico": etiqueta_sesgo_varianza(tr, va, t)})
    return pd.DataFrame(filas)
