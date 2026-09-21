#!/usr/bin/env bash
# Demo de idempotencia (rúbrica 1.5): dispara el DAG `red_metropolitana` dos veces por la REST API
# v2 de Airflow 3, toma una instantánea de conteos por capa tras cada corrida y comprueba que son
# idénticas. Se ejecuta desde la laptop: `make demo-idempotencia`.
#
# Uso:
#   scripts/demo_idempotencia.sh                       # flujo completo (2 corridas + comparación)
#   scripts/demo_idempotencia.sh --sin-disparar A.json B.json   # solo compara dos instantáneas
#
# Variables de entorno (todas opcionales):
#   AIRFLOW_URL      URL pública de Airflow (por defecto https://airflow.<IP_VM>.sslip.io;
#                    si está vacía se intenta `terraform output -raw airflow_url` en infra/main).
#   AIRFLOW_USER     usuario admin (por defecto admin).
#   PROJECT_ID       proyecto de GCP con el secreto airflow-admin-password (cienciadatos-509301).
#   EVIDENCIA_DIR    carpeta de salida (por defecto docs/evidence).
#   INTERVALO_S      segundos entre sondeos del estado (30). TIMEOUT_MIN minutos máximos por corrida (60).
#   DAG_CONF         JSON opcional para `conf` del DagRun, p. ej. '{"idle_segundos": 45}'.
#
# La contraseña de admin se lee de Secret Manager y nunca se imprime. Requiere: gcloud, curl, .venv.
set -euo pipefail

# Resume el estado de las tareas de una corrida (lee el JSON de /taskInstances por stdin).
PY_PROGRESO=$(cat <<'PYEOF'
import json, sys, collections
tis = json.load(sys.stdin).get("task_instances", [])
c = collections.Counter((t.get("state") or "pendiente") for t in tis)
resto = ", ".join(f"{k}={v}" for k, v in sorted(c.items()) if k != "success")
print(f"{c.get('success', 0)}/{len(tis)} ok" + (", " + resto if resto else ""))
PYEOF
)

# Lista las tareas que no terminaron en success (excluye registrar_fallo); vacío = todo en verde.
PY_NO_VERDES=$(cat <<'PYEOF'
import json, sys
tis = json.load(sys.stdin).get("task_instances", [])
malas = [f"{t['task_id']}={t.get('state')}" for t in tis if t["task_id"] != "registrar_fallo" and t.get("state") != "success"]
print(", ".join(malas))
PYEOF
)

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PY="${PY:-$REPO/.venv/bin/python}"
DAG_ID="red_metropolitana"
PROJECT_ID="${PROJECT_ID:-cienciadatos-509301}"
AIRFLOW_USER="${AIRFLOW_USER:-admin}"
AIRFLOW_URL="${AIRFLOW_URL:-https://airflow.<IP_VM>.sslip.io}"
EVIDENCIA_DIR="${EVIDENCIA_DIR:-$REPO/docs/evidence}"
INTERVALO_S="${INTERVALO_S:-30}"
TIMEOUT_MIN="${TIMEOUT_MIN:-60}"
DAG_CONF="${DAG_CONF:-{\}}"
TS="$(date +%Y%m%dT%H%M%S)"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
fallo() { log "ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Comparación de dos instantáneas (también usada por --sin-disparar)
# ---------------------------------------------------------------------------
comparar() {  # comparar A.json B.json informe.md etiquetaA etiquetaB
  local a="$1" b="$2" informe="$3" ea="$4" eb="$5"
  local cuerpo; cuerpo="$(mktemp)"
  local rc=0
  # Códigos de conteos_capas --comparar: 0 idénticas, 1 difieren, 2 no se pudo leer una instantánea.
  "$PY" ingest/conteos_capas.py --comparar "$a" "$b" --etiquetas "$ea" "$eb" --salida "$cuerpo" >/dev/null || rc=$?
  if [[ $rc -gt 1 ]]; then rm -f "$cuerpo"; fallo "no se pudieron comparar $a y $b (código $rc)"; fi
  cat "$cuerpo" >> "$informe"
  rm -f "$cuerpo"
  echo
  cat "$informe"
  echo
  if [[ $rc -ne 0 ]]; then
    log "RESULTADO: DIFERENTES — hay tablas u objetos de Bronze que cambiaron entre corridas (ver $informe)"
    return 1
  fi
  log "RESULTADO: IDÉNTICOS — evidencia en $informe"
  return 0
}

if [[ "${1:-}" == "--sin-disparar" ]]; then
  [[ $# -eq 3 ]] || fallo "uso: $0 --sin-disparar A.json B.json"
  mkdir -p "$EVIDENCIA_DIR"
  INFORME="$EVIDENCIA_DIR/idempotencia_${TS}.md"
  {
    echo "# Demo de idempotencia — comparación de instantáneas ($TS)"
    echo
    echo "Instantánea A: \`$2\`  ·  Instantánea B: \`$3\` (modo --sin-disparar: sin corridas nuevas)"
    echo
  } > "$INFORME"
  comparar "$2" "$3" "$INFORME" "A" "B"
  exit $?
fi

# ---------------------------------------------------------------------------
# 1. URL, contraseña (Secret Manager) y JWT
# ---------------------------------------------------------------------------
command -v gcloud >/dev/null || fallo "gcloud no está en el PATH"
command -v curl >/dev/null || fallo "curl no está en el PATH"
[[ -x "$PY" ]] || fallo "no existe $PY (ejecuta: make venv)"

if [[ -z "$AIRFLOW_URL" ]]; then
  AIRFLOW_URL="$(cd infra/main && terraform output -raw airflow_url 2>/dev/null || true)"
  [[ -n "$AIRFLOW_URL" ]] || fallo "AIRFLOW_URL vacío y no hay output de Terraform"
fi
AIRFLOW_URL="${AIRFLOW_URL%/}"
log "Airflow: $AIRFLOW_URL (DAG $DAG_ID)"

PASS="$(gcloud secrets versions access latest --secret=airflow-admin-password --project "$PROJECT_ID")"
[[ -n "$PASS" ]] || fallo "no se pudo leer el secreto airflow-admin-password"

# POST /auth/token (FAB auth manager): {"username","password"} → 201 {"access_token"}
TOKEN="$(printf '{"username": "%s", "password": "%s"}' "$AIRFLOW_USER" "$PASS" \
  | curl -sS --fail -X POST "$AIRFLOW_URL/auth/token" -H 'Content-Type: application/json' -d @- \
  | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
unset PASS
[[ -n "$TOKEN" ]] || fallo "no se obtuvo el JWT"
log "JWT obtenido"

api() {  # api METODO ruta [json]
  local metodo="$1" ruta="$2" datos="${3:-}"
  if [[ -n "$datos" ]]; then
    curl -sS --fail-with-body -X "$metodo" "$AIRFLOW_URL/api/v2$ruta" \
      -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "$datos"
  else
    curl -sS --fail-with-body -X "$metodo" "$AIRFLOW_URL/api/v2$ruta" -H "Authorization: Bearer $TOKEN"
  fi
}
campo() { "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(d.get(sys.argv[1], ""))' "$1"; }

# ---------------------------------------------------------------------------
# 2. Despausar el DAG si hace falta (PATCH /api/v2/dags/{dag_id} {"is_paused": false})
# ---------------------------------------------------------------------------
PAUSADO="$(api GET "/dags/$DAG_ID" | campo is_paused)"
if [[ "$PAUSADO" == "True" || "$PAUSADO" == "true" ]]; then
  api PATCH "/dags/$DAG_ID?update_mask=is_paused" '{"is_paused": false}' >/dev/null
  log "DAG despausado"
else
  log "DAG ya activo"
fi

# ---------------------------------------------------------------------------
# 3/5. Disparar una corrida y esperar su estado final
# ---------------------------------------------------------------------------
disparar_y_esperar() {  # disparar_y_esperar <dag_run_id>; deja DURACION_S y ESTADO
  local run_id="$1"
  # Cuerpo de POST /api/v2/dags/{dag_id}/dagRuns (TriggerDAGRunPostBody): `logical_date` es
  # obligatorio pero admite null (corrida manual sin fecha lógica, semántica de Airflow 3).
  local cuerpo
  cuerpo="$(printf '{"dag_run_id": "%s", "logical_date": null, "conf": %s, "note": "demo de idempotencia"}' "$run_id" "$DAG_CONF")"
  local resp; resp="$(api POST "/dags/$DAG_ID/dagRuns" "$cuerpo")"
  log "Corrida $run_id encolada (estado inicial: $(printf '%s' "$resp" | campo state))"

  local inicio; inicio=$(date +%s)
  local limite=$(( inicio + TIMEOUT_MIN * 60 ))
  while :; do
    local dr; dr="$(api GET "/dags/$DAG_ID/dagRuns/$run_id")"
    ESTADO="$(printf '%s' "$dr" | campo state)"
    local progreso
    progreso="$(api GET "/dags/$DAG_ID/dagRuns/$run_id/taskInstances?limit=100" | "$PY" -c "$PY_PROGRESO" 2>/dev/null || echo "?")"
    log "  $run_id: estado=$ESTADO · tareas: $progreso"
    case "$ESTADO" in
      success|failed) break ;;
    esac
    [[ $(date +%s) -lt $limite ]] || fallo "tiempo agotado (${TIMEOUT_MIN} min) esperando $run_id"
    sleep "$INTERVALO_S"
  done
  DURACION_S=$(( $(date +%s) - inicio ))
  log "Corrida $run_id terminó en estado $ESTADO tras ${DURACION_S}s"
  [[ "$ESTADO" == "success" ]] || fallo "la corrida $run_id no terminó en success; revisa la UI de Airflow"
  # El estado de la corrida no basta: todas las tareas (salvo registrar_fallo, que solo corre si algo falló) deben
  # estar en success. Así una tarea fallida con reintentos agotados nunca pasa como corrida válida.
  local no_verdes
  no_verdes="$(api GET "/dags/$DAG_ID/dagRuns/$run_id/taskInstances?limit=100" | "$PY" -c "$PY_NO_VERDES")"
  [[ -z "$no_verdes" ]] || fallo "la corrida $run_id tiene tareas no exitosas: $no_verdes"
  log "  las 17 tareas de la corrida $run_id están en success"
}

snapshot() {  # snapshot <base sin extensión>
  "$PY" ingest/conteos_capas.py --json --salida "$1.json" > /dev/null
  "$PY" ingest/conteos_capas.py --salida "$1.md" > /dev/null
  log "Instantánea guardada: $1.json / $1.md"
}

mkdir -p "$EVIDENCIA_DIR"
BASE="$EVIDENCIA_DIR/idempotencia_${TS}"
RUN1="demo-idempotencia-${TS}-1"
RUN2="demo-idempotencia-${TS}-2"

log "== Corrida 1 =="
disparar_y_esperar "$RUN1"; DUR1=$DURACION_S
snapshot "${BASE}_corrida1"

log "== Corrida 2 =="
disparar_y_esperar "$RUN2"; DUR2=$DURACION_S
snapshot "${BASE}_corrida2"

# ---------------------------------------------------------------------------
# 6. Comparar e informar
# ---------------------------------------------------------------------------
INFORME="${BASE}.md"
{
  echo "# Demo de idempotencia — DAG \`$DAG_ID\` ($TS)"
  echo
  echo "Dos corridas consecutivas disparadas por la REST API v2 de Airflow ($AIRFLOW_URL); después de cada una,"
  echo "\`ingest/conteos_capas.py\` toma el COUNT(*) de todas las tablas de bronze/staging/silver/quarantine/gold/features"
  echo "y el número de objetos y bytes en \`gs://\$LAKE_BUCKET/bronze/\`."
  echo
  echo "| corrida | dag_run_id | duración | instantánea |"
  echo "|---|---|---:|---|"
  echo "| 1 | \`$RUN1\` | ${DUR1}s | \`$(basename "${BASE}_corrida1.json")\` |"
  echo "| 2 | \`$RUN2\` | ${DUR2}s | \`$(basename "${BASE}_corrida2.json")\` |"
  echo
} > "$INFORME"
comparar "${BASE}_corrida1.json" "${BASE}_corrida2.json" "$INFORME" "corrida 1 ($RUN1)" "corrida 2 ($RUN2)"
