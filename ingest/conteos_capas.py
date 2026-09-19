"""Instantánea de conteos por capa: COUNT(*) de todas las tablas de bronze, staging, silver,
quarantine, gold y features, más objetos y bytes en gs://<bucket>/bronze/.

Uso:
    python ingest/conteos_capas.py                       # tabla Markdown por stdout
    python ingest/conteos_capas.py --json                # JSON determinista por stdout
    python ingest/conteos_capas.py --salida x.json       # guarda JSON (y .md si termina en .md)
    python ingest/conteos_capas.py --comparar a.json b.json [--salida informe.md]
                                                         # exit 1 si difiere alguna tabla u objeto

Es la comparación que usa la demo de idempotencia (scripts/demo_idempotencia.sh): dos corridas del
DAG deben producir instantáneas idénticas (mismas tablas, mismos conteos, mismos objetos en Bronze).
La lista de tablas es dinámica (`client.list_tables` por dataset) y la salida está ordenada, por lo
que dos instantáneas se pueden comparar clave a clave. Las funciones puras (`comparar_snapshots`,
`a_markdown`, `markdown_comparacion`) no tocan la red y se prueban en tests/test_dag.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ingest import common  # noqa: E402

CAPAS: tuple[str, ...] = ("bronze", "staging", "silver", "quarantine", "gold", "features")
PREFIJO_BRONZE = "bronze/"


# ---------------------------------------------------------------------------
# Funciones puras
# ---------------------------------------------------------------------------
def clave_tabla(capa: str, tabla: str) -> str:
    return f"{capa}.{tabla}"


def comparar_snapshots(a: dict, b: dict) -> list[dict]:
    """Diferencias entre dos instantáneas: tablas (conteo o ausencia) y objetos/bytes de Bronze.

    Devuelve una lista ordenada de {"clave", "a", "b", "tipo"}; vacía si son idénticas.
    `a`/`b` en None significa que la clave no existe en esa instantánea.
    """
    difs: list[dict] = []
    ta, tb = a.get("tablas", {}), b.get("tablas", {})
    for clave in sorted(set(ta) | set(tb)):
        va, vb = ta.get(clave), tb.get(clave)
        if va != vb:
            difs.append({"clave": clave, "a": va, "b": vb, "tipo": "tabla"})
    ga, gb = a.get("gcs_bronze", {}), b.get("gcs_bronze", {})
    for campo in ("objetos", "bytes"):
        if ga.get(campo) != gb.get(campo):
            difs.append({"clave": f"gcs:bronze/ ({campo})", "a": ga.get(campo), "b": gb.get(campo), "tipo": "gcs"})
    fa, fb = ga.get("por_fuente", {}), gb.get("por_fuente", {})
    for fuente in sorted(set(fa) | set(fb)):
        for campo in ("objetos", "bytes"):
            va = (fa.get(fuente) or {}).get(campo)
            vb = (fb.get(fuente) or {}).get(campo)
            if va != vb:
                difs.append({"clave": f"gcs:bronze/{fuente}/ ({campo})", "a": va, "b": vb, "tipo": "gcs"})
    return difs


def _fmt(v) -> str:
    return "—" if v is None else f"{v:,}"


def a_markdown(snapshot: dict) -> str:
    """Tabla Markdown por capa más el resumen de GCS."""
    out = [f"### Conteos por capa · {snapshot.get('generado_ts', '')}", ""]
    tablas = snapshot.get("tablas", {})
    for capa in CAPAS:
        filas = sorted((k.split(".", 1)[1], v) for k, v in tablas.items() if k.startswith(capa + "."))
        out += [f"**{capa}** ({len(filas)} tablas, {sum(v for _, v in filas):,} filas)", ""]
        if filas:
            out += ["| tabla | filas |", "|---|---:|"]
            out += [f"| {t} | {_fmt(v)} |" for t, v in filas]
        else:
            out.append("_(sin tablas)_")
        out.append("")
    gcs = snapshot.get("gcs_bronze", {})
    out += [f"**GCS `gs://{snapshot.get('bucket', '?')}/bronze/`**: {_fmt(gcs.get('objetos'))} objetos, {_fmt(gcs.get('bytes'))} bytes", ""]
    por_fuente = gcs.get("por_fuente", {})
    if por_fuente:
        out += ["| fuente | objetos | bytes |", "|---|---:|---:|"]
        out += [f"| {f} | {_fmt(v.get('objetos'))} | {_fmt(v.get('bytes'))} |" for f, v in sorted(por_fuente.items())]
        out.append("")
    return "\n".join(out)


def markdown_comparacion(a: dict, b: dict, difs: list[dict], etiqueta_a: str = "corrida 1", etiqueta_b: str = "corrida 2") -> str:
    """Tabla lado a lado de las dos instantáneas con la columna 'igual' y el veredicto final."""
    out = [f"| clave | {etiqueta_a} | {etiqueta_b} | igual |", "|---|---:|---:|:---:|"]
    ta, tb = a.get("tablas", {}), b.get("tablas", {})
    for clave in sorted(set(ta) | set(tb)):
        va, vb = ta.get(clave), tb.get(clave)
        out.append(f"| {clave} | {_fmt(va)} | {_fmt(vb)} | {'sí' if va == vb else 'NO'} |")
    ga, gb = a.get("gcs_bronze", {}), b.get("gcs_bronze", {})
    for campo in ("objetos", "bytes"):
        va, vb = ga.get(campo), gb.get(campo)
        out.append(f"| gcs:bronze/ ({campo}) | {_fmt(va)} | {_fmt(vb)} | {'sí' if va == vb else 'NO'} |")
    out.append("")
    if difs:
        out += [f"**{len(difs)} diferencia(s):**", ""]
        out += [f"- `{d['clave']}`: {_fmt(d['a'])} → {_fmt(d['b'])}" for d in difs]
        out += ["", "RESULTADO: DIFERENTES", ""]
    else:
        out += [f"Tablas comparadas: {len(set(ta) | set(tb))}. Objetos en Bronze: {_fmt(ga.get('objetos'))}.", "",
                "RESULTADO: IDÉNTICOS", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Consultas (BigQuery y GCS)
# ---------------------------------------------------------------------------
def tablas_de(bq, dataset: str) -> list[str]:
    """Nombres de tablas (nativas y externas) de un dataset, ordenados; [] si no existe."""
    try:
        return sorted(t.table_id for t in bq.list_tables(f"{common.PROJECT_ID}.{dataset}"))
    except Exception as exc:  # noqa: BLE001 — dataset ausente o sin permiso: se informa y sigue
        print(f"[conteos_capas] {dataset}: {str(exc).splitlines()[0]}", file=sys.stderr)
        return []


def contar_filas(bq, dataset: str, tablas: list[str]) -> dict[str, int]:
    """COUNT(*) de cada tabla en una sola consulta (UNION ALL)."""
    if not tablas:
        return {}
    partes = [f"SELECT '{t}' AS tabla, COUNT(*) AS n FROM `{common.PROJECT_ID}.{dataset}.{t}`" for t in tablas]
    consulta = "\nUNION ALL\n".join(partes)
    return {r.tabla: int(r.n) for r in bq.query(consulta).result()}


def objetos_bronze(gcs, bucket: str) -> dict:
    """Objetos y bytes bajo bronze/, en total y por fuente (bronze/<fuente>/...)."""
    total_obj = total_bytes = 0
    por_fuente: dict[str, dict[str, int]] = {}
    for blob in gcs.bucket(bucket).list_blobs(prefix=PREFIJO_BRONZE):
        resto = blob.name[len(PREFIJO_BRONZE):]
        if not resto or "/" not in resto:
            continue  # marcador de carpeta u objeto suelto: no es una fuente
        fuente = resto.split("/", 1)[0]
        tam = int(blob.size or 0)
        total_obj += 1
        total_bytes += tam
        acc = por_fuente.setdefault(fuente, {"objetos": 0, "bytes": 0})
        acc["objetos"] += 1
        acc["bytes"] += tam
    return {"objetos": total_obj, "bytes": total_bytes, "por_fuente": dict(sorted(por_fuente.items()))}


def tomar_snapshot(bq=None, gcs=None) -> dict:
    bq = bq or common.bq_client()
    gcs = gcs or common.gcs_client()
    tablas: dict[str, int] = {}
    for capa in CAPAS:
        nombres = tablas_de(bq, capa)
        for tabla, n in contar_filas(bq, capa, nombres).items():
            tablas[clave_tabla(capa, tabla)] = n
    return {
        "generado_ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "proyecto": common.PROJECT_ID,
        "bucket": common.LAKE_BUCKET,
        "tablas": dict(sorted(tablas.items())),
        "gcs_bronze": objetos_bronze(gcs, common.LAKE_BUCKET),
    }


def cargar(path: Path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="imprime la instantánea como JSON (ordenado)")
    ap.add_argument("--salida", type=Path, help="archivo de salida (.json o .md)")
    ap.add_argument("--comparar", nargs=2, metavar=("A.json", "B.json"), help="compara dos instantáneas y termina con 1 si difieren")
    ap.add_argument("--etiquetas", nargs=2, metavar=("A", "B"), default=("corrida 1", "corrida 2"), help="encabezados de la comparación")
    args = ap.parse_args(argv)

    if args.comparar:
        try:
            a, b = cargar(Path(args.comparar[0])), cargar(Path(args.comparar[1]))
        except (OSError, ValueError) as exc:  # archivo ausente o JSON inválido: código 2, no "difieren"
            print(f"[conteos_capas] no se pudo leer la instantánea: {exc}", file=sys.stderr)
            return 2
        difs = comparar_snapshots(a, b)
        md = markdown_comparacion(a, b, difs, *args.etiquetas)
        if args.salida:
            args.salida.parent.mkdir(parents=True, exist_ok=True)
            args.salida.write_text(md, encoding="utf-8")
        print(md)
        return 1 if difs else 0

    snap = tomar_snapshot()
    texto_json = json.dumps(snap, indent=2, sort_keys=True, ensure_ascii=False)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(a_markdown(snap) if args.salida.suffix == ".md" else texto_json, encoding="utf-8")
        print(f"[conteos_capas] escrito {args.salida}", file=sys.stderr)
    if args.json:
        print(texto_json)
    else:
        print(a_markdown(snap))
    return 0


if __name__ == "__main__":
    sys.exit(main())
