"""Evidencia de la carga desde cero (Proyecto 2) para un run_id.

Uso:
    python ingest/evidencia_p2.py --run-id <id> [--salida-dir docs/evidence/p2]
                                  [--inicio ISO --fin ISO | --dag-run-json dagrun.json]
                                  [--esperados ingest/expected_hashes.json]

Genera en --salida-dir:
- conteos_bronze.md: filas esperadas (LEEME de la cátedra, expected_hashes.json) vs. COUNT(*) de
  `bronze.<fuente>`; en streaming se reporta además COUNT(DISTINCT archivo||':'||linea_num).
- tiempos.md: última `duracion_s` en success por etapa (ops.run_metrics) para el run_id.
- conteos_capas.md: instantánea de conteos por capa (ingest.conteos_capas).
Termina con código 1 si alguna diferencia de Bronze es distinta de cero (los archivos se escriben igual).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ingest import common, conteos_capas  # noqa: E402

ESPERADOS_DEFECTO = REPO / "ingest" / "expected_hashes.json"
SALIDA_DEFECTO = REPO / "docs" / "evidence" / "p2"


# ---------------------------------------------------------------------------
# Funciones puras
# ---------------------------------------------------------------------------
def fmt_n(v) -> str:
    """Separador de miles con coma, igual que ingest/conteos_bronze.py."""
    return "-" if v is None else f"{v:,}"


def cargar_esperados(path: Path) -> dict[str, int]:
    with Path(path).open(encoding="utf-8") as f:
        return {n: int(d["filas_datos"]) for n, d in json.load(f)["archivos"].items()}


def fila_conteo(fuente: common.Fuente, esperadas: int | None, cargadas: int | None,
                distintas: int | None = None, error: str | None = None) -> dict:
    dif = None if esperadas is None or cargadas is None else cargadas - esperadas
    ok = dif == 0 and (distintas is None or distintas == cargadas)
    nota = error or ""
    if dif == 0 and distintas is not None and distintas != cargadas:
        nota = f"{cargadas - distintas} duplicado(s) de entrega"
    return {"archivo": fuente.archivo, "via": fuente.via, "esperadas": esperadas, "cargadas": cargadas,
            "distintas": distintas, "diferencia": dif, "ok": ok, "nota": nota}


def conteos_a_markdown(filas: list[dict], run_id: str, ts: str) -> str:
    out = ["# Conteos de Bronze vs. LEEME de la cátedra", "",
           f"Generado por `ingest/evidencia_p2.py` · run_id `{run_id}` · {ts}", "",
           "| archivo | vía | filas esperadas (LEEME) | filas cargadas (Bronze) | diferencia | ok |",
           "|---|---|---:|---:|---:|:---:|"]
    for f in filas:
        cargadas = fmt_n(f["cargadas"])
        if f["distintas"] is not None:
            cargadas += f" (distintas: {fmt_n(f['distintas'])})"
        nota = f" ({f['nota']})" if f["nota"] else ""
        out.append(f"| {f['archivo']} | {f['via']} | {fmt_n(f['esperadas'])} | {cargadas} | "
                   f"{fmt_n(f['diferencia'])} | {'sí' if f['ok'] else 'NO'}{nota} |")
    te = sum(f["esperadas"] or 0 for f in filas)
    tc = sum(f["cargadas"] or 0 for f in filas)
    todo_ok = all(f["ok"] for f in filas)
    out.append(f"| **Total** | | **{fmt_n(te)}** | **{fmt_n(tc)}** | **{fmt_n(tc - te)}** | {'sí' if todo_ok else 'NO'} |")
    out += ["", f"Resultado: {'OK' if todo_ok else 'HAY DIFERENCIAS'}.", ""]
    return "\n".join(out)


def ultimas_duraciones(filas: list[dict]) -> list[tuple[str, float]]:
    """Última `duracion_s` con detalle success por etapa, ordenadas por ts. `filas`: dicts etapa, valor, ts, detalle."""
    ult: dict[str, dict] = {}
    for f in filas:
        if f.get("detalle") != "success":
            continue
        previa = ult.get(f["etapa"])
        if previa is None or f["ts"] >= previa["ts"]:
            ult[f["etapa"]] = f
    return [(f["etapa"], float(f["valor"])) for f in sorted(ult.values(), key=lambda x: x["ts"])]


def reloj_dagrun(inicio: str | None, fin: str | None) -> float | None:
    if not inicio or not fin:
        return None
    a = dt.datetime.fromisoformat(inicio.replace("Z", "+00:00"))
    b = dt.datetime.fromisoformat(fin.replace("Z", "+00:00"))
    return (b - a).total_seconds()


def fmt_seg(s: float) -> str:
    return f"{s:,.1f}"


def tiempos_a_markdown(duraciones: list[tuple[str, float]], reloj_s: float | None, run_id: str, ts: str) -> str:
    out = ["# Tiempos por etapa", "", f"Generado por `ingest/evidencia_p2.py` · run_id `{run_id}` · {ts}", "",
           "| etapa | segundos |", "|---|---:|"]
    for etapa, s in duraciones:
        out.append(f"| {etapa} | {fmt_seg(s)} |")
    out.append(f"| **TOTAL (suma de tareas)** | **{fmt_seg(sum(s for _, s in duraciones))}** |")
    if reloj_s is not None:
        out.append(f"| **TOTAL (reloj del DagRun)** | **{fmt_seg(reloj_s)}** |")
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def leer_duraciones(bq, run_id: str) -> list[tuple[str, float]]:
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("run_id", "STRING", run_id)])
    consulta = f"""
        SELECT etapa, valor, ts, detalle
        FROM `{common.RUN_METRICS_TABLE}`
        WHERE run_id = @run_id AND metrica = 'duracion_s'
    """
    filas = [{"etapa": r.etapa, "valor": r.valor, "ts": r.ts, "detalle": r.detalle} for r in bq.query(consulta, job_config=cfg).result()]
    return ultimas_duraciones(filas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--salida-dir", type=Path, default=SALIDA_DEFECTO)
    ap.add_argument("--esperados", type=Path, default=ESPERADOS_DEFECTO)
    ap.add_argument("--inicio", help="inicio del DagRun (ISO 8601)")
    ap.add_argument("--fin", help="fin del DagRun (ISO 8601)")
    ap.add_argument("--dag-run-json", type=Path, help="JSON del DagRun (campos start_date y end_date)")
    args = ap.parse_args(argv)

    inicio, fin = args.inicio, args.fin
    if args.dag_run_json:
        dr = json.loads(args.dag_run_json.read_text(encoding="utf-8"))
        inicio, fin = dr.get("start_date") or inicio, dr.get("end_date") or fin

    bq = common.bq_client()
    ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    args.salida_dir.mkdir(parents=True, exist_ok=True)
    esperados = cargar_esperados(args.esperados)

    # (a) conteos de Bronze vs. LEEME
    from ingest.conteos_bronze import contar_bronze
    filas = []
    for fuente in common.FUENTES.values():
        n, d, err = contar_bronze(bq, fuente)
        filas.append(fila_conteo(fuente, esperados.get(fuente.archivo), n, d, err))
    (args.salida_dir / "conteos_bronze.md").write_text(conteos_a_markdown(filas, args.run_id, ts), encoding="utf-8")

    # (b) tiempos
    dur = leer_duraciones(bq, args.run_id)
    (args.salida_dir / "tiempos.md").write_text(
        tiempos_a_markdown(dur, reloj_dagrun(inicio, fin), args.run_id, ts), encoding="utf-8")

    # (c) conteos por capa
    snap = conteos_capas.tomar_snapshot(bq)
    (args.salida_dir / "conteos_capas.md").write_text(conteos_capas.a_markdown(snap), encoding="utf-8")

    for nombre in ("conteos_bronze.md", "tiempos.md", "conteos_capas.md"):
        print(f"[evidencia] escrito {args.salida_dir / nombre}")
    ok = all(f["ok"] for f in filas)
    print(f"[evidencia] Bronze vs. LEEME: {'OK' if ok else 'HAY DIFERENCIAS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
