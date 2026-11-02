#!/usr/bin/env python
"""Tarea `ml_invariancia` del DAG: compara las predicciones de la corrida con las entregadas.

Referencia: predicciones/predicciones_corte_<fecha>.csv del repo; nueva: salidas/predicciones_<run_id>.csv de la tarea
anterior. Salida 99 (omitida) si falta cualquiera; 0 idénticas; 1 si difieren. Informe en salidas/.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(os.environ.get("REPO_DIR") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

SALTAR = 99


def main() -> int:
    from ml.invariancia import ejecutar
    from ml_predecir_tarea import nombre_seguro

    fecha = os.environ.get("FECHA_CORTE_PREDICCION", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        print(f"ERROR: FECHA_CORTE_PREDICCION inválida: {fecha!r}")
        return 1
    run_id = nombre_seguro(os.environ.get("RUN_ID") or "manual")
    salidas = Path(os.environ.get("SALIDAS_DIR", "/opt/airflow/salidas"))
    referencia = REPO / "predicciones" / f"predicciones_corte_{fecha}.csv"
    nueva = salidas / f"predicciones_{run_id}.csv"
    for ruta in (referencia, nueva):
        if not ruta.exists():
            print(f"No existe {ruta}: se omite la comprobación de invariancia.")
            return SALTAR
    return ejecutar(referencia, nueva, salidas / f"invariancia_{run_id}.md")


if __name__ == "__main__":
    sys.exit(main())
