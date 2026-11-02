"""Líneas base obligatorias en toda tabla de resultados."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin


class BaselineConstante(ClassifierMixin, BaseEstimator):
    """Predice la tasa positiva del conjunto de entrenamiento para todos. Su AP es la tasa positiva de validación
    (piso de referencia: un modelo que no supere esto no aporta ranking)."""

    def fit(self, X, y):
        y = np.asarray(y)
        self.classes_ = np.array([0, 1])
        self.tasa_ = float(np.mean(y))
        return self

    def predict_proba(self, X):
        n = len(X)
        return np.column_stack([np.full(n, 1 - self.tasa_), np.full(n, self.tasa_)])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


class BaselineUnaFeature(ClassifierMixin, BaseEstimator):
    """Puntaje de riesgo = rank percentil de una sola feature, sin entrenar nada.

    Justificación a priori (fijada antes de ver resultados): quien lleva más días sin viajar (`dias_desde_ultimo`)
    es quien tiene más probabilidad de seguir sin viajar en los próximos 30 días; la inactividad reciente es la regla
    de negocio más simple y la que usaría un analista sin modelo. `signo=+1`: valor alto = más riesgo; `-1` invierte.
    El puntaje está en (0, 1] por ranking (empates por promedio; nulos = 0.5), así que solo sirve para ordenar
    (AP, ROC-AUC); su Brier no es interpretable como probabilidad calibrada. El ranking se calcula sobre el
    conjunto que se puntúa.
    """

    def __init__(self, feature: str = "dias_desde_ultimo", signo: int = 1):
        self.feature = feature
        self.signo = signo

    def fit(self, X=None, y=None):
        self.classes_ = np.array([0, 1])
        return self

    def puntaje(self, X: pd.DataFrame) -> np.ndarray:
        v = pd.to_numeric(X[self.feature], errors="coerce") * self.signo
        return v.rank(pct=True, method="average").fillna(0.5).to_numpy()

    def predict_proba(self, X):
        s = self.puntaje(X)
        return np.column_stack([1 - s, s])

    def predict(self, X):
        return (self.puntaje(X) >= 0.5).astype(int)
