"""Prueba de recorte: las features de un corte no deben cambiar si se recortan los datos a < t.

Compara `features.churn_features` (todos los datos) contra `features_recorte.churn_features` (dbt con
`--target recorte` y `recorte_datos_hasta` = día anterior al corte) para un corte: unidades solo en uno u otro,
`EXCEPT DISTINCT` en ambos sentidos y, por columna, el número de filas distintas (floats con tolerancia 1e-6; nulos
iguales). Si alguna feature mira el futuro, difiere. Exit 1 si hay diferencias.
Uso: `python -m ml.prueba_recorte --corte A --fecha-corte 2026-07-01 --informe docs/evidence/p2/prueba_recorte.md`.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from ml import config as cfg

TOLERANCIA = 1e-6
CLAVE = cfg.COLUMNA_ID
# Columnas que por diseño no son features: la letra de corte depende de la posición en fechas_corte, y el linaje cambia.
IGNORAR = {"corte", "run_id", "fecha_referencia"}
TABLA_POR_DEFECTO = "churn_features"
TABLA_COMPLETA = f"{cfg.PROYECTO}.features.{TABLA_POR_DEFECTO}"
TABLA_RECORTE = f"{cfg.PROYECTO}.features_recorte.{TABLA_POR_DEFECTO}"


def tablas_de(tabla: str) -> tuple[str, str]:
    """Nombres completos de la tabla en `features` (datos completos) y en `features_recorte` (datos recortados)."""
    return f"{cfg.PROYECTO}.features.{tabla}", f"{cfg.PROYECTO}.features_recorte.{tabla}"


def fallos_desde_resultado(res: dict) -> list[dict]:
    """Una entrada por feature con filas distintas; causa y corrección se completan a mano."""
    return [{"feature": c, "filas_distintas": n, "causa": "", "correccion": ""}
            for c, n in res["por_columna"].items() if n]


def _distinto_col(a: pd.Series, b: pd.Series, tolerancia: float) -> pd.Series:
    """True donde difieren; nulos iguales entre sí; floats con tolerancia absoluta."""
    nulos_a, nulos_b = a.isna(), b.isna()
    if pd.api.types.is_float_dtype(a) or pd.api.types.is_float_dtype(b) or (
            pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b) and not pd.api.types.is_bool_dtype(a)):
        x, y = pd.to_numeric(a, errors="coerce").astype(float), pd.to_numeric(b, errors="coerce").astype(float)
        igual = np.isclose(x, y, rtol=0, atol=tolerancia, equal_nan=False)
    else:
        igual = (a.astype(object) == b.astype(object)).fillna(False).to_numpy(dtype=bool)
    return pd.Series(~(igual | (nulos_a & nulos_b).to_numpy()), index=a.index)


def _filas_unicas(df: pd.DataFrame, columnas: list[str]) -> set[tuple]:
    """Filas como tuplas con floats redondeados a 6 decimales y nulos normalizados (para EXCEPT DISTINCT)."""
    sub = df[columnas].copy()
    for c in columnas:
        if pd.api.types.is_float_dtype(sub[c]):
            sub[c] = sub[c].round(6)
    sub = sub.astype(object).where(sub.notna(), None)
    return set(map(tuple, sub.itertuples(index=False, name=None)))


def comparar(completa: pd.DataFrame, recorte: pd.DataFrame, tolerancia: float = TOLERANCIA) -> dict:
    """Comparación pura de dos DataFrames de features del mismo corte (clave `unidad_id`)."""
    columnas = [c for c in completa.columns if c in recorte.columns and c != CLAVE and c not in IGNORAR]
    solo_completa = sorted(set(completa[CLAVE]) - set(recorte[CLAVE]))
    solo_recorte = sorted(set(recorte[CLAVE]) - set(completa[CLAVE]))
    m = completa.merge(recorte, on=CLAVE, suffixes=("__c", "__r"))
    por_columna = {c: int(_distinto_col(m[f"{c}__c"], m[f"{c}__r"], tolerancia).sum()) for c in columnas}
    comunes = [CLAVE] + columnas
    sc, sr = _filas_unicas(completa, comunes), _filas_unicas(recorte, comunes)
    except_c_r, except_r_c = len(sc - sr), len(sr - sc)
    total = (len(solo_completa) + len(solo_recorte) + sum(por_columna.values()))
    return {
        "filas_completa": len(completa), "filas_recorte": len(recorte), "filas_comparadas": len(m),
        "solo_completa": solo_completa, "solo_recorte": solo_recorte,
        "except_completa_menos_recorte": except_c_r, "except_recorte_menos_completa": except_r_c,
        "por_columna": por_columna, "columnas_comparadas": columnas,
        "columnas_solo_completa": sorted(set(completa.columns) - set(recorte.columns) - IGNORAR),
        "columnas_solo_recorte": sorted(set(recorte.columns) - set(completa.columns) - IGNORAR),
        "diferencias_totales": total, "sin_diferencias": total == 0 and except_c_r == 0 and except_r_c == 0,
    }


def informe_markdown(res: dict, corte: str, fecha: str, fallos_previos: list[dict] | None = None,
                     tabla: str = TABLA_POR_DEFECTO, etiqueta: str | None = None) -> str:
    L = [f"# Prueba de recorte{f' ({etiqueta})' if etiqueta else ''}", "",
         f"Corte {corte} ({fecha}). `features.{tabla}` (datos completos) vs `features_recorte.{tabla}` "
         f"(datos recortados a < t). Floats con tolerancia {TOLERANCIA}; nulos iguales.", "",
         f"- Filas en completa: {res['filas_completa']}; en recorte: {res['filas_recorte']}; "
         f"comparadas (mismas unidades): {res['filas_comparadas']}",
         f"- Unidades solo en completa: {len(res['solo_completa'])}; solo en recorte: {len(res['solo_recorte'])}",
         f"- `EXCEPT DISTINCT` completa - recorte: {res['except_completa_menos_recorte']} filas; "
         f"recorte - completa: {res['except_recorte_menos_completa']} filas",
         f"- Diferencias totales (celdas + unidades): {res['diferencias_totales']}", ""]
    if res["columnas_solo_completa"] or res["columnas_solo_recorte"]:
        L += [f"- Columnas solo en completa: {res['columnas_solo_completa']}; solo en recorte: "
              f"{res['columnas_solo_recorte']}", ""]
    L += ["## Filas distintas por feature", "", "| Feature | Filas distintas |", "|---|---|"]
    L += [f"| {c} | {n} |" for c, n in res["por_columna"].items()]
    L += ["", f"**Resultado: {'SIN DIFERENCIAS' if res['sin_diferencias'] else 'HAY DIFERENCIAS'}**", "",
          "## Features que fallaron antes de corregir", ""]
    if fallos_previos:
        L += ["| Feature | Causa | Corrección |", "|---|---|---|"]
        L += [f"| {f.get('feature', '')} | {f.get('causa', '')} | {f.get('correccion', '')} |" for f in fallos_previos]
    else:
        L += ["_Sin registro (falta `--fallos-previos` o está vacío)._"]
    return "\n".join(L) + "\n"


def leer_fallos(ruta: Path | None) -> list[dict]:
    if not ruta or not Path(ruta).exists():
        return []
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def _consultar_features(tabla: str, fecha: str, corte: str | None) -> pd.DataFrame:
    """Único acceso a BigQuery: features de un corte (por fecha_corte; y por letra de corte si se indica)."""
    from google.cloud import bigquery

    filtro = "fecha_corte = @f" + (" AND corte = @c" if corte else "")
    params = [bigquery.ScalarQueryParameter("f", "DATE", date.fromisoformat(fecha))]
    if corte:
        params.append(bigquery.ScalarQueryParameter("c", "STRING", corte))
    cliente = bigquery.Client(project=cfg.PROYECTO)
    job = cliente.query(f"SELECT * FROM `{tabla}` WHERE {filtro}",
                        job_config=bigquery.QueryJobConfig(query_parameters=params))
    return job.result().to_dataframe(create_bqstorage_client=False)


def cargar_desde_bigquery(corte: str, fecha: str, tabla: str = TABLA_POR_DEFECTO) -> tuple[pd.DataFrame, pd.DataFrame]:
    # En el dataset recortado hay una sola fecha de corte, así que su letra siempre es 'A': se filtra por fecha.
    completa, recortada = tablas_de(tabla)
    return _consultar_features(completa, fecha, corte), _consultar_features(recortada, fecha, None)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corte", required=True, choices=["A", "B", "C"])
    p.add_argument("--fecha-corte", required=True)
    p.add_argument("--informe", default=None)
    p.add_argument("--tabla", default=TABLA_POR_DEFECTO, help="tabla a comparar en features y features_recorte")
    p.add_argument("--etiqueta-informe", default=None, help="texto entre paréntesis en el título del informe")
    p.add_argument("--salida-fallos", default=None,
                   help="JSON con {feature, filas_distintas, causa, correccion} de las features con diferencias")
    p.add_argument("--origen", choices=["bigquery"], default="bigquery")
    p.add_argument("--fallos-previos", default=str(cfg.EVIDENCIA / "prueba_recorte_fallos.json"))
    a = p.parse_args(argv)
    completa, recorte = cargar_desde_bigquery(a.corte, a.fecha_corte, a.tabla)
    res = comparar(completa, recorte)
    print(f"Filas comparadas: {res['filas_comparadas']} (completa {res['filas_completa']}, recorte "
          f"{res['filas_recorte']}); diferencias totales: {res['diferencias_totales']}")
    for c, n in res["por_columna"].items():
        if n:
            print(f"  {c}: {n} filas distintas")
    if a.informe:
        ruta = Path(a.informe)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(informe_markdown(res, a.corte, a.fecha_corte, leer_fallos(Path(a.fallos_previos)),
                                         a.tabla, a.etiqueta_informe), encoding="utf-8")
        print(f"Informe: {ruta}")
    if a.salida_fallos:
        ruta_f = Path(a.salida_fallos)
        ruta_f.parent.mkdir(parents=True, exist_ok=True)
        ruta_f.write_text(json.dumps(fallos_desde_resultado(res), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Fallos: {ruta_f}")
    return 0 if res["sin_diferencias"] else 1


if __name__ == "__main__":
    sys.exit(main())
