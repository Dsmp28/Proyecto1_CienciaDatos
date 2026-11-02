"""Métricas: Average Precision (principal), ROC-AUC y Brier (secundarias)."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

NOMBRES = ("ap", "roc_auc", "brier")


def evaluar(y, p) -> dict:
    y = np.asarray(y)
    p = np.asarray(p, dtype=float)
    return {
        "ap": float(average_precision_score(y, p)),
        "roc_auc": float(roc_auc_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
    }


def resumen_cv(lista: list[dict]) -> dict:
    """Media y desviación estándar muestral (ddof=1) de cada métrica entre folds."""
    out = {}
    for k in NOMBRES:
        v = np.array([d[k] for d in lista], dtype=float)
        out[f"{k}_media"] = float(v.mean())
        out[f"{k}_sd"] = float(v.std(ddof=1)) if len(v) > 1 else 0.0
    return out


def tabla_markdown(filas: list[dict], columnas: list[str], formato: str = "{:.4f}") -> str:
    """Tabla Markdown; los floats se formatean, el resto se imprime tal cual."""
    def f(v):
        return formato.format(v) if isinstance(v, (float, np.floating)) else str(v)
    enc = "| " + " | ".join(columnas) + " |"
    sep = "|" + "|".join("---" for _ in columnas) + "|"
    cuerpo = ["| " + " | ".join(f(fila.get(c, "")) for c in columnas) + " |" for fila in filas]
    return "\n".join([enc, sep, *cuerpo]) + "\n"
