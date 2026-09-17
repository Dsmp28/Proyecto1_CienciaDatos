# Evidencia F0 — Infraestructura desplegada (2026-09-20)

## Terraform
| Módulo | Resultado |
|---|---|
| `infra/bootstrap` | `Apply complete! Resources: 14 added` (13 APIs + bucket `cienciadatos-509301-tfstate` versionado) |
| `infra/main` | `Apply complete! Resources: 49 added` + `2 added` (dataset `bronze`) |

Outputs de `infra/main`:
```
airflow_url              = "https://airflow.<IP_VM>.sslip.io"
lake_bucket              = "cienciadatos-509301-lake"
bigquery_datasets        = [bronze, features, gold, ops, ops_secrets, quarantine, silver, staging]
secret_names             = [airflow-admin-password, airflow-fernet-key, airflow-viewer-password, hmac-salt]
vm_service_account_email = "sa-pipeline-vm@cienciadatos-509301.iam.gserviceaccount.com"
ssh_command              = "gcloud compute ssh vm-pipeline --zone us-central1-a --tunnel-through-iap --project cienciadatos-509301"
```

## VM y pila Docker (`vm/startup.sh`, log `/var/log/startup-red-metropolitana.log`)
```
vm-airflow-api-server-1      Up (healthy)     vm-kafka-1      Up (healthy)
vm-airflow-scheduler-1       Up (healthy)     vm-postgres-1   Up (healthy)
vm-airflow-dag-processor-1   Up               vm-caddy-1      Up
vm-airflow-triggerer-1       Up
Mem: 7950 MiB total, 2089 usadas tras el arranque; swap 2 GB
```
Construcción de la imagen `red-metropolitana/airflow:3.3.2` (dbt-core 1.12.5, dbt-bigquery 1.12.1): ~4 min.

## HTTPS y autenticación
```
issuer=C=US, O=Let's Encrypt, CN=YE1   notBefore=Sep 21 03:07:16 2026 GMT  notAfter=Dec 20 03:07:15 2026 GMT
GET /api/v2/monitor/health -> {"metadatabase":healthy,"scheduler":healthy,"triggerer":healthy,"dag_processor":healthy}
GET /api/v2/version        -> {"version":"3.3.2"}
```
| Usuario | Rol | `POST /auth/token` | `GET /api/v2/dags` | `POST /api/v2/variables` (escritura) |
|---|---|---|---|---|
| admin | Admin | token OK | 200 | 201 (luego borrada) |
| catedratico | Viewer | token OK | 200 | **403** (solo lectura, como se exige) |

Kafka: sin puertos publicados al host; firewall solo 443 (y 22 desde el rango de IAP). Certificado obtenido con el desafío TLS-ALPN-01 por 443.

## Presupuesto
`google_billing_budget` de 60 USD/mes con umbrales 25/50/75/90/100 % (gasto real) y 100 % (proyección), alertas por correo. Facturación vinculada a la cuenta de prueba gratuita (300 USD).
