# Infraestructura (Terraform) — Pipeline Red Metropolitana

Infraestructura en GCP del proyecto, escrita en Terraform. Proyecto `cienciadatos-509301`,
región `us-central1`, zona `us-central1-a`. Objetivo de costo: **< 60 USD/mes** sobre una
cuenta de prueba de 300 USD.

```
infra/
  bootstrap/   # 1) estado LOCAL: habilita APIs y crea el bucket de estado (una sola vez)
  main/        # 2) estado REMOTO (GCS): red, VM, lake, BigQuery, secretos, IAM, presupuesto
```

## Qué se crea

| Archivo (main/) | Recursos |
|---|---|
| `network.tf` | VPC `vpc-pipeline`, subred `10.10.0.0/24`, firewall: 443 público, 22 solo desde IAP (`35.235.240.0/20`), deny explícito del resto, egress permitido. **Kafka no se expone.** |
| `vm.tf` | VM `vm-pipeline` (`e2-standard-2`, `pd-balanced` 30 GB, Debian 12), IP externa estática, Shielded VM, OS Login, metadata para `vm/startup.sh`. |
| `storage.tf` | Bucket del lake `<project_id>-lake` (acceso uniforme, nunca público, `force_destroy`), carpeta lógica `bronze/`. |
| `bigquery.tf` | Datasets `staging`, `silver`, `quarantine`, `gold`, `features`, `ops`, `ops_secrets` en `us-central1`. |
| `secrets.tf` | Secretos `airflow-admin-password`, `airflow-viewer-password`, `airflow-fernet-key`, `hmac-salt` con su versión 1 generada. |
| `iam.tf` | SA `sa-pipeline-vm` y bindings de mínimo privilegio; accesos opcionales para Tableau y auditor. |
| `budget.tf` | Presupuesto de 60 USD/mes con alertas al 25/50/75/90/100 % (+ 100 % pronosticado) por correo. |

## Requisitos

- Terraform >= 1.9 (probado con v1.15.8). Proveedor `hashicorp/google ~> 8.3`, `hashicorp/random ~> 3.6`.
- `gcloud` instalado y autenticado **con tu usuario** (nunca con llaves JSON):

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project cienciadatos-509301
```

- Tu usuario debe ser propietario del proyecto. Para el presupuesto necesitas además
  `roles/billing.costsManager` (o Billing Account Administrator) en la cuenta de facturación;
  si no lo tienes, usa `create_budget = false`.

## Uso

### 1. Bootstrap (una sola vez)

Crea el bucket de estado `cienciadatos-509301-tfstate` (versionado, privado, `prevent_destroy`)
y habilita las APIs. Usa estado local (`bootstrap/terraform.tfstate`, ignorado por git).

```bash
cd infra/bootstrap
cp terraform.tfvars.example terraform.tfvars   # ajusta project_id si cambia
terraform init
terraform plan
terraform apply
terraform output state_bucket                  # → cienciadatos-509301-tfstate
```

> El bloque `backend "gcs"` de `main/backend.tf` **no admite variables**: el nombre del bucket va
> escrito a mano y debe coincidir con `state_bucket` (`<project_id>-tfstate`). Si cambias el
> `project_id`, edita también `main/backend.tf`.

### 2. Main

```bash
cd infra/main
cp terraform.tfvars.example terraform.tfvars   # completa alert_email, billing_account_id, etc.
terraform init                                 # conecta con el bucket de estado
terraform plan
terraform apply                                # solo con el visto bueno del usuario
terraform output                               # IP, URL de Airflow, comando SSH, nombres de secretos
```

Desde la raíz del repo también existen `make plan`, `make apply`, `make vm-start`, `make vm-stop` y
`make destroy` (ver `CLAUDE.md`).

### Verificación sin crear recursos

```bash
terraform fmt -recursive
(cd bootstrap && terraform init -backend=false && terraform validate)
(cd main      && terraform init -backend=false && terraform validate)
```

### Entrar a la VM

El puerto 22 solo acepta tráfico del rango de IAP; se entra por túnel (OS Login, sin llaves en metadata):

```bash
gcloud compute ssh vm-pipeline --zone us-central1-a --tunnel-through-iap --project cienciadatos-509301
```

### Leer un secreto (solo cuando haga falta)

```bash
gcloud secrets versions access latest --secret airflow-admin-password --project cienciadatos-509301
```

En la VM, `vm/startup.sh` lee los nombres de los secretos desde la metadata de instancia y los
resuelve con la cuenta de servicio adjunta:

```bash
curl -sH "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/lake-bucket
```

Claves disponibles: `project-id`, `region`, `zone`, `lake-bucket`, `airflow-host`,
`secret-airflow-admin-password`, `secret-airflow-viewer-password`, `secret-airflow-fernet-key`,
`secret-hmac-salt`, `secret-names`, `enable-oslogin`.

> Si `vm/startup.sh` aún no existe, la VM se crea sin script de arranque (la expresión usa
> `fileexists()` para que `terraform validate` funcione). Al crear o cambiar el script, Terraform
> **recrea** la VM (comportamiento de `metadata_startup_script`).

## Variables de `main/`

| Variable | Default | Descripción |
|---|---|---|
| `project_id` | — | ID del proyecto de GCP. |
| `region` / `zone` | `us-central1` / `us-central1-a` | Región y zona. |
| `billing_account_id` | — | `XXXXXX-XXXXXX-XXXXXX`, sin prefijo `billingAccounts/`. |
| `alert_email` | — | Correo para alertas del presupuesto. |
| `create_budget` | `true` | Crear el presupuesto (requiere rol en la cuenta de facturación). |
| `budget_amount_usd` | `60` | Monto mensual. |
| `machine_type` | `e2-standard-2` | Tipo de VM. |
| `disk_size_gb` | `30` | Disco de arranque (pd-balanced). |
| `vm_image` | `debian-cloud/debian-12` | Alternativa: `ubuntu-os-cloud/ubuntu-2404-lts-amd64`. |
| `tableau_user_email` | `""` | Usuario OAuth de Tableau: `dataViewer` solo en `gold` + `jobUser`. |
| `auditor_email` | `""` | Auditor de fraude: `dataViewer` en `silver`. |
| `labels` | `{proyecto, curso}` | Etiquetas para todos los recursos (útiles para filtrar costos). |
| `lake_bronze_nearline_days` | `0` | Mover `bronze/` a NEARLINE tras N días (0 = no). |

## Modelo de permisos (mínimo privilegio, sin roles primitivos)

| Principal | Permisos |
|---|---|
| `sa-pipeline-vm` (adjunta a la VM, scope `cloud-platform`) | `storage.objectAdmin` **solo en el bucket del lake**; `bigquery.jobUser` en el proyecto; `bigquery.dataEditor` en **cada dataset**; `secretmanager.secretAccessor` **por secreto**; `logging.logWriter`; `monitoring.metricWriter`. |
| `tableau_user_email` (opcional) | `bigquery.dataViewer` solo en `gold`, `bigquery.jobUser` en el proyecto. |
| `auditor_email` (opcional) | `bigquery.dataViewer` solo en `silver` (ve la llave nativa). |
| `ops_secrets` | Solo `sa-pipeline-vm` (dataEditor) y el propietario del proyecto. |

No existe ninguna llave JSON: la VM usa el metadata server y las personas usan ADC/OAuth.

## Seguridad y estado

- **El estado de Terraform contiene secretos.** Las contraseñas de Airflow, la Fernet key y la sal
  HMAC se generan con `random_password`/`random_bytes` y se guardan como versión 1 de cada secreto;
  esos valores quedan en texto claro en el estado. Por eso el bucket de estado es privado, con
  acceso uniforme, prevención de acceso público, versionado y `prevent_destroy`. No compartas el
  bucket ni copies el estado.
- Terraform crea los **contenedores** de los secretos; no se escriben valores a mano en el repo.
- Firewall: solo 443 a internet; 22 solo desde IAP; Kafka nunca expuesto.
- OS Login activado y llaves SSH de proyecto bloqueadas.
- Buckets con `public_access_prevention = "enforced"`.

## Costos estimados (us-central1, precios de lista, sin créditos)

| Recurso | Estimación mensual |
|---|---|
| VM `e2-standard-2` encendida 24/7 | ~49 USD (0 si está apagada) |
| VM ~8 h/día | ~16 USD |
| Disco `pd-balanced` 30 GB | ~3.00 USD (se cobra aunque la VM esté apagada) |
| IP externa estática | ~3.65 USD asignada a VM encendida; ~7.30 USD si la VM está apagada |
| Egress (nivel STANDARD) | < 0.10 USD |
| Bucket del lake (~200 MB) + bucket de estado | < 0.05 USD |
| BigQuery (10 GB y 1 TB de consultas gratis al mes) | ~0 USD |
| Secret Manager (4 versiones × 1 réplica) | 0.24 USD |
| VPC, firewall, IAM, IAP, presupuesto, Monitoring | 0 USD |
| **Total 24/7** | **~56 USD** |
| **Total con la VM apagada fuera de horario** | **~20–25 USD** |

El presupuesto excluye créditos (`EXCLUDE_ALL_CREDITS`) para medir el consumo real aunque la cuenta
de prueba lo cubra. Apagar la VM cuando no se usa es la palanca de ahorro principal.

## Destruir

```bash
cd infra/main && terraform destroy       # borra VM, lake (force_destroy), datasets, secretos, presupuesto
```

El bucket de estado tiene `prevent_destroy`; para eliminarlo hay que quitar esa línea a mano en
`bootstrap/main.tf` (consciente de que se pierde el historial de estado).
