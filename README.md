# Agencia Metropolitana de Transporte — Proyecto 1 (URL, Ciencia de Datos)

Pipeline de datos de punta a punta que integra los cuatro operadores de transporte del área
metropolitana de Guatemala (Transmetro, Transurbano, MetroRiel y Aerómetro) en una arquitectura
Bronze → Staging/CDC → Silver (+ cuarentena) → Gold dimensional → Tableau y tabla de features.

| Capa | Dónde vive |
|---|---|
| Bronze (crudo, particionado por fecha de ingesta) | Cloud Storage `gs://cienciadatos-509301-lake/bronze/` |
| Staging, Silver, Cuarentena, Gold, Features, Ops | BigQuery (`us-central1`) |
| Streaming | Kafka 4.x (KRaft) en Docker, en una VM de Compute Engine |
| Transformación | dbt Core 1.12 + dbt-bigquery |
| Orquestación | Airflow 3.3 en Docker (misma VM), HTTPS con Caddy |
| Infraestructura | Terraform (`infra/`) |
| Visualización | Tableau Desktop → dataset `gold` |

Documentos clave: [plan](docs/PLAN.md) · [avance](docs/PROGRESS.md) · [decisiones (ADR)](docs/DECISIONS.md) ·
[grano y matriz del bus](docs/modelo/matriz_bus.md) · [métricas](docs/METRICAS.md) · [checklist de rúbrica](docs/RUBRICA_CHECKLIST.md).

## Requisitos
- macOS o Linux con `gcloud` (≥ 585), `terraform` (≥ 1.15), `docker` + `compose`, `uv` o Python 3.12, `make`, `git`.
- Proyecto de GCP con facturación habilitada y `gcloud auth login` + `gcloud auth application-default login`.
- Tableau Desktop (solo para el tablero).

## Instalación y ejecución desde cero
```bash
make venv                        # 1. entorno local con dbt
cp infra/bootstrap/terraform.tfvars.example infra/bootstrap/terraform.tfvars
cp infra/main/terraform.tfvars.example infra/main/terraform.tfvars
make bootstrap-plan && make bootstrap-apply   # 2. bucket de estado + APIs
make init && make plan && make apply          # 3. VM, red, buckets, datasets, secretos, presupuesto
make vm-sync && make vm-up                    # 4. copia el código a la VM y levanta Kafka + Airflow + Caddy
make outputs                                  # 5. URL de Airflow (https://airflow.<IP>.sslip.io)
```
El flujo completo se dispara desde Airflow (DAG `red_metropolitana`). La demostración de idempotencia:
```bash
make demo-idempotencia
```
Apagar la VM cuando no se use: `make vm-stop`. Destruir todo: `make destroy`.

*(README en construcción: se completa en la fase F7 con la guía detallada.)*
