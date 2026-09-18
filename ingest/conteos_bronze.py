"""Concilia Bronze con el manifiesto: filas por fuente en las tablas externas vs. filas_origen.

Uso:
    python ingest/conteos_bronze.py [--salida docs/evidence/conteos_bronze.md]

Para cada fuente del catálogo:
- filas_origen: última fila 'completado'/'publicado' del archivo en `ops.ingest_manifest`.
- filas_bronze: COUNT(*) de la tabla externa `bronze.<fuente>`. En streaming se calcula además
  COUNT(DISTINCT (archivo, linea_num)) para detectar duplicados de entrega (at-least-once).
- Las fuentes streaming solo se comparan si el manifiesto tiene filas para ellas; si sus
  prefijos están vacíos, la fila queda como "sin ingesta" y no cuenta como diferencia.

Escribe la tabla Markdown en docs/evidence/conteos_bronze.md, la imprime y registra la métrica
`filas` (etapa conteos_bronze, capa bronze) por fuente. Termina con código 1 si alguna
diferencia es distinta de cero.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ingest import common  # noqa: E402

SALIDA_DEFECTO = REPO / "docs" / "evidence" / "conteos_bronze.md"


# ---------------------------------------------------------------------------
# Funciones puras
# ---------------------------------------------------------------------------
def conciliar(fuente: common.Fuente, filas_origen: int | None, filas_bronze: int | None,
              filas_distintas: int | None = None, error: str | None = None) -> dict:
    """Arma la fila de conciliación de una fuente y decide si está ok."""
    fila = {
        "archivo": fuente.archivo, "fuente": fuente.fuente, "via": fuente.via,
        "filas_origen": filas_origen, "filas_bronze": filas_bronze,
        "filas_distintas": filas_distintas, "diferencia": None, "ok": True, "nota": "",
    }
    if filas_origen is None:
        # Sin ingesta registrada: en streaming es lo esperado antes de la primera corrida de Kafka.
        fila["nota"] = "sin ingesta en el manifiesto"
        fila["ok"] = fuente.via == "streaming" or filas_bronze in (None, 0)
        if error:
            fila["nota"] += f"; {error}"
        return fila
    if filas_bronze is None:
        fila["ok"] = False
        fila["nota"] = error or "sin conteo en Bronze"
        return fila
    fila["diferencia"] = filas_bronze - filas_origen
    fila["ok"] = fila["diferencia"] == 0
    if filas_distintas is not None and filas_distintas != filas_bronze:
        fila["ok"] = False
        fila["nota"] = f"{filas_bronze - filas_distintas} duplicado(s) de entrega"
    return fila


def a_markdown(filas: list[dict], run_id: str, ts: str) -> str:
    out = [
        "# Conteos de Bronze vs. manifiesto",
        "",
        f"Generado por `ingest/conteos_bronze.py` · run_id `{run_id}` · {ts}",
        "",
        "| archivo | vía | filas_origen | filas_bronze | diferencia | ok |",
        "|---|---|---:|---:|---:|:---:|",
    ]
    for f in filas:
        v = lambda x: "-" if x is None else f"{x:,}"  # noqa: E731
        ok = "sí" if f["ok"] else "NO"
        nota = f" ({f['nota']})" if f["nota"] else ""
        out.append(f"| {f['archivo']} | {f['via']} | {v(f['filas_origen'])} | {v(f['filas_bronze'])} | "
                   f"{v(f['diferencia'])} | {ok}{nota} |")
    total_dif = sum(abs(f["diferencia"]) for f in filas if f["diferencia"] is not None)
    out += ["", f"Diferencia total: {total_dif}. Resultado: {'OK' if all(f['ok'] for f in filas) else 'HAY DIFERENCIAS'}.", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def filas_origen_manifiesto(bq) -> dict[str, int]:
    """Última fila completado/publicado por archivo → filas_origen."""
    consulta = f"""
        SELECT archivo, filas_origen
        FROM (
          SELECT archivo, filas_origen,
                 ROW_NUMBER() OVER (PARTITION BY archivo ORDER BY ingest_ts DESC) AS rn
          FROM `{common.MANIFEST_TABLE}`
          WHERE estado IN ('completado', 'publicado')
        )
        WHERE rn = 1
    """
    return {r.archivo: int(r.filas_origen) for r in bq.query(consulta).result()}


def contar_bronze(bq, fuente: common.Fuente) -> tuple[int | None, int | None, str | None]:
    tabla = f"{common.PROJECT_ID}.{common.BRONZE_DATASET}.{fuente.fuente}"
    if fuente.via == "streaming":
        consulta = f"SELECT COUNT(*) AS n, COUNT(DISTINCT CONCAT(archivo, ':', CAST(linea_num AS STRING))) AS d FROM `{tabla}`"
    else:
        consulta = f"SELECT COUNT(*) AS n, NULL AS d FROM `{tabla}`"
    try:
        r = next(iter(bq.query(consulta).result()))
        return int(r.n), (int(r.d) if r.d is not None else None), None
    except Exception as exc:  # noqa: BLE001 — se informa en la tabla
        return None, None, str(exc).splitlines()[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", type=Path, default=SALIDA_DEFECTO)
    args = ap.parse_args(argv)

    bq = common.bq_client()
    common.asegurar_tablas_ops(bq)
    run_id = common.run_id_actual()
    origen = filas_origen_manifiesto(bq)

    filas = []
    for fuente in common.FUENTES.values():
        fo = origen.get(fuente.archivo)
        if fuente.via == "streaming" and fo is None:
            fila = conciliar(fuente, None, None)
        else:
            n, d, err = contar_bronze(bq, fuente)
            fila = conciliar(fuente, fo, n, d, err)
            if n is not None:
                common.registrar_metrica(bq, "conteos_bronze", "filas", n, capa="bronze", fuente=fuente.fuente,
                                         detalle=f"filas_origen={fo}", run_id=run_id)
        filas.append(fila)

    md = a_markdown(filas, run_id, dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(md, encoding="utf-8")
    print(md)
    print(f"[conteos] escrito {args.salida}")
    return 0 if all(f["ok"] for f in filas) else 1


if __name__ == "__main__":
    sys.exit(main())
