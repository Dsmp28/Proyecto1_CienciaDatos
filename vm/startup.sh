#!/usr/bin/env bash
# =============================================================================
# Script de arranque de la VM (metadata_startup_script de Terraform).
# Debian 12, se ejecuta como root en CADA arranque; todo es idempotente.
#
# 1. Instala Docker Engine + Compose plugin (repo oficial de Docker) y utilidades.
# 2. Lee metadata de instancia: project-id, region, lake-bucket, airflow-host.
# 3. Obtiene secretos de Secret Manager con la cuenta de servicio de la VM.
# 4. Usa el repo en /opt/red-metropolitana (llega por `make vm-sync`).
# 5. Genera vm/.env desde vm/.env.template (la sal HMAC NO se escribe).
# 6. Crea un swapfile de 2 GB.
# 7. `docker compose up -d --build` con TZ=America/Guatemala.
# 8. Registra todo en /var/log/startup-red-metropolitana.log.
# =============================================================================
set -Eeuo pipefail

LOG=/var/log/startup-red-metropolitana.log
REPO_DIR=/opt/red-metropolitana
VM_DIR="${REPO_DIR}/vm"
STATE_DIR=/etc/red-metropolitana        # secretos internos generados una sola vez
SWAPFILE=/swapfile
SWAP_SIZE_GB=2
export TZ=America/Guatemala
export DEBIAN_FRONTEND=noninteractive

exec > >(tee -a "${LOG}") 2>&1
log() { printf '%s [startup] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*"; }
trap 'log "ERROR en la línea ${LINENO} (código $?). Revisa ${LOG}."' ERR

log "===== Inicio del arranque de la VM Red Metropolitana ====="

# -----------------------------------------------------------------------------
# 1. Docker Engine + Compose plugin (https://docs.docker.com/engine/install/debian/)
# -----------------------------------------------------------------------------
instalar_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker $(docker --version | awk '{print $3}') y $(docker compose version --short) ya instalados."
    return
  fi
  log "Instalando Docker Engine y el plugin de Compose desde el repositorio oficial..."
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  # Formato deb822 (docker.sources), tal como lo documenta Docker para Debian.
  tee /etc/apt/sources.list.d/docker.sources >/dev/null <<SRC
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "${VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
SRC
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  log "Docker instalado: $(docker --version)"
}

instalar_utilidades() {
  local faltan=()
  for p in git make python3 jq curl rsync; do
    dpkg -s "$p" >/dev/null 2>&1 || faltan+=("$p")
  done
  if ((${#faltan[@]})); then
    log "Instalando utilidades: ${faltan[*]}"
    apt-get update -qq
    apt-get install -y -qq "${faltan[@]}"
  else
    log "Utilidades (git, make, python3, jq, curl, rsync) ya presentes."
  fi
}

instalar_docker
instalar_utilidades

# -----------------------------------------------------------------------------
# 2. Metadata de instancia (servidor de metadata de GCE)
# -----------------------------------------------------------------------------
MD_BASE="http://metadata.google.internal/computeMetadata/v1"
md_attr() { curl -sf -H "Metadata-Flavor: Google" "${MD_BASE}/instance/attributes/$1"; }
md_path() { curl -sf -H "Metadata-Flavor: Google" "${MD_BASE}/$1"; }

GCP_PROJECT_ID="$(md_attr project-id || md_path project/project-id)"
GCP_REGION="$(md_attr region || true)"
LAKE_BUCKET="$(md_attr lake-bucket || true)"
AIRFLOW_HOST="$(md_attr airflow-host || true)"
ACME_EMAIL="$(md_attr acme-email || true)"   # opcional; Let's Encrypt no lo verifica

for v in GCP_PROJECT_ID GCP_REGION LAKE_BUCKET AIRFLOW_HOST; do
  if [[ -z "${!v}" ]]; then
    log "ERROR: falta la metadata para ${v}. Terraform debe pasar project-id, region, lake-bucket y airflow-host."
    exit 1
  fi
done
[[ -n "${ACME_EMAIL}" ]] || ACME_EMAIL="admin@${AIRFLOW_HOST}"
log "Metadata: proyecto=${GCP_PROJECT_ID} region=${GCP_REGION} bucket=${LAKE_BUCKET} host=${AIRFLOW_HOST}"

# -----------------------------------------------------------------------------
# 3. Secretos (Secret Manager) con la cuenta de servicio de la VM (ADC, sin llaves JSON)
#    Preferimos gcloud (viene en las imágenes de GCE); si no está, usamos la API REST
#    con el token del servidor de metadata.
# -----------------------------------------------------------------------------
leer_secreto() {
  local nombre="$1"
  if command -v gcloud >/dev/null 2>&1; then
    gcloud secrets versions access latest --secret="${nombre}" --project="${GCP_PROJECT_ID}"
  else
    local token
    token="$(md_path instance/service-accounts/default/token | jq -r .access_token)"
    curl -sf -H "Authorization: Bearer ${token}" \
      "https://secretmanager.googleapis.com/v1/projects/${GCP_PROJECT_ID}/secrets/${nombre}/versions/latest:access" \
      | jq -r .payload.data | base64 -d
  fi
}

log "Leyendo secretos de Secret Manager (airflow-admin-password, airflow-viewer-password, airflow-fernet-key)..."
AIRFLOW_ADMIN_PASSWORD="$(leer_secreto airflow-admin-password)"
AIRFLOW_VIEWER_PASSWORD="$(leer_secreto airflow-viewer-password)"
AIRFLOW_FERNET_KEY="$(leer_secreto airflow-fernet-key)"
# hmac-salt NO se lee aquí: el DAG la obtiene de Secret Manager en tiempo de ejecución.
for v in AIRFLOW_ADMIN_PASSWORD AIRFLOW_VIEWER_PASSWORD AIRFLOW_FERNET_KEY; do
  [[ -n "${!v}" ]] || { log "ERROR: el secreto para ${v} está vacío."; exit 1; }
done
log "Secretos leídos (valores no registrados)."

# Secretos internos de Airflow 3 (JWT entre componentes y secret_key del api-server):
# se generan una vez y se persisten en ${STATE_DIR} para sobrevivir reinicios.
install -d -m 0700 "${STATE_DIR}"
generar_si_falta() {
  local archivo="${STATE_DIR}/$1"
  if [[ ! -s "${archivo}" ]]; then
    (umask 077; openssl rand -hex 32 > "${archivo}")
    log "Generado ${archivo}"
  fi
  cat "${archivo}"
}
AIRFLOW_JWT_SECRET="$(generar_si_falta airflow_jwt_secret)"
AIRFLOW_API_SECRET_KEY="$(generar_si_falta airflow_api_secret_key)"

# -----------------------------------------------------------------------------
# 4. Código del proyecto: llega por `make vm-sync` (gcloud compute scp por IAP)
#    porque el repo aún no tiene remoto. Sin código no hay nada que levantar.
# -----------------------------------------------------------------------------
install -d -m 0755 "${REPO_DIR}"
if [[ ! -f "${VM_DIR}/docker-compose.yml" ]]; then
  log "AVISO: no existe ${VM_DIR}/docker-compose.yml."
  log "       Sincroniza el repositorio desde tu laptop con:  make vm-sync"
  log "       y luego vuelve a ejecutar este script:  sudo google_metadata_script_runner startup"
  log "       (o directamente: sudo bash ${VM_DIR}/startup.sh)."
  log "===== Arranque terminado sin levantar contenedores ====="
  exit 0
fi
log "Repositorio encontrado en ${REPO_DIR}."

# -----------------------------------------------------------------------------
# 5. vm/.env desde vm/.env.template (permisos 600, solo root; nunca al repo)
# -----------------------------------------------------------------------------
if [[ ! -f "${VM_DIR}/.env.template" ]]; then
  log "ERROR: falta ${VM_DIR}/.env.template"; exit 1
fi
log "Generando ${VM_DIR}/.env"
(
  umask 077
  # python3 sustituye los marcadores y entrecomilla los valores ('...') para que Compose
  # no interprete $, # ni comillas dentro de contraseñas o claves.
  GCP_PROJECT_ID="${GCP_PROJECT_ID}" GCP_REGION="${GCP_REGION}" LAKE_BUCKET="${LAKE_BUCKET}" \
  AIRFLOW_HOST="${AIRFLOW_HOST}" AIRFLOW_ADMIN_PASSWORD="${AIRFLOW_ADMIN_PASSWORD}" \
  AIRFLOW_VIEWER_PASSWORD="${AIRFLOW_VIEWER_PASSWORD}" AIRFLOW_FERNET_KEY="${AIRFLOW_FERNET_KEY}" \
  AIRFLOW_JWT_SECRET="${AIRFLOW_JWT_SECRET}" AIRFLOW_API_SECRET_KEY="${AIRFLOW_API_SECRET_KEY}" \
  ACME_EMAIL="${ACME_EMAIL}" \
  python3 - "${VM_DIR}/.env.template" "${VM_DIR}/.env" <<'PY'
import os, re, sys
plantilla, destino = sys.argv[1], sys.argv[2]
texto = open(plantilla, encoding="utf-8").read()
faltantes = []
def sustituir(m):
    clave = m.group(1)
    valor = os.environ.get(clave)
    if valor is None:
        faltantes.append(clave)
        return m.group(0)
    # Compose interpola $VAR y corta en " #" dentro de valores sin comillas del .env.
    # Entre comillas simples todo es literal salvo \' (comilla escapada); una barra
    # invertida podría romper el cierre, así que se rechaza (rotar el secreto).
    if "\\" in valor:
        sys.exit(f"El valor de {clave} contiene una barra invertida; genera el secreto sin '\\'.")
    if "\n" in valor or "\r" in valor:
        sys.exit(f"El valor de {clave} contiene saltos de línea.")
    return "'" + valor.replace("'", "\\'") + "'"
# Solo se sustituye en líneas de asignación; los comentarios se copian tal cual.
lineas = []
for linea in texto.splitlines(keepends=True):
    if linea.lstrip().startswith("#"):
        lineas.append(linea)
    else:
        lineas.append(re.sub(r"__([A-Z0-9_]+)__", sustituir, linea))
salida = "".join(lineas)
if faltantes:
    sys.exit(f"Marcadores sin valor en la plantilla: {', '.join(faltantes)}")
with open(destino, "w", encoding="utf-8") as f:
    f.write(salida)
PY
)
chmod 600 "${VM_DIR}/.env"
log ".env generado (${VM_DIR}/.env, 600 root)."

# Directorios que los contenedores montan; deben existir antes de `up` para que
# Docker no los cree como root con permisos inadecuados (airflow-init ajusta el dueño).
for d in airflow/dags airflow/logs airflow/plugins dbt ingest scripts tests datos_red; do
  install -d "${REPO_DIR}/${d}"
done

# -----------------------------------------------------------------------------
# 6. Swap de 2 GB (8 GB de RAM es justo para Airflow + Kafka + Postgres)
# -----------------------------------------------------------------------------
if [[ ! -f "${SWAPFILE}" ]]; then
  log "Creando swapfile de ${SWAP_SIZE_GB} GB en ${SWAPFILE}..."
  fallocate -l "${SWAP_SIZE_GB}G" "${SWAPFILE}" || dd if=/dev/zero of="${SWAPFILE}" bs=1M count=$((SWAP_SIZE_GB * 1024)) status=none
  chmod 600 "${SWAPFILE}"
  mkswap "${SWAPFILE}" >/dev/null
fi
if ! swapon --show=NAME --noheadings | grep -qx "${SWAPFILE}"; then
  swapon "${SWAPFILE}"
  log "Swap activado."
fi
grep -q "^${SWAPFILE} " /etc/fstab || echo "${SWAPFILE} none swap sw 0 0" >> /etc/fstab
# Preferir RAM; usar swap solo bajo presión real.
sysctl -q -w vm.swappiness=10
echo "vm.swappiness=10" > /etc/sysctl.d/90-red-metropolitana.conf
log "Swap: $(free -h | awk '/Swap:/ {print $2 " total, " $3 " en uso"}')"

# -----------------------------------------------------------------------------
# 7. Levantar la pila
# -----------------------------------------------------------------------------
log "Ejecutando docker compose up -d --build en ${VM_DIR} (la primera construcción tarda varios minutos)..."
cd "${VM_DIR}"
docker compose --env-file "${VM_DIR}/.env" up -d --build --remove-orphans
log "Estado de los servicios:"
docker compose --env-file "${VM_DIR}/.env" ps
# Imágenes intermedias de construcciones anteriores.
docker image prune -f >/dev/null 2>&1 || true

log "Airflow: https://${AIRFLOW_HOST}  (usuarios: admin y catedratico)"
log "===== Arranque completado ====="
