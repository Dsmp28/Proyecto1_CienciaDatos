#!/usr/bin/env python
"""Predicción de churn por persona para un corte: `python predecir.py --datos <carpeta> --fecha-corte 2026-08-30`.

Verifica las huellas de los 9 archivos crudos, carga las features del corte y puntúa con el modelo guardado (nunca
reentrena). Escribe `predicciones/predicciones_corte_<fecha>.csv` con `unidad_id,tarjetas,puntaje,contactar`.
Códigos de salida: 0 ok; 2 huellas distintas, archivos faltantes o fecha fuera de `fechas_corte`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ml.prediccion import ejecutar  # noqa: E402


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--datos", required=True, help="carpeta con los 9 archivos crudos")
    p.add_argument("--fecha-corte", required=True, help="AAAA-MM-DD; debe estar en fechas_corte de dbt_project.yml")
    p.add_argument("--origen", choices=["bigquery", "csv"], default="bigquery")
    p.add_argument("--salida", default=None, help="por defecto predicciones/predicciones_corte_<fecha>.csv")
    p.add_argument("--modelo", default="ACTUAL", help="ruta al .joblib o ACTUAL (ml/modelos/ACTUAL)")
    p.add_argument("--sin-verificar", action="store_true", help="solo avisa si las huellas difieren")
    p.add_argument("--sufijo-dataset", default="", help="sufijo de los datasets (p. ej. _recorte)")
    p.add_argument("--umbral", type=float, default=None, help="reemplaza el umbral de los metadatos del modelo")
    p.add_argument("--features-csv", default=None, help="modo csv: ruta del CSV de features (por defecto "
                   "predicciones/features_corte_<fecha>.csv)")
    return p


def main(argv=None) -> int:
    a = construir_parser().parse_args(argv)
    return ejecutar(a.datos, a.fecha_corte, a.origen, a.salida, a.modelo, a.sin_verificar, a.sufijo_dataset,
                    a.umbral, a.features_csv)


if __name__ == "__main__":
    sys.exit(main())
