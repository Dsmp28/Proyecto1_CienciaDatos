"""Guardado y carga de modelos con metadatos y verificación de versión/huella."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from ml import config as cfg


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=cfg.REPO, capture_output=True, text=True,
                              check=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def guardar_modelo(pipeline, metadatos: dict | None = None, directorio: Path | None = None,
                   version: str = cfg.VERSION_MODELO) -> Path:
    """Escribe `churn_persona_v<version>.joblib` y su `.json`, y apunta `ACTUAL` a él. Devuelve la ruta del joblib.
    `metadatos` aporta lo que ya se conoce (metricas_cv, umbral, ...); el resto se completa aquí."""
    directorio = Path(directorio) if directorio else cfg.MODELOS
    directorio.mkdir(parents=True, exist_ok=True)
    nombre = f"churn_persona_v{version}.joblib"
    ruta = directorio / nombre
    joblib.dump(pipeline, ruta)
    meta = {
        "version": version,
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit_git": _commit(),
        "features": cfg.FEATURES,
        "umbral": None,
        "semilla": cfg.SEMILLA,
        "versiones": {"scikit-learn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__},
        "metricas_cv": None,
        **(metadatos or {}),
        "sha256_joblib": _sha256(ruta),
    }
    (directorio / f"churn_persona_v{version}.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, default=str) + "\n")
    (directorio / "ACTUAL").write_text(nombre + "\n")
    return ruta


def cargar_modelo(ruta: Path | None = None, directorio: Path | None = None):
    """(pipeline, metadatos). Sin `ruta` usa el archivo que indica `ACTUAL`. Exige la misma versión de scikit-learn
    con la que se guardó y que el sha256 coincida con el de los metadatos."""
    directorio = Path(directorio) if directorio else cfg.MODELOS
    if ruta is None:
        ruta = directorio / (directorio / "ACTUAL").read_text().strip()
    ruta = Path(ruta)
    meta = json.loads(ruta.with_suffix(".json").read_text())
    esperada = meta["versiones"]["scikit-learn"]
    if esperada != sklearn.__version__:
        raise RuntimeError(f"scikit-learn {sklearn.__version__} != {esperada} con la que se guardó el modelo")
    if _sha256(ruta) != meta["sha256_joblib"]:
        raise RuntimeError(f"sha256 de {ruta.name} no coincide con sus metadatos")
    return joblib.load(ruta), meta
