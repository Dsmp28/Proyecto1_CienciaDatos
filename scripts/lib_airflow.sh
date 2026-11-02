# Funciones compartidas para hablar con la REST API v2 de Airflow 3 (se usan con `source`).
# Esperan estas variables del script que las carga: REPO, PY, DAG_ID, PROJECT_ID, AIRFLOW_USER, AIRFLOW_URL.
# La contraseña de admin se lee de Secret Manager (airflow-admin-password) y nunca se imprime.

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

# Igual que PY_NO_VERDES pero tolera las tareas omitidas (skipped), p. ej. ramas de origen_datos no usadas.
PY_NO_VERDES_SALVO_SKIPPED=$(cat <<'PYEOF'
import json, sys
tis = json.load(sys.stdin).get("task_instances", [])
malas = [f"{t['task_id']}={t.get('state')}" for t in tis if t["task_id"] != "registrar_fallo" and t.get("state") not in ("success", "skipped")]
print(", ".join(malas))
PYEOF
)

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
fallo() { log "ERROR: $*" >&2; exit 1; }

# Obtiene AIRFLOW_URL (si está vacío), la contraseña de Secret Manager y el JWT (TOKEN).
airflow_login() {
  command -v gcloud >/dev/null || fallo "gcloud no está en el PATH"
  command -v curl >/dev/null || fallo "curl no está en el PATH"
  [[ -x "$PY" ]] || fallo "no existe $PY (ejecuta: make venv)"

  if [[ -z "$AIRFLOW_URL" ]]; then
    AIRFLOW_URL="$(cd "$REPO/infra/main" && terraform output -raw airflow_url 2>/dev/null || true)"
    [[ -n "$AIRFLOW_URL" ]] || fallo "AIRFLOW_URL vacío y no hay output de Terraform"
  fi
  AIRFLOW_URL="${AIRFLOW_URL%/}"
  log "Airflow: $AIRFLOW_URL (DAG $DAG_ID)"

  local PASS
  PASS="$(gcloud secrets versions access latest --secret=airflow-admin-password --project "$PROJECT_ID")"
  [[ -n "$PASS" ]] || fallo "no se pudo leer el secreto airflow-admin-password"

  # POST /auth/token (FAB auth manager): {"username","password"} → 201 {"access_token"}
  TOKEN="$(printf '{"username": "%s", "password": "%s"}' "$AIRFLOW_USER" "$PASS" \
    | curl -sS --fail -X POST "$AIRFLOW_URL/auth/token" -H 'Content-Type: application/json' -d @- \
    | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
  unset PASS
  [[ -n "$TOKEN" ]] || fallo "no se obtuvo el JWT"
  log "JWT obtenido"
}

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

# Despausar el DAG si hace falta (PATCH /api/v2/dags/{dag_id} {"is_paused": false})
airflow_despausar() {
  local pausado
  pausado="$(api GET "/dags/$DAG_ID" | campo is_paused)"
  if [[ "$pausado" == "True" || "$pausado" == "true" ]]; then
    api PATCH "/dags/$DAG_ID?update_mask=is_paused" '{"is_paused": false}' >/dev/null
    log "DAG despausado"
  else
    log "DAG ya activo"
  fi
}
