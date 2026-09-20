"""Idempotencia: ningún modelo, macro, seed o prueba de dbt usa la fecha del sistema.

La fecha de referencia es var('fecha_referencia'); CURRENT_DATE/CURRENT_TIMESTAMP/NOW
cambiarían los conteos entre corridas. Se permiten solo en models/ops (marcas de tiempo
de auditoría de la corrida) y en macros marcadas con `-- idempotencia: permitido`.
"""
import re
from pathlib import Path

PATRON = re.compile(r"\b(CURRENT_DATE|CURRENT_TIMESTAMP|CURRENT_DATETIME|CURRENT_TIME|NOW)\s*\(", re.IGNORECASE)
EXENTOS = ("models/ops/",)
MARCA_PERMISO = "idempotencia: permitido"


def _archivos_sql(dbt_dir: Path):
    for sub in ("models", "macros", "tests", "analyses"):
        base = dbt_dir / sub
        if base.exists():
            # Se omiten archivos ocultos (p. ej. `._x.sql`, metadatos AppleDouble que deja tar en macOS): dbt no los lee.
            yield from (p for p in base.rglob("*.sql") if not p.name.startswith("."))


def test_sin_fecha_del_sistema(dbt_dir):
    hallazgos = []
    for path in _archivos_sql(dbt_dir):
        rel = path.relative_to(dbt_dir).as_posix()
        if rel.startswith(EXENTOS):
            continue
        texto = path.read_text(encoding="utf-8")
        if MARCA_PERMISO in texto:
            continue
        for i, linea in enumerate(texto.splitlines(), 1):
            if PATRON.search(linea):
                hallazgos.append(f"{rel}:{i}: {linea.strip()}")
    assert not hallazgos, "Uso de fecha del sistema (rompe idempotencia):\n" + "\n".join(hallazgos)
