"""Invariancia de las predicciones: compara dos CSV de `predecir.py` (referencia vs nueva).

Compara el conjunto de `unidad_id` (faltantes/sobrantes), `tarjetas` y `contactar` con igualdad exacta, y `puntaje`
tras redondear a 6 decimales (tolerancia 1e-6). Salida 0 si son idénticas, 1 si difieren, 2 si no se pueden leer.
Uso: `python -m ml.invariancia --referencia A.csv --nueva B.csv [--informe docs/evidence/p2/invariancia_<ts>.md]`.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

TOLERANCIA = 1e-6
COLUMNAS = ["unidad_id", "tarjetas", "puntaje", "contactar"]


def leer(ruta: Path) -> pd.DataFrame:
    df = pd.read_csv(ruta, dtype={"unidad_id": "string", "tarjetas": "string"})
    faltan = [c for c in COLUMNAS if c not in df]
    if faltan:
        raise ValueError(f"{ruta}: faltan columnas {faltan}")
    if df["unidad_id"].duplicated().any():
        raise ValueError(f"{ruta}: unidad_id repetidos")
    return df[COLUMNAS]


def comparar(ref: pd.DataFrame, nueva: pd.DataFrame, tolerancia: float = TOLERANCIA) -> dict:
    """Resultado puro: ids faltantes/sobrantes, filas comparadas y diferencias por columna (con ejemplos)."""
    ids_ref, ids_nueva = set(ref["unidad_id"]), set(nueva["unidad_id"])
    faltantes, sobrantes = sorted(ids_ref - ids_nueva), sorted(ids_nueva - ids_ref)
    m = ref.merge(nueva, on="unidad_id", suffixes=("_ref", "_nueva"))
    difs = {}
    for c in ("tarjetas", "contactar"):
        a, b = m[f"{c}_ref"], m[f"{c}_nueva"]
        distinto = ~((a == b) | (a.isna() & b.isna())).fillna(False)
        difs[c] = m.loc[distinto, ["unidad_id", f"{c}_ref", f"{c}_nueva"]]
    pa, pb = np.round(m["puntaje_ref"].astype(float), 6), np.round(m["puntaje_nueva"].astype(float), 6)
    distinto = ~np.isclose(pa, pb, rtol=0, atol=tolerancia + 1e-12, equal_nan=True)
    difs["puntaje"] = m.loc[distinto, ["unidad_id", "puntaje_ref", "puntaje_nueva"]]
    n_difs = {c: len(d) for c, d in difs.items()}
    identicas = not faltantes and not sobrantes and not any(n_difs.values())
    return {"filas_ref": len(ref), "filas_nueva": len(nueva), "filas_comparadas": len(m), "faltantes": faltantes,
            "sobrantes": sobrantes, "diferencias": n_difs, "detalle": difs, "identicas": identicas}


def tabla_md(df: pd.DataFrame) -> str:
    """Tabla Markdown sin depender de `tabulate`."""
    filas = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    filas += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(filas)


def informe_markdown(res: dict, referencia: str, nueva: str, ejemplos: int = 10) -> str:
    L = ["# Invariancia de las predicciones", "",
         f"- Referencia: `{referencia}` ({res['filas_ref']} filas)",
         f"- Nueva: `{nueva}` ({res['filas_nueva']} filas)",
         f"- Filas comparadas: {res['filas_comparadas']}",
         f"- Unidades faltantes en la nueva: {len(res['faltantes'])}; sobrantes: {len(res['sobrantes'])}",
         f"- Tolerancia de `puntaje`: {TOLERANCIA} (inclusiva) tras redondear a 6 decimales", "",
         "| Columna | Filas distintas |", "|---|---|"]
    L += [f"| {c} | {n} |" for c, n in res["diferencias"].items()]
    L += ["", f"**Resultado: {'IDÉNTICAS' if res['identicas'] else 'DIFIEREN'}**"]
    for c, d in res["detalle"].items():
        if len(d):
            L += ["", f"## Ejemplos de `{c}`", "", tabla_md(d.head(ejemplos))]
    if res["faltantes"]:
        L += ["", "## Faltantes (primeros)", "", ", ".join(f"`{u}`" for u in res["faltantes"][:ejemplos])]
    if res["sobrantes"]:
        L += ["", "## Sobrantes (primeros)", "", ", ".join(f"`{u}`" for u in res["sobrantes"][:ejemplos])]
    return "\n".join(L) + "\n"


def ejecutar(referencia, nueva, informe=None, out=print) -> int:
    try:
        ref, nue = leer(Path(referencia)), leer(Path(nueva))
    except Exception as e:  # noqa: BLE001 — cualquier fallo de lectura es código 2
        out(f"ERROR: no se pueden leer los CSV: {e}")
        return 2
    res = comparar(ref, nue)
    out(f"Filas comparadas: {res['filas_comparadas']} (ref {res['filas_ref']}, nueva {res['filas_nueva']}); "
        f"faltantes {len(res['faltantes'])}, sobrantes {len(res['sobrantes'])}")
    for c, n in res["diferencias"].items():
        out(f"  diferencias en {c}: {n}")
    out("IDÉNTICAS" if res["identicas"] else "DIFIEREN")
    if informe:
        ruta = Path(informe)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(informe_markdown(res, str(referencia), str(nueva)), encoding="utf-8")
        out(f"Informe: {ruta}")
    return 0 if res["identicas"] else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--referencia", required=True)
    p.add_argument("--nueva", required=True)
    p.add_argument("--informe", nargs="?", const="", default=None,
                   help="ruta del informe Markdown (sin valor: docs/evidence/p2/invariancia_<ts>.md)")
    a = p.parse_args(argv)
    informe = a.informe
    if informe == "":
        from ml import config as cfg
        informe = cfg.EVIDENCIA / f"invariancia_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.md"
    return ejecutar(a.referencia, a.nueva, informe)


if __name__ == "__main__":
    sys.exit(main())
