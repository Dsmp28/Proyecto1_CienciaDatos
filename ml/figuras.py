"""Figuras de la fase 1 (backend Agg, sin pantalla)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

COLORES = {"L2": "#1f77b4", "L1": "#d95f02", "ElasticNet": "#2ca02c"}


def figura_ap_vs_lambda(resultados, ruta, linea_base: float | None = None) -> Path:
    """AP de validación (media ± sd entre folds) contra log10(λ), una curva por castigo; ★ marca λ*.
    `linea_base` (opcional) dibuja la tasa positiva (AP del baseline constante)."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.5, 4.6), dpi=130)
    for castigo, sub in resultados.groupby("castigo", sort=False):
        sub = sub.sort_values("lambda")
        x, m, s = sub["lambda"].to_numpy(), sub["ap_val_media"].to_numpy(), sub["ap_val_sd"].to_numpy()
        col = COLORES.get(castigo)
        ax.plot(x, m, marker="o", ms=3.5, lw=1.6, color=col, label=castigo)
        ax.fill_between(x, m - s, m + s, color=col, alpha=0.15, lw=0)
        opt = sub[sub["es_optimo"]]
        if len(opt):
            ax.plot(opt["lambda"], opt["ap_val_media"], marker="*", ms=15, color=col, mec="black", mew=0.8, ls="none")
    if linea_base is not None:
        ax.axhline(linea_base, color="gray", ls="--", lw=1, label="baseline constante")
    ax.set_xscale("log")
    ax.set_xlabel("λ (C = 1/λ), escala log")
    ax.set_ylabel("Average Precision en validación")
    ax.set_title("AP vs λ por castigo (media ± sd, 5 folds de A; ★ = λ*)")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(ruta)
    plt.close(fig)
    return ruta
