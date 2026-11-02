"""Pruebas de la comparación pura de ml.prueba_recorte (sin red)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.prueba_recorte import comparar, informe_markdown  # noqa: E402


def feats() -> pd.DataFrame:
    return pd.DataFrame({
        "unidad_id": ["a", "b", "c"], "corte": "A", "fecha_corte": "2026-07-01",
        "n_abordajes_28d": [5.0, 8.0, 3.0], "ratio_ult14_prev14": [np.nan, 1.5, 0.5],
        "modo_principal": ["TM", None, "TU"], "tiene_padron_a_t": [True, False, True],
    })


def test_iguales_sin_diferencias():
    r = comparar(feats(), feats().assign(corte="B"))  # la letra de corte no cuenta
    assert r["sin_diferencias"] and r["diferencias_totales"] == 0 and r["filas_comparadas"] == 3
    assert r["except_completa_menos_recorte"] == 0 and r["except_recorte_menos_completa"] == 0
    assert "SIN DIFERENCIAS" in informe_markdown(r, "A", "2026-07-01")


def test_tolerancia_float():
    n = feats()
    n.loc[0, "n_abordajes_28d"] += 5e-7
    assert comparar(feats(), n)["sin_diferencias"]


def test_una_feature_distinta():
    n = feats()
    n.loc[1, "ratio_ult14_prev14"] = 2.0
    n.loc[0, "ratio_ult14_prev14"] = 0.1  # nulo vs valor
    r = comparar(feats(), n)
    assert not r["sin_diferencias"]
    assert r["por_columna"]["ratio_ult14_prev14"] == 2
    assert sum(v for c, v in r["por_columna"].items() if c != "ratio_ult14_prev14") == 0
    assert r["except_completa_menos_recorte"] == 2
    md = informe_markdown(r, "A", "2026-07-01", [{"feature": "x", "causa": "mira el futuro", "correccion": "filtro < t"}])
    assert "| ratio_ult14_prev14 | 2 |" in md and "HAY DIFERENCIAS" in md and "| x | mira el futuro | filtro < t |" in md


def test_categorica_y_booleana_distintas():
    n = feats()
    n.loc[0, "modo_principal"] = "MR"
    n.loc[2, "tiene_padron_a_t"] = False
    r = comparar(feats(), n)
    assert r["por_columna"]["modo_principal"] == 1 and r["por_columna"]["tiene_padron_a_t"] == 1


def test_unidades_solo_en_un_lado():
    r = comparar(feats(), feats().iloc[:2])
    assert r["solo_completa"] == ["c"] and r["solo_recorte"] == [] and not r["sin_diferencias"]
    assert r["filas_comparadas"] == 2
