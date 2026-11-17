#!/usr/bin/env python3
"""Fabrica un conjunto de ensayo para la prueba de invariancia: los nueve archivos v2 más 30 días de registros.

El día de la defensa la cátedra entrega "los mismos datos con 30 días más". Ese zip no existe todavía, así que este
script construye un sustituto: copia byte a byte cada archivo v2 y le **anexa** los registros de los últimos 30 días
(2026-07-31 a 2026-08-29) con la fecha desplazada +30 días (2026-08-30 a 2026-09-28) e identificadores nuevos
(`validacion_id`, `boarding_id`, `trip_id` y `seq` continúan la numeración). Los catálogos se copian sin cambios.
Las líneas cuya fecha no se puede leer (problemas de calidad sembrados) no se desplazan.

No son datos de la cátedra: sirven solo para ensayar que el flujo completo, con registros posteriores al corte C,
deja idénticas las predicciones del corte 2026-08-30.

Uso:
    python scripts/fabricar_datos_ensayo.py --origen docs/P2_datos_red/datos_red --destino tmp/datos_ensayo
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

DIAS = 30
DESDE = date(2026, 7, 31)
HASTA = date(2026, 8, 29)
CATALOGOS = ["tm_estaciones.csv", "tu_paradas.csv", "mr_estaciones.csv", "am_estaciones.csv"]


def _en_rango(d: date) -> bool:
    return DESDE <= d <= HASTA


def _mover_iso(texto: str, desfase_utc_h: int = 0) -> str | None:
    """'2026-08-01T10:00:00', '2026-08-01 10:00:00' o con 'Z' final -> misma forma, +30 días; None si no aplica.

    El rango se decide con la fecha **local**. Aerómetro viene en UTC (`desfase_utc_h=-6`): un abordaje de las 20:00 del
    30 de julio aparece como 31 de julio 02:00Z; si se decidiera por la fecha UTC, al desplazarlo caería en la noche
    local del 29 de agosto, antes del corte C, y el conjunto de ensayo cambiaría datos anteriores al corte."""
    try:
        d = date.fromisoformat(texto[:10])
        local = (datetime.fromisoformat(texto[:19].replace(" ", "T")) + timedelta(hours=desfase_utc_h)).date()
    except (ValueError, TypeError):
        return None
    if not _en_rango(local):
        return None
    return (d + timedelta(days=DIAS)).isoformat() + texto[10:]


def _ultimo_id(lineas: list[str]) -> int:
    ids = []
    for linea in lineas[1:]:
        cabeza = linea.split(",", 1)[0]
        if cabeza.isdigit():
            ids.append(int(cabeza))
    return max(ids)


def _anexar_csv_con_id(origen: Path, destino: Path, col_fecha: int, desfase_utc_h: int = 0) -> int:
    """CSV cuya primera columna es un id entero y cuya columna `col_fecha` es una fecha-hora ISO."""
    lineas = origen.read_text(encoding="utf-8").splitlines()
    siguiente = _ultimo_id(lineas) + 1
    nuevas = []
    for linea in lineas[1:]:
        c = linea.split(",")
        if len(c) <= col_fecha or not c[0].isdigit():
            continue
        movida = _mover_iso(c[col_fecha], desfase_utc_h)
        if movida is None:
            continue
        c[0], c[col_fecha] = str(siguiente), movida
        siguiente += 1
        nuevas.append(",".join(c))
    with open(destino, "a", encoding="utf-8") as f:
        f.write("".join(n + "\n" for n in nuevas))
    return len(nuevas)


def _anexar_transurbano(origen: Path, destino: Path) -> int:
    """Sin identificador; fecha dd/mm/aaaa en la primera columna."""
    nuevas = []
    with open(origen, encoding="utf-8") as f:
        next(f)
        for linea in f:
            c = linea.rstrip("\n").split(",")
            try:
                d = datetime.strptime(c[0], "%d/%m/%Y").date()
            except ValueError:
                continue
            if not _en_rango(d):
                continue
            c[0] = (d + timedelta(days=DIAS)).strftime("%d/%m/%Y")
            nuevas.append(",".join(c))
    with open(destino, "a", encoding="utf-8") as f:
        f.write("".join(n + "\n" for n in nuevas))
    return len(nuevas)


def _anexar_metroriel(origen: Path, destino: Path) -> int:
    viajes, ultimo = [], 0
    with open(origen, encoding="utf-8") as f:
        for linea in f:
            try:
                j = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if isinstance(j.get("trip_id"), int):
                ultimo = max(ultimo, j["trip_id"])
            entrada = j.get("entry") if isinstance(j.get("entry"), dict) else None
            movida = _mover_iso(str(entrada.get("ts"))) if entrada else None
            if movida is None:
                continue
            viajes.append((j, movida))
    nuevas = []
    for j, movida in viajes:
        ultimo += 1
        j["trip_id"] = ultimo
        j["entry"]["ts"] = movida
        salida = j.get("exit")
        if isinstance(salida, dict) and salida.get("ts"):
            try:
                salida["ts"] = (datetime.fromisoformat(salida["ts"]) + timedelta(days=DIAS)).isoformat()
            except ValueError:
                pass
        nuevas.append(json.dumps(j, ensure_ascii=False))
    with open(destino, "a", encoding="utf-8") as f:
        f.write("".join(n + "\n" for n in nuevas))
    return len(nuevas)


def fabricar(origen: Path, destino: Path) -> dict[str, int]:
    destino.mkdir(parents=True, exist_ok=True)
    anexadas = {}
    for nombre in CATALOGOS:
        shutil.copyfile(origen / nombre, destino / nombre)
        anexadas[nombre] = 0
    for nombre, anexar in (
        ("transmetro_validaciones.csv", lambda o, d: _anexar_csv_con_id(o, d, col_fecha=4)),
        ("aerometro_boardings.csv", lambda o, d: _anexar_csv_con_id(o, d, col_fecha=4, desfase_utc_h=-6)),
        ("cdc_padron_usuarios.csv", lambda o, d: _anexar_csv_con_id(o, d, col_fecha=1)),
        ("transurbano_transacciones.csv", _anexar_transurbano),
        ("metroriel_viajes.jsonl", _anexar_metroriel),
    ):
        shutil.copyfile(origen / nombre, destino / nombre)
        with open(destino / nombre, "rb") as f:
            f.seek(-1, 2)
            if f.read(1) != b"\n":
                raise SystemExit(f"{nombre} no termina en salto de línea: no se puede anexar sin alterar el original")
        anexadas[nombre] = anexar(origen / nombre, destino / nombre)
    return anexadas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origen", type=Path, required=True, help="carpeta con los nueve archivos v2")
    ap.add_argument("--destino", type=Path, required=True, help="carpeta nueva para el conjunto de ensayo")
    args = ap.parse_args()
    if args.destino.resolve() == args.origen.resolve():
        raise SystemExit("--destino no puede ser la carpeta de origen")
    anexadas = fabricar(args.origen, args.destino)
    print("| archivo | filas anexadas (2026-08-30 a 2026-09-28) |\n|---|---:|")
    for nombre, n in anexadas.items():
        print(f"| {nombre} | {n} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
