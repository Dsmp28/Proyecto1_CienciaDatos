"""Genera (si faltan) y verifica los 9 archivos crudos de datos_red/.

Uso:
    python ingest/generar_o_verificar.py [--json] [--sin-verificar] [--regenerar]

Flujo:
1. Si falta alguno de los 9 archivos del catálogo (o se pide --regenerar), ejecuta el
   generador oficial `docs/generar_red_metropolitana.py`. El generador escribe siempre en
   `./datos_red` relativo a su cwd, así que se lanza con cwd = raíz del repo (o el padre
   de DATOS_DIR cuando DATOS_DIR apunta a otro sitio).
2. Calcula sha256, filas de datos y bytes de cada archivo y los compara con
   `ingest/expected_hashes.json` (huella de la corrida oficial: ESCALA=0.08, semilla 2026).
   Cualquier diferencia termina con código 1, salvo `--sin-verificar`.
3. Imprime una tabla; con `--json` vuelca el resultado en la salida estándar (la tabla va
   a stderr) para que Airflow lo recoja por XCom.

Variable de entorno ESCALA: si existe y no es "0.08" ni vacía, se ejecuta una copia
temporal del generador con esa escala y se omite la verificación de hashes (los
archivos ya no coinciden con la huella oficial por diseño).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ingest.common import DATOS_DIR, FUENTES, contar_filas, sha256_archivo  # noqa: E402

GENERADOR = REPO / "docs" / "generar_red_metropolitana.py"
HASHES_ESPERADOS = REPO / "ingest" / "expected_hashes.json"
ESCALA_OFICIAL = "0.08"
PATRON_ESCALA = re.compile(r"^(ESCALA\s*=\s*)[0-9.]+", re.M)


# ---------------------------------------------------------------------------
# Funciones puras (probadas en tests/test_ingest_batch.py)
# ---------------------------------------------------------------------------
def escala_personalizada(valor: str | None) -> str | None:
    """Devuelve la escala pedida por entorno si difiere de la oficial; None en otro caso."""
    if valor is None:
        return None
    valor = valor.strip()
    if valor == "" or valor == ESCALA_OFICIAL:
        return None
    try:
        float(valor)
    except ValueError as exc:
        raise ValueError(f"ESCALA={valor!r} no es un número") from exc
    return valor


def sustituir_escala(codigo: str, escala: str) -> str:
    """Reemplaza la línea `ESCALA = 0.08` del generador por la escala pedida."""
    nuevo, n = PATRON_ESCALA.subn(rf"\g<1>{escala}", codigo, count=1)
    if n != 1:
        raise ValueError("No se encontró la línea `ESCALA = ...` en el generador")
    return nuevo


def comparar_hashes(esperado: dict[str, dict], calculado: dict[str, dict]) -> list[dict]:
    """Compara, archivo por archivo, la huella esperada con la calculada.

    Devuelve una lista (ordenada por archivo) de dicts con: archivo, bytes, filas, sha256,
    esperado_sha256, esperado_filas, verificado (bool) y detalle (por qué falló, si falló).
    Un archivo presente en `esperado` pero ausente en `calculado` cuenta como fallo.
    """
    filas = []
    for archivo in sorted(set(esperado) | set(calculado)):
        esp = esperado.get(archivo)
        cal = calculado.get(archivo)
        fila = {
            "archivo": archivo,
            "bytes": cal["bytes"] if cal else None,
            "filas": cal["filas_datos"] if cal else None,
            "sha256": cal["sha256"] if cal else None,
            "esperado_sha256": esp["sha256"] if esp else None,
            "esperado_filas": esp["filas_datos"] if esp else None,
        }
        if cal is None:
            fila.update(verificado=False, detalle="archivo ausente")
        elif esp is None:
            fila.update(verificado=False, detalle="sin huella esperada")
        elif cal["sha256"] != esp["sha256"]:
            fila.update(verificado=False, detalle="sha256 distinto")
        elif cal["filas_datos"] != esp["filas_datos"]:
            fila.update(verificado=False, detalle="filas distintas")
        else:
            fila.update(verificado=True, detalle="")
        filas.append(fila)
    return filas


def formatear_tabla(filas: list[dict]) -> str:
    ancho = max(len(f["archivo"]) for f in filas) if filas else 10
    cab = f"{'archivo':<{ancho}} | {'bytes':>10} | {'filas':>8} | {'sha256[:12]':<12} | verificado"
    lineas = [cab, "-" * len(cab)]
    for f in filas:
        sha = (f["sha256"] or "")[:12]
        est = "sí" if f["verificado"] else f"NO ({f['detalle']})"
        lineas.append(f"{f['archivo']:<{ancho}} | {f['bytes'] if f['bytes'] is not None else '-':>10} | "
                      f"{f['filas'] if f['filas'] is not None else '-':>8} | {sha:<12} | {est}")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Efectos: generador y cálculo de huellas
# ---------------------------------------------------------------------------
def directorio_trabajo_generador(datos_dir: Path) -> Path:
    """cwd para el generador: escribe en ./datos_red, así que el cwd es el padre de DATOS_DIR."""
    datos_dir = datos_dir.resolve()
    if datos_dir.name != "datos_red":
        raise SystemExit(
            f"DATOS_DIR={datos_dir} no se llama 'datos_red'; el generador solo escribe en ./datos_red. "
            "Ajusta DATOS_DIR o genera los datos manualmente."
        )
    return datos_dir.parent


def ejecutar_generador(datos_dir: Path, escala: str | None) -> None:
    cwd = directorio_trabajo_generador(datos_dir)
    if escala is None:
        script = GENERADOR
        print(f"[generar] Faltan archivos: ejecutando {GENERADOR.relative_to(REPO)} (cwd={cwd})", file=sys.stderr)
        subprocess.run([sys.executable, str(script)], cwd=cwd, check=True)
        return
    codigo = sustituir_escala(GENERADOR.read_text(encoding="utf-8"), escala)
    with tempfile.TemporaryDirectory(prefix="generador_") as tmp:
        script = Path(tmp) / GENERADOR.name
        script.write_text(codigo, encoding="utf-8")
        print(f"[generar] Ejecutando copia temporal del generador con ESCALA={escala} (cwd={cwd})", file=sys.stderr)
        subprocess.run([sys.executable, str(script)], cwd=cwd, check=True)


def calcular_huellas(datos_dir: Path) -> dict[str, dict]:
    huellas = {}
    for nombre, fuente in FUENTES.items():
        p = datos_dir / nombre
        if not p.exists():
            continue
        huellas[nombre] = {
            "sha256": sha256_archivo(p),
            "filas_datos": contar_filas(p, fuente.formato),
            "bytes": p.stat().st_size,
        }
    return huellas


def archivos_faltantes(datos_dir: Path) -> list[str]:
    return [n for n in FUENTES if not (datos_dir / n).exists()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="vuelca el resultado como JSON en stdout (tabla a stderr)")
    ap.add_argument("--sin-verificar", action="store_true", help="no falla si los hashes difieren de expected_hashes.json")
    ap.add_argument("--regenerar", action="store_true", help="ejecuta el generador aunque los archivos existan")
    args = ap.parse_args(argv)

    datos_dir = DATOS_DIR if DATOS_DIR.is_absolute() else REPO / DATOS_DIR
    escala = escala_personalizada(os.environ.get("ESCALA"))
    verificar = not args.sin_verificar
    avisos: list[str] = []

    faltan = archivos_faltantes(datos_dir)
    generado = False
    if faltan or args.regenerar:
        ejecutar_generador(datos_dir, escala)
        generado = True
        faltan = archivos_faltantes(datos_dir)
        if faltan:
            raise SystemExit(f"El generador terminó pero siguen faltando: {faltan}")

    if escala is not None and verificar:
        avisos.append(f"ESCALA={escala} distinta de la oficial ({ESCALA_OFICIAL}): se omite la verificación de hashes")
        verificar = False

    esperado = json.loads(HASHES_ESPERADOS.read_text(encoding="utf-8"))["archivos"]
    calculado = calcular_huellas(datos_dir)
    filas = comparar_hashes(esperado, calculado)
    todo_ok = all(f["verificado"] for f in filas)

    resultado = {
        "datos_dir": str(datos_dir),
        "generado": generado,
        "escala": escala or ESCALA_OFICIAL,
        "verificacion_aplicada": verificar,
        "todo_verificado": todo_ok,
        "avisos": avisos,
        "archivos": filas,
    }

    salida_tabla = sys.stderr if args.json else sys.stdout
    for a in avisos:
        print(f"[aviso] {a}", file=salida_tabla)
    print(formatear_tabla(filas), file=salida_tabla)
    print(("Todos los archivos verificados." if todo_ok else "HAY DIFERENCIAS respecto a expected_hashes.json."),
          file=salida_tabla)
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False))

    if verificar and not todo_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
