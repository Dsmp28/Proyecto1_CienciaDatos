"""Umbral de decisión por ganancia económica (campaña de retención) y nota de calibración.

Escenario: contactar a una persona cuesta COSTO_CONTACTO (Q5); si va a abandonar (y=1) la campaña la retiene con
probabilidad TASA_RETENCION (25 %) y retenida vale VALOR_RETENIDO (Q60). Para quien se contacta:
    ganancia_i = TASA * VALOR * y_i - COSTO = 15 * y_i - 5
    G(u) = sum_{p_i >= u} ganancia_i = 15 * TP - 5 * (TP + FP)
Contactar conviene si P(y=1) * 15 > 5, es decir p > COSTO / (TASA * VALOR) = 1/3 (umbral teórico, válido solo si
las probabilidades están calibradas). El umbral operativo u* se elige empíricamente sobre las predicciones
fuera de muestra (OOF) de A: argmax de G(u).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
from sklearn.metrics import brier_score_loss  # noqa: E402

from ml import config as cfg  # noqa: E402
from ml.metricas import tabla_markdown  # noqa: E402

TOLERANCIA_UMBRAL = 0.1  # |u* - 1/3| mayor a esto se deja por escrito en el informe de calibración


def ganancia_por_contactado() -> float:
    return cfg.TASA_RETENCION * cfg.VALOR_RETENIDO


def umbral_teorico() -> float:
    return cfg.COSTO_CONTACTO / (cfg.TASA_RETENCION * cfg.VALOR_RETENIDO)


def ganancia(y, p, u: float) -> float:
    """G(u) = sum_{p_i >= u} (TASA * VALOR * y_i - COSTO) en quetzales."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    sel = p >= u
    return float((ganancia_por_contactado() * y[sel] - cfg.COSTO_CONTACTO).sum())


def curva_ganancia(y, p, umbrales=None) -> pd.DataFrame:
    """(umbral, contactados, tp, fp, precision, recall, ganancia_q) para cada umbral (contactar si p >= umbral)."""
    umbrales = np.linspace(0, 1, 201) if umbrales is None else np.asarray(umbrales, dtype=float)
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    positivos = int(y.sum())
    filas = []
    for u in umbrales:
        sel = p >= u
        n = int(sel.sum())
        tp = int(y[sel].sum())
        fp = n - tp
        filas.append({
            "umbral": float(u), "contactados": n, "tp": tp, "fp": fp,
            "precision": tp / n if n else np.nan, "recall": tp / positivos if positivos else np.nan,
            "ganancia_q": ganancia_por_contactado() * tp - cfg.COSTO_CONTACTO * n,
        })
    return pd.DataFrame(filas)


def elegir_umbral(curva: pd.DataFrame) -> float:
    """Umbral de máxima ganancia; en empate, el mayor (contacta menos gente para la misma ganancia)."""
    mx = curva["ganancia_q"].max()
    return float(curva.loc[np.isclose(curva["ganancia_q"], mx, rtol=0, atol=1e-9), "umbral"].max())


def figura_curva_ganancia(curva: pd.DataFrame, u_estrella: float, ruta) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.5, 4.6), dpi=130)
    ax.plot(curva["umbral"], curva["ganancia_q"], color="#1f77b4", lw=1.8)
    g = float(curva.loc[np.isclose(curva["umbral"], u_estrella), "ganancia_q"].iloc[0])
    ax.axvline(umbral_teorico(), color="gray", ls="--", lw=1.2, label=f"umbral teórico 1/3 = {umbral_teorico():.3f}")
    ax.axvline(u_estrella, color="#d95f02", lw=1.2, label=f"u* = {u_estrella:.3f}")
    ax.plot([u_estrella], [g], marker="*", ms=15, color="#d95f02", mec="black", mew=0.8, ls="none")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_xlabel("umbral u (se contacta si p ≥ u)")
    ax.set_ylabel("ganancia en Q (predicciones fuera de muestra de A)")
    ax.set_title("Ganancia vs umbral")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(ruta)
    plt.close(fig)
    return ruta


def nota_calibracion(y, p, u_estrella: float, ruta=None) -> dict:
    """Brier y curva de calibración por deciles (cuantiles de p). Escribe `calibracion.md` si se da `ruta`.
    No recalibra: si |u* - 1/3| > 0.1 solo deja constancia."""
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    brier = float(brier_score_loss(y, p))
    brier_const = float(brier_score_loss(y, np.full(len(y), y.mean())))
    frac, medio = calibration_curve(y, p, n_bins=10, strategy="quantile")
    tabla = pd.DataFrame({"decil": np.arange(1, len(frac) + 1), "p_media": medio, "tasa_observada": frac})
    desvio = abs(u_estrella - umbral_teorico())
    aviso = desvio > TOLERANCIA_UMBRAL
    res = {"brier": brier, "brier_constante": brier_const, "u_estrella": float(u_estrella),
           "u_teorico": umbral_teorico(), "desvio_umbral": float(desvio), "aviso_desvio": bool(aviso),
           "calibracion_deciles": tabla.to_dict("records")}
    if ruta is not None:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        texto = [
            "# Nota de calibración (predicciones fuera de muestra de A)\n",
            f"- Brier del modelo: {brier:.4f}; Brier del baseline constante (tasa de A): {brier_const:.4f}.",
            f"- Umbral empírico u* = {u_estrella:.3f}; umbral teórico (costo / (tasa · valor)) = {umbral_teorico():.3f}; "
            f"diferencia absoluta = {desvio:.3f}.\n",
            "Curva de calibración por deciles de la probabilidad predicha (un modelo calibrado tiene "
            "p media ≈ tasa observada):\n",
            tabla_markdown(tabla.to_dict("records"), ["decil", "p_media", "tasa_observada"]),
        ]
        if aviso:
            texto.append(f"\n**Constancia:** |u* − 1/3| = {desvio:.3f} supera {TOLERANCIA_UMBRAL}. Las probabilidades "
                         "no están bien calibradas en la zona de decisión (o la curva de ganancia es plana); el "
                         "umbral teórico no aplica directamente y se usa u* empírico. No se recalibró.\n")
        else:
            texto.append(f"\nu* queda a menos de {TOLERANCIA_UMBRAL} del umbral teórico: no se requiere comentario "
                         "adicional ni recalibración.\n")
        ruta.write_text("\n".join(texto))
    return res
