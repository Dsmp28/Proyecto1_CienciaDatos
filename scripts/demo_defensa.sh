#!/usr/bin/env bash
# Demostración de MLOps del video de defensa (parte 2), en una sola toma:
#   1. git log -1: el commit en uso debe ser el de la etiqueta entrega-final.
#   2. python predecir.py --datos <carpeta de 90 días> --fecha-corte 2026-08-30 (carga el modelo guardado, no reentrena).
#   3. Compara la salida con el CSV entregado en el repositorio: sha256 de ambos y diff.
#   4. Señala en la ficha del modelo las fugas revisadas y los límites.
# Uso: scripts/demo_defensa.sh [carpeta_de_datos] [bigquery|csv]
# Con `csv` no hace falta GCP: lee el respaldo versionado de las features del corte.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

DATOS="${1:-docs/P2_datos_red/datos_red}"
ORIGEN="${2:-bigquery}"
PY="${PY:-.venv/bin/python}"
FECHA="2026-08-30"
ENTREGADO="predicciones/predicciones_corte_${FECHA}.csv"
SALIDA="tmp/predicciones_demo_${FECHA}.csv"

paso() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
correr() { printf '$ %s\n' "$*"; "$@"; }

paso "Paso 1 · commit en uso (debe ser el de la etiqueta entrega-final)"
correr git log -1 --decorate --format='%H%n%d%n%an · %ad%n%s' --date=iso
correr git status --short
correr git rev-parse 'entrega-final^{commit}'

paso "Paso 2 · predecir.py con los datos de 90 días (modelo guardado, sin reentrenar)"
mkdir -p tmp
correr "$PY" predecir.py --datos "$DATOS" --fecha-corte "$FECHA" --origen "$ORIGEN" --salida "$SALIDA"

paso "Paso 3 · la salida coincide con el CSV entregado"
correr wc -l "$SALIDA" "$ENTREGADO"
correr shasum -a 256 "$SALIDA" "$ENTREGADO"
printf '$ git show entrega-final:%s | shasum -a 256\n' "$ENTREGADO"
git show "entrega-final:${ENTREGADO}" | shasum -a 256
if correr diff -q "$SALIDA" "$ENTREGADO"; then
  printf '\033[1mIDÉNTICOS: 0 diferencias\033[0m\n'
else
  printf '\033[1mDIFIEREN\033[0m\n'; exit 1
fi

paso "Paso 4 · ficha del modelo: fugas revisadas y límites"
correr grep -n '^## Fugas revisadas\|^## Límites y riesgos' docs/P2/FICHA_MODELO.md
correr sed -n '/^## Fugas revisadas/,/^## Uso y mantenimiento/p' docs/P2/FICHA_MODELO.md
