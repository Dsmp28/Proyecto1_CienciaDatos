#!/usr/bin/env bash
# Carga desde cero (Proyecto 2): reset confirmado -> sincroniza la VM -> dispara el DAG `red_metropolitana`
# -> espera -> genera la evidencia (conteos Bronze vs. LEEME, tiempos por etapa, conteos por capa).
#
# Uso:
#   CONFIRMAR=BORRAR-cienciadatos-509301 scripts/desde_cero.sh      # reset + carga completa
#   scripts/desde_cero.sh --sin-reset                              # solo sincroniza, dispara y genera evidencia
#
# Variables de entorno:
#   CONFIRMAR        obligatoria salvo --sin-reset; debe ser exactamente BORRAR-<PROJECT_ID>.
#   ORIGEN_DATOS     landing (defecto) | generador | local.   VERSION_DATOS  v2 (defecto).
#   VERIFICAR_HASHES true (defecto) | false.
#   AIRFLOW_URL, AIRFLOW_USER, PROJECT_ID, EVIDENCIA_DIR (defecto docs/evidence/p2), INTERVALO_S (30), TIMEOUT_MIN (90).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PY="${PY:-$REPO/.venv/bin/python}"
DAG_ID="red_metropolitana"
PROJECT_ID="${PROJECT_ID:-cienciadatos-509301}"
AIRFLOW_USER="${AIRFLOW_USER:-admin}"
AIRFLOW_URL="${AIRFLOW_URL:-}"
EVIDENCIA_DIR="${EVIDENCIA_DIR:-$REPO/docs/evidence/p2}"
INTERVALO_S="${INTERVALO_S:-30}"
TIMEOUT_MIN="${TIMEOUT_MIN:-90}"
TS="$(date +%Y%m%dT%H%M%S)"
RUN_ID="desde-cero-${TS}"

source "$REPO/scripts/lib_airflow.sh"

SIN_RESET=0
for a in "$@"; do
  case "$a" in
    --sin-reset) SIN_RESET=1 ;;
    *) fallo "argumento desconocido: $a (uso: $0 [--sin-reset])" ;;
  esac
done

if [[ $SIN_RESET -eq 0 ]]; then
  [[ "${CONFIRMAR:-}" == "BORRAR-${PROJECT_ID}" ]] || fallo "falta CONFIRMAR=BORRAR-${PROJECT_ID} (o usa --sin-reset)"
  log "== 1. Reset =="
  "$PY" scripts/reset_p2.py --confirmar "$CONFIRMAR"
else
  log "== 1. Reset omitido (--sin-reset) =="
fi

log "== 2. Sincronizar código a la VM =="
make vm-sync

log "== 3. Login a Airflow =="
airflow_login
airflow_despausar

log "== 4. Disparar $RUN_ID =="
CONF="$(printf '{"origen_datos":"%s","version_datos":"%s","verificar_hashes":%s}' \
  "${ORIGEN_DATOS:-landing}" "${VERSION_DATOS:-v2}" "${VERIFICAR_HASHES:-true}")"
log "conf: $CONF"
CUERPO="$(printf '{"dag_run_id": "%s", "logical_date": null, "conf": %s, "note": "carga desde cero del Proyecto 2"}' "$RUN_ID" "$CONF")"
RESP="$(api POST "/dags/$DAG_ID/dagRuns" "$CUERPO")"
log "Corrida $RUN_ID encolada (estado inicial: $(printf '%s' "$RESP" | campo state))"

LIMITE=$(( $(date +%s) + TIMEOUT_MIN * 60 ))
while :; do
  DR="$(api GET "/dags/$DAG_ID/dagRuns/$RUN_ID")"
  ESTADO="$(printf '%s' "$DR" | campo state)"
  PROGRESO="$(api GET "/dags/$DAG_ID/dagRuns/$RUN_ID/taskInstances?limit=100" | "$PY" -c "$PY_PROGRESO" 2>/dev/null || echo "?")"
  log "  $RUN_ID: estado=$ESTADO · tareas: $PROGRESO"
  case "$ESTADO" in success|failed) break ;; esac
  [[ $(date +%s) -lt $LIMITE ]] || fallo "tiempo agotado (${TIMEOUT_MIN} min) esperando $RUN_ID"
  sleep "$INTERVALO_S"
done
[[ "$ESTADO" == "success" ]] || fallo "la corrida $RUN_ID terminó en $ESTADO; revisa la UI de Airflow"
NO_VERDES="$(api GET "/dags/$DAG_ID/dagRuns/$RUN_ID/taskInstances?limit=100" | "$PY" -c "$PY_NO_VERDES_SALVO_SKIPPED")"
[[ -z "$NO_VERDES" ]] || fallo "tareas no exitosas en $RUN_ID: $NO_VERDES"
log "todas las tareas (salvo registrar_fallo y las omitidas) están en success"

log "== 5. Evidencia =="
mkdir -p "$EVIDENCIA_DIR"
DR_JSON="$EVIDENCIA_DIR/dagrun_${RUN_ID}.json"
printf '%s' "$DR" > "$DR_JSON"
RC=0
"$PY" ingest/evidencia_p2.py --run-id "$RUN_ID" --salida-dir "$EVIDENCIA_DIR" --dag-run-json "$DR_JSON" || RC=$?

echo
cat "$EVIDENCIA_DIR/conteos_bronze.md" "$EVIDENCIA_DIR/tiempos.md" 2>/dev/null || true
if [[ $RC -ne 0 ]]; then
  log "RESULTADO: HAY DIFERENCIAS entre Bronze y el LEEME (ver $EVIDENCIA_DIR/conteos_bronze.md)"
  exit 1
fi
log "RESULTADO: OK — evidencia en $EVIDENCIA_DIR (run_id $RUN_ID)"
