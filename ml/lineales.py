"""Regresión logística con castigos L2, L1 y ElasticNet (saga), grilla de λ y selección por AP de validación."""
from __future__ import annotations

import time
import warnings

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.base import clone
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score

from ml import config as cfg
from ml.pipeline import construir_pipeline, construir_preprocesador

# l1_ratio del castigo (sklearn >= 1.8: 0 = L2, 1 = L1, intermedio = ElasticNet; `penalty` está en desuso).
CASTIGOS = {"L2": 0.0, "L1": 1.0, "ElasticNet": 0.5}
LAMBDAS = np.logspace(-4, 2, 13)


def _logistica(castigo: str, lam: float) -> LogisticRegression:
    return LogisticRegression(solver="saga", l1_ratio=CASTIGOS[castigo], C=1.0 / lam, max_iter=5000,
                              random_state=cfg.SEMILLA)


def _ajustar(castigo, lam, Xtr, ytr, Xva, yva):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        m = _logistica(castigo, lam).fit(Xtr, ytr)
    return (average_precision_score(yva, m.predict_proba(Xva)[:, 1]),
            average_precision_score(ytr, m.predict_proba(Xtr)[:, 1]))


def entrenar_logisticas(X, y, folds, lambdas=None, castigos=None, n_jobs: int = -1, tiempos: dict | None = None):
    """CV con los folds dados. Devuelve (resultados, modelos, oof):

    - resultados: DataFrame largo (castigo, lambda, C, ap_val_media, ap_val_sd, ap_train_media, es_optimo).
    - modelos: {castigo: Pipeline reentrenado en todo A con λ*}; λ* = argmax de AP de validación media
      (empate: el mayor λ, es decir el modelo más regularizado/simple).
    - oof: {castigo: probabilidades fuera de muestra (alineadas con X) con λ*}.
    El preprocesador se ajusta dentro de cada fold (sin fuga de la validación).
    Si se pasa `tiempos` (dict) se llenan `cv_s` (CV, selección y OOF) y `ajuste_final_s` (reentrenamiento en A).
    """
    t0 = time.perf_counter()
    lambdas = np.asarray(LAMBDAS if lambdas is None else lambdas, dtype=float)
    castigos = list(CASTIGOS) if castigos is None else list(castigos)
    X = X.reset_index(drop=True)
    y = np.asarray(y)
    folds = np.asarray(folds)
    ks = sorted(set(folds.tolist()))

    matrices = []
    for k in ks:
        tr, va = folds != k, folds == k
        pre = clone(construir_preprocesador()).fit(X[tr], y[tr])
        matrices.append((pre.transform(X[tr]), y[tr], pre.transform(X[va]), y[va], va))

    tareas = [(c, lam, i) for c in castigos for lam in lambdas for i in range(len(ks))]
    salidas = Parallel(n_jobs=n_jobs)(
        delayed(_ajustar)(c, lam, *matrices[i][:4]) for c, lam, i in tareas)
    largo = pd.DataFrame(tareas, columns=["castigo", "lambda", "fold"])
    largo["ap_val"] = [s[0] for s in salidas]
    largo["ap_train"] = [s[1] for s in salidas]
    res = (largo.groupby(["castigo", "lambda"], sort=False)
           .agg(ap_val_media=("ap_val", "mean"), ap_val_sd=("ap_val", lambda s: s.std(ddof=1) if len(s) > 1 else 0.0),
                ap_train_media=("ap_train", "mean")).reset_index())
    res["C"] = 1.0 / res["lambda"]
    res["es_optimo"] = False

    modelos, oof = {}, {}
    for c in castigos:
        sub = res[res["castigo"] == c]
        mejor = sub[np.isclose(sub["ap_val_media"], sub["ap_val_media"].max(), rtol=0, atol=1e-12)]
        lam_opt = float(mejor["lambda"].max())
        res.loc[(res["castigo"] == c) & np.isclose(res["lambda"], lam_opt, rtol=1e-9), "es_optimo"] = True
        p = np.zeros(len(y))
        for i, k in enumerate(ks):
            Xtr, ytr, Xva, _, va = matrices[i]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ConvergenceWarning)
                p[va] = _logistica(c, lam_opt).fit(Xtr, ytr).predict_proba(Xva)[:, 1]
        oof[c] = p
    t1 = time.perf_counter()
    for c in castigos:
        lam_opt = float(res[(res["castigo"] == c) & res["es_optimo"]]["lambda"].iloc[0])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            modelos[c] = construir_pipeline(_logistica(c, lam_opt)).fit(X, y)
    if tiempos is not None:
        tiempos["cv_s"] = t1 - t0
        tiempos["ajuste_final_s"] = time.perf_counter() - t1
    cols = ["castigo", "lambda", "C", "ap_val_media", "ap_val_sd", "ap_train_media", "es_optimo"]
    return res[cols], modelos, oof


def coeficientes(modelo, nombres_features=None) -> pd.DataFrame:
    """Coeficientes (feature, coeficiente) sobre features estandarizadas, ordenados de mayor a menor.
    Positivo = empuja hacia churn. `nombres_features` por defecto sale del preprocesador del pipeline."""
    if nombres_features is None:
        nombres_features = modelo[:-1].get_feature_names_out()
    coef = modelo[-1].coef_.ravel()
    if len(coef) != len(nombres_features):
        raise ValueError("coeficientes y nombres de distinto largo")
    return (pd.DataFrame({"feature": list(nombres_features), "coeficiente": coef})
            .sort_values("coeficiente", ascending=False, kind="stable").reset_index(drop=True))


def top_coeficientes(df: pd.DataFrame, n: int = 5):
    """(top n hacia churn, top n protectores)."""
    return df.head(n).reset_index(drop=True), df.tail(n).iloc[::-1].reset_index(drop=True)
