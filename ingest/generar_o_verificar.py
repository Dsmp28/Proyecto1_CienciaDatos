"""Genera (si faltan) y verifica los 9 archivos crudos de datos_red/.

Uso:
    python ingest/generar_o_verificar.py [--json] [--sin-verificar] [--regenerar]
                                         [--origen {landing,generador,local}] [--version v2]

Origen de los datos (`--origen` o env ORIGEN_DATOS, default `landing`; `--version` o env
VERSION_DATOS, default `v2`):
- `landing`: si falta algún archivo o su sha256 no coincide con `ingest/expected_hashes.json`
  (datos v2 del Proyecto 2), los baja de `gs://<lake>/landing/datos_red/<version>/`
  con `ingest.landing.descargar` y luego verifica.
- `generador`: comportamiento del Proyecto 1; si falta algo (o --regenerar) ejecuta
  `docs/generar_red_metropolitana.py` y compara con `ingest/expected_hashes_p1.json`.
  El generador escribe siempre en `./datos_red` relativo a su cwd, así que se lanza con
  cwd = padre de DATOS_DIR.
- `local`: nunca descarga ni genera; solo verifica lo que haya en DATOS_DIR.

Verificación: calcula sha256, filas de datos y bytes de cada archivo y los compara con la huella
del origen elegido. Cualquier diferencia termina con código 1, salvo `--sin-verificar` o la env
VERIFICAR_HASHES en {false, 0, no}.
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
HASHES_ESPERADOS = REPO / "ingest" / "expected_hashes.json"        # datos v2 (Proyecto 2)
HASHES_ESPERADOS_P1 = REPO / "ingest" / "expected_hashes_p1.json"  # generador (Proyecto 1)
ORIGENES = ("landing", "generador", "local")
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


def resolver_origen(arg: str | None, env: str | None) -> str:
    """Origen de datos: argumento > env ORIGEN_DATOS > `landing`."""
    valor = (arg or env or "landing").strip().lower()
    if valor not in ORIGENES:
        raise ValueError(f"origen={valor!r} inválido; usa uno de {ORIGENES}")
    return valor


def resolver_version(arg: str | None, env: str | None) -> str:
    """Versión de datos: argumento > env VERSION_DATOS > `v2`."""
    return (arg or env or "v2").strip()


def verificar_desde_env(valor: str | None) -> bool:
    """False si VERIFICAR_HASHES vale false/0/no (sin distinguir mayúsculas); True en otro caso."""
    return (valor or "").strip().lower() not in ("false", "0", "no")


def huella_esperada_para(origen: str) -> Path:
    """Archivo de huellas: el del generador (P1) solo con origen `generador`; v2 en los demás."""
    return HASHES_ESPERADOS_P1 if origen == "generador" else HASHES_ESPERADOS


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
    ap.add_argument("--regenerar", action="store_true", help="ejecuta el generador aunque los archivos existan (origen generador)")
    ap.add_argument("--origen", choices=ORIGENES, default=None, help="landing (default, env ORIGEN_DATOS) | generador | local")
    ap.add_argument("--version", default=None, help="versión en landing (default v2, env VERSION_DATOS)")
    args = ap.parse_args(argv)
    origen = resolver_origen(args.origen, os.environ.get("ORIGEN_DATOS"))
    version = resolver_version(args.version, os.environ.get("VERSION_DATOS"))

    datos_dir = DATOS_DIR if DATOS_DIR.is_absolute() else REPO / DATOS_DIR
    escala = escala_personalizada(os.environ.get("ESCALA"))
    verificar = not args.sin_verificar and verificar_desde_env(os.environ.get("VERIFICAR_HASHES"))
    avisos: list[str] = []
    esperado = json.loads(huella_esperada_para(origen).read_text(encoding="utf-8"))["archivos"]

    generado = False
    descargados: list[str] = []
    if origen == "generador":
        faltan = archivos_faltantes(datos_dir)
        if faltan or args.regenerar:
            ejecutar_generador(datos_dir, escala)
            generado = True
            faltan = archivos_faltantes(datos_dir)
            if faltan:
                raise SystemExit(f"El generador terminó pero siguen faltando: {faltan}")
        if escala is not None and verificar:
            avisos.append(f"ESCALA={escala} distinta de la oficial ({ESCALA_OFICIAL}): se omite la verificación de hashes")
            verificar = False
    elif origen == "landing":
        from ingest import landing  # importación perezosa: solo aquí hace falta GCS

        calculado = calcular_huellas(datos_dir)
        if any(not f["verificado"] for f in comparar_hashes(esperado, calculado)):
            print(f"[landing] Descargando versión {version} a {datos_dir}", file=sys.stderr)
            descargados = landing.descargar(version, datos_dir, solo_faltantes=True)

    calculado = calcular_huellas(datos_dir)
    filas = comparar_hashes(esperado, calculado)
    todo_ok = all(f["verificado"] for f in filas)

    resultado = {
        "datos_dir": str(datos_dir),
        "origen": origen,
        "version": version if origen == "landing" else None,
        "descargados": descargados,
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
    print(("Todos los archivos verificados." if todo_ok else "HAY DIFERENCIAS respecto a la huella esperada."),
          file=salida_tabla)
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False))

    if verificar and not todo_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
