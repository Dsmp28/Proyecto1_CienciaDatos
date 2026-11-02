"""Exporta desde BigQuery las features de un corte a `predicciones/features_corte_<fecha>.csv`.

Es exactamente lo que `predecir.py --origen csv` lee: las columnas de `features.churn_dataset` (sin etiqueta) más
`tarjetas` de `silver.silver_unidad_tarjetas_corte`. Uso: `python -m ml.exportar --fecha-corte 2026-08-30`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ml import prediccion as pr


def exportar(fecha: str, sufijo: str = "", salida: Path | None = None) -> Path:
    fecha = pr.validar_fecha_corte(fecha)
    df = pr._consultar(pr.consulta_features(sufijo), fecha).sort_values("unidad_id")
    salida = Path(salida) if salida else pr.ruta_features_csv(fecha)
    salida.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(salida, index=False, lineterminator="\n", encoding="utf-8")
    return salida


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fecha-corte", default="2026-08-30")
    p.add_argument("--sufijo-dataset", default="")
    p.add_argument("--salida", default=None)
    a = p.parse_args(argv)
    print(exportar(a.fecha_corte, a.sufijo_dataset, a.salida))


if __name__ == "__main__":
    main()
