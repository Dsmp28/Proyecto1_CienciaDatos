"""Crea (o reemplaza) las tablas externas de Bronze en BigQuery a partir de la plantilla SQL.

Uso:
    python ingest/bronze_external_tables.py [--verificar] [--solo-imprimir]

- Lee `ingest/sql/bronze_external_tables.sql`, sustituye {project} y {bucket} y ejecuta cada
  sentencia por separado (una tabla externa por fuente, dataset `bronze`). Es idempotente:
  el DDL es CREATE OR REPLACE EXTERNAL TABLE.
- Prefijo vacío: BigQuery rechaza crear una tabla externa Hive sin objetos bajo el prefijo
  ("Cannot query hive partitioned data ... without any associated files"). Ocurre con las dos
  fuentes streaming antes de la primera corrida de Kafka. Esas tablas quedan en estado
  "pendiente", se informa y el script termina con 0 (con `--estricto` termina con 1); basta
  reejecutarlo cuando existan objetos.
- `--verificar`: tras el DDL, SELECT COUNT(*) de cada tabla creada y lo imprime.
- `--solo-imprimir`: muestra el SQL renderizado sin ejecutar nada.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ingest import common  # noqa: E402

PLANTILLA = REPO / "ingest" / "sql" / "bronze_external_tables.sql"
MARCA_PREFIJO_VACIO = "without any associated files"


# ---------------------------------------------------------------------------
# Funciones puras (probadas en tests/test_ingest_batch.py)
# ---------------------------------------------------------------------------
def renderizar(plantilla: str, project: str, bucket: str) -> str:
    """Sustituye {project} y {bucket}; falla si queda alguna llave de plantilla sin resolver."""
    sql = plantilla.replace("{project}", project).replace("{bucket}", bucket)
    if "{project}" in sql or "{bucket}" in sql:
        raise ValueError("La plantilla conserva marcadores sin sustituir")
    return sql


def dividir_sentencias(sql: str) -> list[str]:
    """Separa el SQL en sentencias por ';' al final de línea, sin comentarios sueltos ni vacíos."""
    sentencias = []
    for bloque in sql.split(";\n"):
        lineas = [l for l in bloque.splitlines() if l.strip() and not l.strip().startswith("--")]
        if lineas:
            sentencias.append("\n".join(lineas) + ";")
    return sentencias


def nombre_tabla(sentencia: str) -> str:
    """Extrae `proyecto.dataset.tabla` de una sentencia CREATE ... EXTERNAL TABLE `...`."""
    ini = sentencia.index("`") + 1
    return sentencia[ini:sentencia.index("`", ini)]


def sql_renderizado(project: str | None = None, bucket: str | None = None) -> str:
    return renderizar(PLANTILLA.read_text(encoding="utf-8"), project or common.PROJECT_ID, bucket or common.LAKE_BUCKET)


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------
def ejecutar_ddl(bq, sentencias: list[str]) -> list[dict]:
    resultados = []
    for s in sentencias:
        tabla = nombre_tabla(s)
        try:
            bq.query(s).result()
            resultados.append({"tabla": tabla, "ok": True, "detalle": "creada/reemplazada"})
            print(f"[ddl] OK  {tabla}")
        except Exception as exc:  # noqa: BLE001 — se informa y se sigue con la siguiente tabla
            msg = str(exc).splitlines()[0]
            if MARCA_PREFIJO_VACIO in msg:
                # Prefijo sin objetos (streaming antes de Kafka): no es un error del DDL, se reintenta después.
                resultados.append({"tabla": tabla, "ok": False, "pendiente": True,
                                   "detalle": "prefijo vacío en GCS; reejecutar cuando existan objetos"})
                print(f"[ddl] PENDIENTE {tabla}: prefijo vacío en GCS (BigQuery no crea tablas Hive sin archivos)")
            else:
                resultados.append({"tabla": tabla, "ok": False, "pendiente": False, "detalle": msg})
                print(f"[ddl] ERROR {tabla}: {msg}")
    return resultados


def verificar_conteos(bq, tablas: list[str]) -> list[dict]:
    conteos = []
    for t in tablas:
        try:
            n = next(iter(bq.query(f"SELECT COUNT(*) AS n FROM `{t}`").result())).n
            conteos.append({"tabla": t, "filas": n, "detalle": ""})
            print(f"[verificar] {t}: {n} filas")
        except Exception as exc:  # noqa: BLE001 — un prefijo vacío no debe tumbar la verificación
            msg = str(exc).splitlines()[0]
            conteos.append({"tabla": t, "filas": None, "detalle": msg})
            print(f"[verificar] {t}: sin conteo ({msg})")
    return conteos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verificar", action="store_true", help="SELECT COUNT(*) de cada tabla tras el DDL")
    ap.add_argument("--solo-imprimir", action="store_true", help="imprime el SQL renderizado y termina")
    ap.add_argument("--estricto", action="store_true", help="falla también si una tabla queda pendiente por prefijo vacío")
    args = ap.parse_args(argv)

    sql = sql_renderizado()
    sentencias = dividir_sentencias(sql)
    if args.solo_imprimir:
        print(sql)
        return 0

    bq = common.bq_client()
    print(f"[ddl] proyecto={common.PROJECT_ID} bucket={common.LAKE_BUCKET} sentencias={len(sentencias)}")
    resultados = ejecutar_ddl(bq, sentencias)
    fallidas = [r for r in resultados if not r["ok"] and not r.get("pendiente")]
    pendientes = [r for r in resultados if r.get("pendiente")]

    if args.verificar:
        verificar_conteos(bq, [r["tabla"] for r in resultados if r["ok"]])

    ok = [r for r in resultados if r["ok"]]
    print(f"[ddl] creadas={len(ok)} pendientes={len(pendientes)} errores={len(fallidas)}")
    for r in pendientes:
        print(f"  - pendiente {r['tabla']}: {r['detalle']}")
    for r in fallidas:
        print(f"  - error {r['tabla']}: {r['detalle']}")
    if fallidas or (pendientes and args.estricto):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
