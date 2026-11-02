"""Carga del dataset de churn (BigQuery o CSV) con la guardia de la etiqueta del corte B.

La etiqueta de B se usa una sola vez (fase 2, `ml/evaluar_b.py`). Por eso pedir filas de B con etiqueta lanza
`AccesoProhibidoB`, salvo que se pase el token interno `TOKEN_B_INTERNO`. Para usos que no necesitan la etiqueta
(p. ej. el ensayo de invariancia) existe `sin_etiqueta=True`, que además nunca la lee de la fuente.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ml import config as cfg


class AccesoProhibidoB(RuntimeError):
    """Se intentó leer la etiqueta del corte B fuera de `ml/evaluar_b.py`."""


# Token privado del módulo: solo `ml/evaluar_b.py` (fase 2) debe importarlo.
TOKEN_B_INTERNO = object()

CORTES_VALIDOS = ("A", "B", "C")

DTYPES_CSV = {
    cfg.COLUMNA_ID: "string", cfg.COLUMNA_CORTE: "string",
    **{c: "float64" for c in cfg.FEATURES_NUM},
    "modo_principal": "string", "zona_principal": "string", "perfil_padron_a_t": "string",
    cfg.COLUMNA_ETIQUETA: "Int64", "run_id": "string",
}


def _validar_cortes(cortes) -> list[str]:
    cortes = list(cortes)
    malos = [c for c in cortes if c not in CORTES_VALIDOS]
    if not cortes or malos:
        raise ValueError(f"cortes inválidos {malos or cortes}; válidos: {CORTES_VALIDOS}")
    return cortes


def _consulta(cortes: list[str], con_etiqueta: bool) -> str:
    cols = "*" if con_etiqueta else f"* EXCEPT({cfg.COLUMNA_ETIQUETA})"
    return (f"SELECT {cols} FROM `{cfg.PROYECTO}.{cfg.TABLA_DATASET}` "
            f"WHERE {cfg.COLUMNA_CORTE} IN UNNEST(@cortes) ORDER BY {cfg.COLUMNA_CORTE}, {cfg.COLUMNA_ID}")


def _desde_bigquery(cortes: list[str], con_etiqueta: bool) -> pd.DataFrame:
    from google.cloud import bigquery  # import diferido: las pruebas con CSV no necesitan red ni credenciales

    cliente = bigquery.Client(project=cfg.PROYECTO)
    job = cliente.query(
        _consulta(cortes, con_etiqueta),
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ArrayQueryParameter("cortes", "STRING", cortes)]),
    )
    return job.result().to_dataframe(create_bqstorage_client=False)


def _desde_csv(ruta: Path) -> pd.DataFrame:
    cabecera = pd.read_csv(ruta, nrows=0).columns
    dtypes = {c: t for c, t in DTYPES_CSV.items() if c in cabecera}
    if "tiene_padron_a_t" in cabecera:
        dtypes["tiene_padron_a_t"] = "boolean"
    return pd.read_csv(ruta, dtype=dtypes, parse_dates=[c for c in ("fecha_corte", "fecha_referencia") if c in cabecera])


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Tipos estables sin importar la fuente; ordena por (corte, unidad_id) para que todo sea determinista."""
    df = df.copy()
    for c in cfg.FEATURES_NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    for c in cfg.FEATURES_CAT + [cfg.COLUMNA_ID, cfg.COLUMNA_CORTE]:
        df[c] = df[c].astype(object).where(df[c].notna(), np.nan)
    df["tiene_padron_a_t"] = df["tiene_padron_a_t"].fillna(False).astype(bool)
    if cfg.COLUMNA_ETIQUETA in df:
        df[cfg.COLUMNA_ETIQUETA] = pd.to_numeric(df[cfg.COLUMNA_ETIQUETA], errors="coerce").astype("float64")
    return df.sort_values([cfg.COLUMNA_CORTE, cfg.COLUMNA_ID]).reset_index(drop=True)


def cargar_dataset(cortes, origen: str = "bigquery", ruta_csv=None, _token_b=None,
                   sin_etiqueta: bool = False) -> pd.DataFrame:
    """Devuelve las filas de `features.churn_dataset` de los cortes pedidos.

    - `origen`: 'bigquery' o 'csv' (con `ruta_csv`).
    - Pedir el corte B con etiqueta lanza `AccesoProhibidoB` salvo `_token_b is TOKEN_B_INTERNO`.
    - `sin_etiqueta=True` devuelve los cortes sin la columna `etiqueta` (en BigQuery ni siquiera se consulta).
    """
    cortes = _validar_cortes(cortes)
    if "B" in cortes and not sin_etiqueta and _token_b is not TOKEN_B_INTERNO:
        raise AccesoProhibidoB(
            "La etiqueta del corte B se usa una sola vez (make ml-test-b). Para datos de B sin etiqueta usa "
            "sin_etiqueta=True.")
    if origen == "bigquery":
        df = _desde_bigquery(cortes, con_etiqueta=not sin_etiqueta)
    elif origen == "csv":
        if ruta_csv is None:
            raise ValueError("origen='csv' exige ruta_csv")
        df = _desde_csv(Path(ruta_csv))
        df = df[df[cfg.COLUMNA_CORTE].isin(cortes)]
    else:
        raise ValueError(f"origen inválido: {origen!r}")
    if sin_etiqueta and cfg.COLUMNA_ETIQUETA in df:
        df = df.drop(columns=[cfg.COLUMNA_ETIQUETA])
    return _normalizar(df)


def preparar_xy(df: pd.DataFrame):
    """(X, y, ids): X con FEATURES_NUM + FEATURES_CAT + FEATURES_BOOL en orden fijo, y entero 0/1, ids = unidad_id."""
    if cfg.COLUMNA_ETIQUETA not in df:
        raise ValueError("el DataFrame no trae etiqueta")
    if df[cfg.COLUMNA_ETIQUETA].isna().any():
        raise ValueError("hay etiquetas nulas (corte C no tiene etiqueta): no se puede entrenar ni evaluar")
    X = df[cfg.FEATURES].reset_index(drop=True)
    y = df[cfg.COLUMNA_ETIQUETA].astype(int).reset_index(drop=True)
    ids = df[cfg.COLUMNA_ID].reset_index(drop=True)
    return X, y, ids


def exportar(salida: Path | None = None) -> Path:
    """Exporta el dataset completo a CSV: A y C como vienen, B SIN etiqueta (no se toca antes de la fase 2)."""
    salida = Path(salida) if salida else cfg.CACHE / "churn_dataset.csv"
    ac = cargar_dataset(["A", "C"], "bigquery")
    b = cargar_dataset(["B"], "bigquery", sin_etiqueta=True)
    b[cfg.COLUMNA_ETIQUETA] = np.nan
    df = pd.concat([ac, b], ignore_index=True).sort_values([cfg.COLUMNA_CORTE, cfg.COLUMNA_ID])
    salida.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(salida, index=False)
    return salida


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("exportar", help="exporta el dataset de BigQuery a CSV sin la etiqueta de B")
    e.add_argument("--salida", default=None)
    args = p.parse_args(argv)
    if args.cmd == "exportar":
        print(exportar(args.salida))


if __name__ == "__main__":
    main()
