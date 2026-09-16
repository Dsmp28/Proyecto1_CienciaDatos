# Proyecto 1 · Agencia Metropolitana de Transporte
# Uso: make <objetivo>. Ver `make help`.

SHELL := /bin/bash
.DEFAULT_GOAL := help

PROJECT_ID ?= cienciadatos-509301
REGION     ?= us-central1
ZONE       ?= us-central1-a
VM_NAME    ?= vm-pipeline
VENV       := .venv
PY         := $(VENV)/bin/python
DBT        := $(VENV)/bin/dbt
TF_MAIN    := infra/main
TF_BOOT    := infra/bootstrap
VM_DIR     := /opt/red-metropolitana

help: ## Lista los objetivos disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------- Entorno local ----------
venv: ## Crea .venv (Python 3.12) con dbt-bigquery y librerías de ingesta
	uv venv --python 3.12 $(VENV)
	uv pip install --python $(PY) -r requirements.txt
	$(DBT) --version

# ---------- Terraform ----------
bootstrap-plan: ## terraform plan del bootstrap (bucket de estado + APIs)
	cd $(TF_BOOT) && terraform init -input=false && terraform plan -input=false

bootstrap-apply: ## terraform apply del bootstrap (pide confirmación)
	cd $(TF_BOOT) && terraform apply -input=false

init: ## terraform init de infra/main (backend en GCS)
	cd $(TF_MAIN) && terraform init -input=false

plan: ## terraform plan de infra/main
	cd $(TF_MAIN) && terraform plan -input=false -out=tfplan && terraform show -no-color tfplan | tail -n 40

apply: ## terraform apply del plan guardado (solo con OK explícito)
	cd $(TF_MAIN) && terraform apply -input=false tfplan

destroy: ## Destruye toda la infraestructura de infra/main (pide confirmación)
	cd $(TF_MAIN) && terraform destroy -input=false

outputs: ## Muestra los outputs de Terraform (IP, URL de Airflow, bucket)
	cd $(TF_MAIN) && terraform output

# ---------- VM ----------
vm-start: ## Enciende la VM
	gcloud compute instances start $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID)

vm-stop: ## Apaga la VM (ahorra ~33 USD/mes; la IP estática se sigue cobrando)
	gcloud compute instances stop $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID)

vm-status: ## Estado de la VM
	gcloud compute instances describe $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID) --format='value(status,networkInterfaces[0].accessConfigs[0].natIP)'

vm-ssh: ## SSH a la VM por túnel IAP (el puerto 22 no está abierto a internet)
	gcloud compute ssh $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID) --tunnel-through-iap --quiet

vm-sync: ## Copia el código del repo a la VM por IAP (sin datos, sin .venv, sin estado)
	git ls-files -z | xargs -0 tar czf /tmp/red-metropolitana-src.tgz
	gcloud compute scp /tmp/red-metropolitana-src.tgz $(VM_NAME):/tmp/ --zone $(ZONE) --project $(PROJECT_ID) --tunnel-through-iap --quiet
	gcloud compute ssh $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID) --tunnel-through-iap --quiet -- \
	  'sudo mkdir -p $(VM_DIR) && sudo tar xzf /tmp/red-metropolitana-src.tgz -C $(VM_DIR) && sudo chown -R $$(id -u):$$(id -g) $(VM_DIR) && echo sincronizado'

vm-up: ## Reejecuta el script de arranque en la VM (instala Docker, levanta la pila)
	gcloud compute ssh $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID) --tunnel-through-iap --quiet -- 'sudo google_metadata_script_runner startup'

vm-logs: ## Logs del arranque y de los contenedores
	gcloud compute ssh $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID) --tunnel-through-iap --quiet -- \
	  'sudo tail -n 60 /var/log/startup-red-metropolitana.log; cd $(VM_DIR)/vm && sudo docker compose ps'

# ---------- dbt ----------
dbt-deps: ## Instala paquetes de dbt
	cd dbt && ../$(DBT) deps

dbt-build: ## dbt build completo (seeds, modelos, pruebas) por capas
	cd dbt && ../$(DBT) build --select tag:staging && ../$(DBT) build --select tag:silver tag:quarantine \
	  && ../$(DBT) build --select tag:gold && ../$(DBT) build --select tag:features

dbt-test: ## Solo pruebas de dbt
	cd dbt && ../$(DBT) test

dbt-docs: ## Genera dbt docs (grafo de linaje) en dbt/target
	cd dbt && ../$(DBT) docs generate

test: ## Pruebas de Python (linaje de Gold, sin CURRENT_DATE, idempotencia)
	$(VENV)/bin/pytest -q tests

# ---------- Demostraciones ----------
demo-idempotencia: ## Corre el flujo dos veces, compara conteos por capa y falla si difieren
	bash scripts/demo_idempotencia.sh

scan-secrets: ## Escanea el historial de git en busca de secretos
	bash scripts/scan_secrets.sh

.PHONY: help venv bootstrap-plan bootstrap-apply init plan apply destroy outputs vm-start vm-stop vm-status vm-ssh vm-sync vm-up vm-logs dbt-deps dbt-build dbt-test dbt-docs test demo-idempotencia scan-secrets
