"""Registra en `ops.run_metrics` el tamaño de cada capa al final de una corrida del DAG.

Uso:
    RUN_ID=<run_id> python -m ingest.run_metrics [--estado 1] [--salida informe.md]
    RUN_ID=<run_id> python -m ingest.run_metrics --solo-estado 0     # tarea registrar_fallo

Para cada dataset de {bronze, staging, silver, quarantine, gold, features} y cada tabla:
- `filas`  = COUNT(*) (en Bronze, sobre las tablas externas Hive).
- `bytes`  = `__TABLES__.size_bytes` en tablas nativas; en Bronze, bytes de los objetos de GCS
             bajo `bronze/<fuente>/` (las tablas externas no ocupan almacenamiento en BigQuery).
             Nota: `region-us-central1.INFORMATION_SCHEMA.TABLE_STORAGE` exige permisos a nivel de
             proyecto (403 con ADC en la laptop); `__TABLES__` funciona con permisos de dataset.
Además, por capa: `filas_capa` y `bytes_capa` (sumas) y, con --estado, `estado` (1 = éxito, 0 = fallo).
Todas las filas llevan capa=<dataset>, fuente=<tabla> (o NULL en las agregadas), etapa=registrar_metricas.

Imprime una tabla Markdown por capa; `--salida` la guarda. Las funciones puras
(`construir_metricas`, `a_markdown`) se prueban sin red en tests/test_dag.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ingest import common  # noqa: E402
from ingest.conteos_capas import CAPAS, contar_filas, objetos_bronze, tablas_de  # noqa: E402

ETAPA = "registrar_metricas"
ETAPA_FALLO = "registrar_fallo"


# ---------------------------------------------------------------------------
# Funciones puras
# ---------------------------------------------------------------------------
def fila_metrica(run_id: str, etapa: str, metrica: str, valor: float, ts: str, *, capa: str | None = None,
                 fuente: str | None = None, detalle: str | None = None) -> dict:
    """Una fila con el esquema de ops.run_metrics (common.RUN_METRICS_SCHEMA)."""
    return {"run_id": run_id, "etapa": etapa, "capa": capa, "fuente": fuente, "metrica": metrica,
            "valor": float(valor), "ts": ts, "detalle": detalle}


def construir_metricas(run_id: str, conteos: dict[str, dict[str, dict]], ts: str, estado: int | None = None) -> list[dict]:
    """Convierte {capa: {tabla: {"filas": n, "bytes": b}}} en filas de ops.run_metrics.

    Por tabla: `filas` y `bytes`; por capa: `filas_capa` y `bytes_capa` (también para capas vacías,
    con 0, para que el tablero vea explícitamente que la capa no tiene datos). Con `estado`, una fila
    `estado` sin capa. Orden determinista: capas en el orden de CAPAS, tablas alfabéticas.
    """
    filas: list[dict] = []
    for capa in CAPAS:
        tablas = conteos.get(capa, {})
        total_filas = total_bytes = 0
        for tabla in sorted(tablas):
            n = tablas[tabla].get("filas")
            b = tablas[tabla].get("bytes")
            if n is not None:
                filas.append(fila_metrica(run_id, ETAPA, "filas", n, ts, capa=capa, fuente=tabla))
                total_filas += int(n)
            if b is not None:
                filas.append(fila_metrica(run_id, ETAPA, "bytes", b, ts, capa=capa, fuente=tabla))
                total_bytes += int(b)
        filas.append(fila_metrica(run_id, ETAPA, "filas_capa", total_filas, ts, capa=capa, detalle=f"tablas={len(tablas)}"))
        filas.append(fila_metrica(run_id, ETAPA, "bytes_capa", total_bytes, ts, capa=capa, detalle=f"tablas={len(tablas)}"))
    if estado is not None:
        filas.append(fila_metrica(run_id, ETAPA, "estado", estado, ts, detalle="success" if estado else "failed"))
    return filas


def _fmt(v) -> str:
    return "—" if v is None else f"{v:,}"


def a_markdown(run_id: str, conteos: dict[str, dict[str, dict]], ts: str) -> str:
    out = ["# Métricas de la corrida por capa", "", f"run_id `{run_id}` · {ts} · `ingest/run_metrics.py`", ""]
    for capa in CAPAS:
        tablas = conteos.get(capa, {})
        tf = sum(int(v.get("filas") or 0) for v in tablas.values())
        tb = sum(int(v.get("bytes") or 0) for v in tablas.values())
        out += [f"## {capa} — {len(tablas)} tablas, {tf:,} filas, {tb:,} bytes", ""]
        if not tablas:
            out += ["_(sin tablas)_", ""]
            continue
        out += ["| tabla | filas | bytes |", "|---|---:|---:|"]
        out += [f"| {t} | {_fmt(v.get('filas'))} | {_fmt(v.get('bytes'))} |" for t, v in sorted(tablas.items())]
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def bytes_tablas_nativas(bq, dataset: str) -> dict[str, int]:
    """size_bytes de las tablas nativas del dataset (`__TABLES__`; type 1 = tabla)."""
    consulta = f"SELECT table_id, size_bytes, type FROM `{common.PROJECT_ID}.{dataset}.__TABLES__`"
    try:
        return {r.table_id: int(r.size_bytes or 0) for r in bq.query(consulta).result() if r.type == 1}
    except Exception as exc:  # noqa: BLE001
        print(f"[run_metrics] __TABLES__ de {dataset}: {str(exc).splitlines()[0]}", file=sys.stderr)
        return {}


def recolectar_conteos(bq, gcs) -> dict[str, dict[str, dict]]:
    """{capa: {tabla: {"filas": n, "bytes": b}}} para las seis capas."""
    conteos: dict[str, dict[str, dict]] = {}
    bronze_gcs = objetos_bronze(gcs, common.LAKE_BUCKET)["por_fuente"]
    for capa in CAPAS:
        tablas = tablas_de(bq, capa)
        filas = contar_filas(bq, capa, tablas)
        if capa == common.BRONZE_DATASET:
            bytes_por_tabla = {t: bronze_gcs.get(t, {}).get("bytes", 0) for t in tablas}
        else:
            bytes_por_tabla = bytes_tablas_nativas(bq, capa)
        conteos[capa] = {t: {"filas": filas.get(t), "bytes": bytes_por_tabla.get(t)} for t in tablas}
    return conteos


def registrar_lote(bq, filas: list[dict]) -> None:
    """Un solo job de carga para todas las filas (WRITE_APPEND), en vez de un job por métrica."""
    if not filas:
        return
    from google.cloud import bigquery

    job = bq.load_table_from_json(
        filas, common.RUN_METRICS_TABLE,
        job_config=bigquery.LoadJobConfig(schema=common.RUN_METRICS_SCHEMA, write_disposition="WRITE_APPEND"),
    )
    job.result()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--estado", type=int, choices=(0, 1), help="registra además metrica='estado' con este valor")
    ap.add_argument("--solo-estado", type=int, choices=(0, 1), metavar="{0,1}",
                    help="solo registra metrica='estado' (etapa registrar_fallo si es 0) y termina")
    ap.add_argument("--salida", type=Path, help="guarda la tabla Markdown en este archivo")
    args = ap.parse_args(argv)

    bq = common.bq_client()
    common.asegurar_tablas_ops(bq)
    run_id = common.run_id_actual()
    ts = dt.datetime.now(dt.timezone.utc).isoformat()

    if args.solo_estado is not None:
        etapa = ETAPA if args.solo_estado else ETAPA_FALLO
        registrar_lote(bq, [fila_metrica(run_id, etapa, "estado", args.solo_estado, ts,
                                         detalle="success" if args.solo_estado else "failed")])
        print(f"[run_metrics] estado={args.solo_estado} registrado para run_id {run_id}")
        return 0

    conteos = recolectar_conteos(bq, common.gcs_client())
    filas = construir_metricas(run_id, conteos, ts, estado=args.estado)
    registrar_lote(bq, filas)
    md = a_markdown(run_id, conteos, ts)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(md, encoding="utf-8")
    print(md)
    print(f"[run_metrics] {len(filas)} filas registradas en {common.RUN_METRICS_TABLE} (run_id {run_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
