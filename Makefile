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

vm-stop: ## Apaga la VM (ahorra ~49 USD/mes de cómputo; disco e IP estática se siguen cobrando)
	gcloud compute instances stop $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID)

vm-status: ## Estado de la VM
	gcloud compute instances describe $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID) --format='value(status,networkInterfaces[0].accessConfigs[0].natIP)'

vm-ssh: ## SSH a la VM por túnel IAP (el puerto 22 no está abierto a internet)
	gcloud compute ssh $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID) --tunnel-through-iap --quiet

vm-sync: ## Copia el código del repo a la VM por IAP (sin datos, sin .venv, sin estado)
	COPYFILE_DISABLE=1 git ls-files -z | xargs -0 tar czf /tmp/red-metropolitana-src.tgz --no-xattrs
	gcloud compute scp /tmp/red-metropolitana-src.tgz $(VM_NAME):/tmp/ --zone $(ZONE) --project $(PROJECT_ID) --tunnel-through-iap --quiet
	gcloud compute ssh $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID) --tunnel-through-iap --quiet -- \
	  'sudo mkdir -p $(VM_DIR)/airflow/logs $(VM_DIR)/airflow/salidas $(VM_DIR)/datos_red && sudo tar xzf /tmp/red-metropolitana-src.tgz -C $(VM_DIR) --no-same-owner \
	   && sudo find $(VM_DIR) -name '._*' -delete && sudo chown -R 50000:0 $(VM_DIR)/airflow/logs $(VM_DIR)/airflow/salidas $(VM_DIR)/dbt $(VM_DIR)/datos_red && sudo chmod -R g+rwX $(VM_DIR)/airflow/logs $(VM_DIR)/airflow/salidas $(VM_DIR)/dbt $(VM_DIR)/datos_red \
	   && echo sincronizado'
	# Los directorios que escribe el contenedor (logs, dbt/target, datos_red) pertenecen al usuario airflow (uid 50000);
	# el resto queda de root y es legible por todos. Nunca chown -R al usuario de SSH: rompe los logs de las tareas.

vm-up: ## Reejecuta el script de arranque en la VM (instala Docker, levanta la pila)
	gcloud compute ssh $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID) --tunnel-through-iap --quiet -- 'sudo google_metadata_script_runner startup'

vm-logs: ## Logs del arranque y de los contenedores
	gcloud compute ssh $(VM_NAME) --zone $(ZONE) --project $(PROJECT_ID) --tunnel-through-iap --quiet -- \
	  'sudo tail -n 60 /var/log/startup-red-metropolitana.log; cd $(VM_DIR)/vm && sudo docker compose ps'

# ---------- dbt ----------
dbt-deps: ## Instala paquetes de dbt
	cd dbt && ../$(DBT) deps

dbt-build: ## dbt build completo (seeds, modelos, pruebas) por capas
	cd dbt && ../$(DBT) build --indirect-selection cautious --select tag:staging \
	  && ../$(DBT) build --indirect-selection cautious --select tag:silver tag:quarantine \
	  && ../$(DBT) build --indirect-selection cautious --select tag:gold \
	  && ../$(DBT) build --indirect-selection cautious --select tag:features --exclude tag:churn \
	  && ../$(DBT) build --indirect-selection cautious --select tag:churn

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

.PHONY: help venv bootstrap-plan bootstrap-apply init plan apply destroy outputs vm-start vm-stop vm-status vm-ssh vm-sync vm-up vm-logs dbt-deps dbt-build dbt-test dbt-docs test demo-idempotencia scan-secrets landing-subir reset reset-dry-run desde-cero evidencia-p2 ml-entrenar ml-dataset

# ---- Proyecto 2 ----
VERSION ?= v2
ORIGEN  ?= docs/P2_datos_red/datos_red

landing-subir: ## Sube los 9 archivos crudos v2 a gs://<lake>/landing/datos_red/<VERSION>/ y escribe el MANIFEST
	$(PY) -m ingest.landing subir --origen $(ORIGEN) --version $(VERSION)

reset: ## Borra Bronze, tablas de BigQuery y estado de la VM (exige CONFIRMAR=BORRAR-<proyecto>)
	$(PY) scripts/reset_p2.py --confirmar "$(CONFIRMAR)"

reset-dry-run: ## Lista lo que borraría el reset, sin borrar nada
	$(PY) scripts/reset_p2.py --dry-run

desde-cero: ## Reset + carga completa v2 por Airflow + evidencia en docs/evidence/p2 (exige CONFIRMAR=BORRAR-<proyecto>)
	CONFIRMAR="$(CONFIRMAR)" bash scripts/desde_cero.sh

evidencia-p2: ## Genera conteos, tiempos y capas de un run_id: make evidencia-p2 RUN_ID=desde-cero-...
	@test -n "$(RUN_ID)" || (echo "falta RUN_ID=<dag_run_id>" && exit 1)
	$(PY) ingest/evidencia_p2.py --run-id "$(RUN_ID)"

FASE ?= 1
ML_ORIGEN ?= bigquery

ml-entrenar: ## Entrena modelos del P2: make ml-entrenar FASE=1 [ML_ORIGEN=bigquery|csv] (csv exige RUTA_CSV=...)
	$(PY) -m ml.entrenar --fase $(FASE) --origen $(ML_ORIGEN) $(if $(RUTA_CSV),--ruta-csv $(RUTA_CSV),)

ml-dataset: ## Exporta features.churn_dataset a ml/artefactos/cache/churn_dataset.csv (sin la etiqueta de B)
	$(PY) -m ml.datos exportar

FECHA ?= 2026-08-30
SCRATCH ?= tmp
DBT_RECORTE = cd dbt && dbt run --target recorte --select tag:staging tag:silver tag:quarantine tag:churn

ml-exportar-features: ## Exporta las features (con tarjetas, sin etiqueta) de FECHA a predicciones/features_corte_<FECHA>.csv
	$(PY) -m ml.exportar --fecha-corte $(FECHA)

prueba-recorte: ## Prueba de recorte real: *_recorte (a), borrador ingenuo en dev (b), fallos del ingenuo (c) y churn_features corregida (d)
	cd dbt && dbt seed --target recorte
	$(DBT_RECORTE) tag:auditoria_recorte --vars '{"recorte_datos_hasta": "2026-06-30", "fechas_corte": ["2026-07-01"]}' && \
	  dbt test --target recorte --select tag:churn --vars '{"recorte_datos_hasta": "2026-06-30", "fechas_corte": ["2026-07-01"]}'
	cd dbt && dbt run --target dev --select tag:auditoria_recorte
	-$(PY) -m ml.prueba_recorte --corte A --fecha-corte 2026-07-01 --tabla churn_features_ingenuo --etiqueta-informe "borrador ingenuo" \
	  --informe docs/evidence/p2/prueba_recorte_ingenuo.md --salida-fallos tmp/prueba_recorte_fallos_detectados.json
	$(PY) -m ml.prueba_recorte --corte A --fecha-corte 2026-07-01 --informe docs/evidence/p2/prueba_recorte.md \
	  --fallos-previos docs/evidence/p2/prueba_recorte_fallos.json

ensayo-invariancia: ## Predice el corte B con datos recortados a < 2026-07-31 y completos; las predicciones deben coincidir
	$(DBT_RECORTE) --vars '{"recorte_datos_hasta": "2026-07-30", "fechas_corte": ["2026-07-31"]}' && \
	  dbt test --target recorte --select tag:churn --vars '{"recorte_datos_hasta": "2026-07-30", "fechas_corte": ["2026-07-31"]}'
	mkdir -p $(SCRATCH)
	$(PY) predecir.py --datos $(ORIGEN) --fecha-corte 2026-07-31 --sufijo-dataset _recorte --salida $(SCRATCH)/pred_B_recorte.csv --sin-verificar
	$(PY) predecir.py --datos $(ORIGEN) --fecha-corte 2026-07-31 --salida $(SCRATCH)/pred_B_completo.csv
	$(PY) -m ml.invariancia --referencia $(SCRATCH)/pred_B_completo.csv --nueva $(SCRATCH)/pred_B_recorte.csv --informe docs/evidence/p2/invariancia_B.md

.PHONY: ml-exportar-features prueba-recorte ensayo-invariancia

ml-test-b: ## Evaluación ÚNICA del modelo ACTUAL en el corte B (árbol limpio; aborta si ya se hizo: --forzar "justificación")
	$(PY) -m ml.evaluar_b --modelo ACTUAL $(if $(FORZAR),--forzar "$(FORZAR)",)

ml-segmentos: ## Segmenta las personas de A (KMeans, PCA, medianas, acciones): make ml-segmentos [ML_ORIGEN=bigquery|csv] [RUTA_CSV=...]
	$(PY) -m ml.segmentos --origen $(ML_ORIGEN) $(if $(RUTA_CSV),--ruta-csv $(RUTA_CSV),)

.PHONY: ml-test-b ml-segmentos
