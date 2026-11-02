"""Folds de validación cruzada: se calculan una sola vez sobre A y se reutilizan en todos los modelos."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from ml import config as cfg


def obtener_folds(ids, y, ruta: Path | None = None) -> np.ndarray:
    """Devuelve un arreglo `fold` (0..N_FOLDS-1) alineado con `ids`.

    Si `ruta` (por defecto `ml/artefactos/folds_A.csv`) existe se reutiliza, verificando que cubre exactamente las
    unidades de `ids`; si no, se calcula con StratifiedKFold(5, shuffle=True, random_state=2026) sobre las unidades
    ordenadas por `unidad_id` (independiente del orden de las filas) y se persiste.
    """
    ruta = Path(ruta) if ruta else cfg.ARTEFACTOS / "folds_A.csv"
    ids = pd.Series(list(ids), dtype="object")
    y = np.asarray(y)
    if ids.duplicated().any():
        raise ValueError("unidad_id duplicado en A: los folds exigen una fila por unidad")
    if len(ids) != len(y):
        raise ValueError("ids e y de distinto largo")

    if ruta.exists():
        guardado = pd.read_csv(ruta, dtype={"unidad_id": "object", "fold": "int64"})
        if set(guardado["unidad_id"]) != set(ids) or len(guardado) != len(ids):
            raise ValueError(f"{ruta} no cubre exactamente las unidades de A; bórralo solo si el dataset cambió "
                             "a propósito (invalida todos los resultados previos)")
        mapa = guardado.set_index("unidad_id")["fold"]
        return mapa.loc[ids].to_numpy()

    orden = np.argsort(ids.to_numpy().astype(str), kind="stable")
    fold_ord = np.empty(len(ids), dtype="int64")
    skf = StratifiedKFold(n_splits=cfg.N_FOLDS, shuffle=True, random_state=cfg.SEMILLA)
    for k, (_, val) in enumerate(skf.split(np.zeros(len(ids)), y[orden])):
        fold_ord[val] = k
    folds = np.empty(len(ids), dtype="int64")
    folds[orden] = fold_ord
    ruta.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"unidad_id": ids[orden].to_numpy(), "fold": fold_ord}).to_csv(ruta, index=False)
    return folds
