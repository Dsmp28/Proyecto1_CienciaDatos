"""Predicción del corte C (y ensayos) con un modelo ya guardado: nunca reentrena.

Pasos de `ejecutar`: (1) verifica el sha256 de los 9 archivos crudos contra el manifiesto de BigQuery o contra
`ingest/expected_hashes.json`; (2) valida que la fecha esté en `fechas_corte` de dbt; (3) carga las features del corte
(sin etiqueta); (4) puntúa con `persistencia.cargar_modelo`; (5) escribe `unidad_id,tarjetas,puntaje,contactar`.
La lógica es de funciones puras (probables sin red); el acceso a BigQuery está aislado en `_consultar`.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ml import config as cfg
from ml.persistencia import cargar_modelo

DBT_PROJECT = cfg.REPO / "dbt" / "dbt_project.yml"
HASHES_CSV = cfg.REPO / "ingest" / "expected_hashes.json"
PREDICCIONES = cfg.REPO / "predicciones"
COLUMNAS_SALIDA = ["unidad_id", "tarjetas", "puntaje", "contactar"]
ESTADOS_MANIFIESTO = ("completado", "publicado")
DECIMALES = 6
COD_OK, COD_ERROR, COD_HASH = 0, 1, 2


class ErrorUso(RuntimeError):
    """Entrada inválida (archivos faltantes, huellas distintas, fecha fuera de `fechas_corte`): código de salida 2."""


# ---------------------------------------------------------------------------
# Huellas de los archivos crudos
# ---------------------------------------------------------------------------
def nombres_catalogo() -> list[str]:
    from ingest.common import FUENTES

    return sorted(FUENTES)


def hashes_calculados(datos: Path, nombres: list[str] | None = None) -> dict[str, str]:
    """sha256 de cada archivo del catálogo en `datos`; todos deben existir."""
    from ingest.common import sha256_archivo

    datos = Path(datos)
    nombres = nombres or nombres_catalogo()
    faltan = [n for n in nombres if not (datos / n).is_file()]
    if faltan:
        raise ErrorUso(f"faltan archivos en {datos}: {', '.join(faltan)}")
    return {n: sha256_archivo(datos / n) for n in nombres}


def hashes_esperados_csv(ruta: Path = HASHES_CSV) -> dict[str, str]:
    archivos = json.loads(Path(ruta).read_text(encoding="utf-8"))["archivos"]
    return {n: v["sha256"] for n, v in archivos.items()}


def consulta_manifiesto() -> str:
    """Último sha256 por archivo entre las filas `completado`/`publicado` (un archivo puede ingerirse varias veces)."""
    from ingest.common import MANIFEST_TABLE

    return (f"SELECT archivo, ARRAY_AGG(sha256 ORDER BY ingest_ts DESC LIMIT 1)[OFFSET(0)] AS sha256 "
            f"FROM `{MANIFEST_TABLE}` WHERE estado IN UNNEST(@estados) AND archivo IN UNNEST(@archivos) "
            f"GROUP BY archivo")


def hashes_esperados_bigquery(cliente=None, nombres: list[str] | None = None) -> dict[str, str]:
    from google.cloud import bigquery

    if cliente is None:
        from ingest.common import bq_client

        cliente = bq_client()
    cfg_job = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ArrayQueryParameter("estados", "STRING", list(ESTADOS_MANIFIESTO)),
        bigquery.ArrayQueryParameter("archivos", "STRING", nombres or nombres_catalogo()),
    ])
    return {r["archivo"]: r["sha256"] for r in cliente.query(consulta_manifiesto(), job_config=cfg_job).result()}


def comparar_huellas(esperado: dict[str, str], calculado: dict[str, str]) -> list[dict]:
    """Archivos cuya huella calculada no coincide (o que no tienen huella esperada)."""
    return [{"archivo": n, "esperado": esperado.get(n), "calculado": h}
            for n, h in sorted(calculado.items()) if esperado.get(n) != h]


# ---------------------------------------------------------------------------
# Fecha de corte y carga de features
# ---------------------------------------------------------------------------
def fechas_corte_dbt(ruta: Path = DBT_PROJECT) -> list[str]:
    cfgd = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    return [str(f) for f in cfgd["vars"]["fechas_corte"]]


def validar_fecha_corte(fecha: str, validas: list[str] | None = None) -> str:
    fecha = str(fecha)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        raise ErrorUso(f"fecha de corte inválida: {fecha!r} (formato AAAA-MM-DD)")
    validas = validas if validas is not None else fechas_corte_dbt()
    if fecha not in validas:
        raise ErrorUso(f"la fecha {fecha} no está en fechas_corte de dbt_project.yml: {', '.join(validas)}")
    return fecha


def validar_sufijo(sufijo: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]*", sufijo or ""):
        raise ErrorUso(f"sufijo de dataset inválido: {sufijo!r}")
    return sufijo or ""


def consulta_features(sufijo: str = "", con_etiqueta: bool = False) -> str:
    sufijo = validar_sufijo(sufijo)
    cols = "d.*" if con_etiqueta else f"d.* EXCEPT ({cfg.COLUMNA_ETIQUETA})"
    return (f"SELECT {cols}, t.tarjetas FROM `{cfg.PROYECTO}.features{sufijo}.churn_dataset` AS d "
            f"JOIN `{cfg.PROYECTO}.silver{sufijo}.silver_unidad_tarjetas_corte` AS t "
            f"USING ({cfg.COLUMNA_ID}, {cfg.COLUMNA_FECHA}) WHERE d.{cfg.COLUMNA_FECHA} = @f")


def _consultar(sql: str, fecha: str) -> pd.DataFrame:
    """Único punto de acceso a BigQuery de la carga de features."""
    from google.cloud import bigquery

    cliente = bigquery.Client(project=cfg.PROYECTO)
    job = cliente.query(sql, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("f", "DATE", date.fromisoformat(fecha))]))
    return job.result().to_dataframe(create_bqstorage_client=False)


def ruta_features_csv(fecha: str) -> Path:
    return PREDICCIONES / f"features_corte_{fecha}.csv"


def leer_features_csv(ruta: Path) -> pd.DataFrame:
    cabecera = pd.read_csv(ruta, nrows=0).columns
    tipos = {c: "float64" for c in cfg.FEATURES_NUM if c in cabecera}
    tipos.update({c: "string" for c in (cfg.COLUMNA_ID, "tarjetas", *cfg.FEATURES_CAT) if c in cabecera})
    if "tiene_padron_a_t" in cabecera:
        tipos["tiene_padron_a_t"] = "boolean"
    return pd.read_csv(ruta, dtype=tipos)


def normalizar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Mismos tipos que `ml.datos._normalizar` (el modelo se entrenó con ellos), sin exigir `corte`."""
    df = df.copy()
    for c in cfg.FEATURES_NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    for c in cfg.FEATURES_CAT + [cfg.COLUMNA_ID]:
        df[c] = df[c].astype(object).where(df[c].notna(), np.nan)
    df["tiene_padron_a_t"] = df["tiene_padron_a_t"].fillna(False).astype(bool)
    return df.sort_values(cfg.COLUMNA_ID).reset_index(drop=True)


def cargar_features(fecha: str, origen: str = "bigquery", sufijo: str = "", features_csv: Path | None = None) -> pd.DataFrame:
    if origen == "bigquery":
        df = _consultar(consulta_features(sufijo), fecha)
    elif origen == "csv":
        df = leer_features_csv(Path(features_csv) if features_csv else ruta_features_csv(fecha))
        if cfg.COLUMNA_FECHA in df:
            df = df[pd.to_datetime(df[cfg.COLUMNA_FECHA]).dt.strftime("%Y-%m-%d") == fecha]
    else:
        raise ErrorUso(f"origen inválido: {origen!r}")
    if cfg.COLUMNA_ETIQUETA in df:
        df = df.drop(columns=[cfg.COLUMNA_ETIQUETA])
    faltan = [c for c in ("tarjetas", cfg.COLUMNA_ID, *cfg.FEATURES) if c not in df]
    if faltan:
        raise ErrorUso(f"faltan columnas en las features: {faltan}")
    return normalizar_features(df)


# ---------------------------------------------------------------------------
# Puntuación y salida
# ---------------------------------------------------------------------------
def predecir(pipeline, meta: dict, df: pd.DataFrame, umbral: float | None = None) -> pd.DataFrame:
    """DataFrame `unidad_id,tarjetas,puntaje,contactar` ordenado por unidad_id. Umbral: argumento o metadatos."""
    umbral = umbral if umbral is not None else meta.get("umbral")
    if umbral is None:
        raise ErrorUso("el modelo no trae umbral en sus metadatos; pásalo con --umbral")
    columnas = meta.get("features") or cfg.FEATURES
    faltan = [c for c in columnas if c not in df]
    if faltan:
        raise ErrorUso(f"faltan features del modelo: {faltan}")
    if df[cfg.COLUMNA_ID].duplicated().any():
        raise ErrorUso("hay unidad_id repetidos: se espera una fila por unidad")
    df = df.sort_values(cfg.COLUMNA_ID).reset_index(drop=True)
    puntaje = np.round(pipeline.predict_proba(df[list(columnas)])[:, 1], DECIMALES)
    return pd.DataFrame({
        "unidad_id": df[cfg.COLUMNA_ID].astype(str),
        "tarjetas": df["tarjetas"].astype("string"),
        "puntaje": puntaje,
        "contactar": (puntaje >= float(umbral)).astype("int64"),
    })[COLUMNAS_SALIDA]


def escribir_salida(pred: pd.DataFrame, ruta: Path) -> Path:
    """UTF-8 sin BOM, '\\n', puntaje con 6 decimales fijos (texto estable entre corridas)."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    pred[COLUMNAS_SALIDA].sort_values("unidad_id").to_csv(
        ruta, index=False, lineterminator="\n", encoding="utf-8", float_format=f"%.{DECIMALES}f")
    return ruta


def verificar_huellas(datos: Path, origen: str, hashes_esperados: dict[str, str] | None = None,
                      cliente=None) -> list[dict]:
    calculado = hashes_calculados(datos)
    if hashes_esperados is None:
        hashes_esperados = hashes_esperados_bigquery(cliente) if origen == "bigquery" else hashes_esperados_csv()
    return comparar_huellas(hashes_esperados, calculado)


def ejecutar(datos, fecha_corte: str, origen: str = "bigquery", salida=None, modelo: str | None = "ACTUAL",
             sin_verificar: bool = False, sufijo: str = "", umbral: float | None = None,
             features_csv=None, hashes_esperados: dict[str, str] | None = None, directorio_modelos=None,
             fechas_validas: list[str] | None = None, cliente=None, out=print) -> int:
    """Flujo completo. Devuelve el código de salida: 0 ok, 2 huellas distintas / entrada inválida."""
    inicio = time.time()
    try:
        diferencias = verificar_huellas(Path(datos), origen, hashes_esperados, cliente)
        if diferencias:
            for d in diferencias:
                out(f"  DIFIERE {d['archivo']}: esperado={d['esperado']} calculado={d['calculado']}")
            if not sin_verificar:
                out(f"ERROR: {len(diferencias)} archivo(s) no coinciden con las huellas oficiales "
                    f"({'ops.ingest_manifest' if origen == 'bigquery' else 'ingest/expected_hashes.json'}).")
                return COD_HASH
            out("AVISO: huellas distintas; se continúa por --sin-verificar.")
        else:
            out("Huellas verificadas: los 9 archivos coinciden.")
        fecha = validar_fecha_corte(fecha_corte, fechas_validas)
        salida = Path(salida) if salida else PREDICCIONES / f"predicciones_corte_{fecha}.csv"
        df = cargar_features(fecha, origen, sufijo, features_csv)
    except ErrorUso as e:
        out(f"ERROR: {e}")
        return COD_HASH
    if modelo in (None, "ACTUAL"):
        pipeline, meta = cargar_modelo(directorio=directorio_modelos)
    else:
        pipeline, meta = cargar_modelo(Path(modelo))
    try:
        pred = predecir(pipeline, meta, df, umbral)
    except ErrorUso as e:
        out(f"ERROR: {e}")
        return COD_HASH
    escribir_salida(pred, salida)
    out(f"Predicciones: {len(pred)} filas, {int(pred['contactar'].sum())} a contactar "
        f"(umbral {umbral if umbral is not None else meta.get('umbral')}), "
        f"{time.time() - inicio:.1f} s -> {salida}")
    return COD_OK
