"""Pruebas de ml.invariancia (sin red)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.invariancia import ejecutar  # noqa: E402


def base() -> pd.DataFrame:
    return pd.DataFrame({"unidad_id": ["a", "b", "c", "d"], "tarjetas": ["T1", "T2;U2", "T3", "T4"],
                         "puntaje": [0.123456, 0.5, 0.9, 0.01], "contactar": [0, 1, 1, 0]})


def escribir(df, ruta):
    df.to_csv(ruta, index=False, lineterminator="\n")
    return ruta


@pytest.fixture
def ref(tmp_path):
    return escribir(base(), tmp_path / "ref.csv")


def correr(ref, nueva_df, tmp_path):
    return ejecutar(ref, escribir(nueva_df, tmp_path / "nueva.csv"), out=lambda *_: None)


def test_identicas(ref, tmp_path):
    assert correr(ref, base(), tmp_path) == 0


def test_septima_cifra_tolerada(ref, tmp_path):
    n = base()
    n.loc[0, "puntaje"] = 0.1234564
    assert correr(ref, n, tmp_path) == 0


def test_quinta_cifra_difiere(ref, tmp_path):
    n = base()
    n.loc[0, "puntaje"] = 0.123406
    assert correr(ref, n, tmp_path) == 1


def test_unidad_faltante_o_sobrante(ref, tmp_path):
    assert correr(ref, base().iloc[:3], tmp_path) == 1
    extra = pd.concat([base(), pd.DataFrame({"unidad_id": ["z"], "tarjetas": ["T9"], "puntaje": [0.3], "contactar": [0]})])
    assert correr(ref, extra, tmp_path) == 1


def test_tarjetas_o_contactar_distintos(ref, tmp_path):
    n = base()
    n.loc[1, "tarjetas"] = "T2;U9"
    assert correr(ref, n, tmp_path) == 1
    m = base()
    m.loc[2, "contactar"] = 0
    assert correr(ref, m, tmp_path) == 1


def test_ilegible_codigo_2_e_informe(ref, tmp_path):
    assert ejecutar(ref, tmp_path / "no_existe.csv", out=lambda *_: None) == 2
    malo = tmp_path / "malo.csv"
    malo.write_text("x,y\n1,2\n")
    assert ejecutar(ref, malo, out=lambda *_: None) == 2
    n = base()
    n.loc[0, "puntaje"] = 0.2
    informe = tmp_path / "docs" / "inv.md"
    assert ejecutar(ref, escribir(n, tmp_path / "n.csv"), informe, out=lambda *_: None) == 1
    texto = informe.read_text()
    assert "DIFIEREN" in texto and "| puntaje | 1 |" in texto
