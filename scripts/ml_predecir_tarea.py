#!/usr/bin/env python
"""Tarea `ml_predecir_corte_c` del DAG: predice el corte con el modelo ACTUAL y sube el CSV al lago.

Entorno: FECHA_CORTE_PREDICCION (AAAA-MM-DD), RUN_ID. Salida 99 si no existe `ml/modelos/ACTUAL` (el DAG la toma
como "omitida"). Escribe /opt/airflow/salidas/predicciones_<run_id>.csv (o $SALIDAS_DIR) y lo sube a
gs://<lake>/ml/predicciones/<run_id>/predicciones_corte_<fecha>.csv.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(os.environ.get("REPO_DIR") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(REPO))

SALTAR = 99


def nombre_seguro(run_id: str) -> str:
    """El run_id llega del entorno: solo caracteres de nombre de archivo."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", run_id)


def main() -> int:
    fecha = os.environ.get("FECHA_CORTE_PREDICCION", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        print(f"ERROR: FECHA_CORTE_PREDICCION inválida: {fecha!r}")
        return 1
    if not (REPO / "ml" / "modelos" / "ACTUAL").exists():
        print("Sin ml/modelos/ACTUAL: no hay modelo entrenado, se omite la predicción.")
        return SALTAR
    from ingest.common import LAKE_BUCKET, gcs_client, run_id_actual
    from ml.prediccion import ejecutar

    run_id = nombre_seguro(run_id_actual())
    salidas = Path(os.environ.get("SALIDAS_DIR", "/opt/airflow/salidas"))
    datos = os.environ.get("DATOS_DIR", "/opt/airflow/datos_red")
    salida = salidas / f"predicciones_{run_id}.csv"
    codigo = ejecutar(datos, fecha, origen="bigquery", salida=salida, modelo="ACTUAL")
    if codigo != 0:
        return codigo
    destino = f"ml/predicciones/{run_id}/predicciones_corte_{fecha}.csv"
    gcs_client().bucket(LAKE_BUCKET).blob(destino).upload_from_filename(str(salida), content_type="text/csv")
    print(f"Subido a gs://{LAKE_BUCKET}/{destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
