# Seguridad y manejo de datos personales

Entregable 3.3: las cuatro decisiones y su justificación. Los datos son generados, pero el escenario no: un
sistema de transporte sabe dónde estuvo cada persona, a qué hora, todos los días.

## 1. Credenciales: nada en el repositorio
- **Autenticación sin llaves.** En la laptop, Application Default Credentials del usuario (`gcloud auth application-default login`).
  En la VM, la cuenta de servicio adjunta `sa-pipeline-vm` emite tokens por el servidor de metadata. No existe ninguna
  llave JSON de cuenta de servicio, ni en el repo ni en la VM (`infra/main/iam.tf`).
- **Mínimo privilegio.** `sa-pipeline-vm` tiene `objectAdmin` solo en el bucket del lake, `dataEditor` por dataset,
  `secretAccessor` por secreto y `jobUser` en el proyecto. Sin roles primitivos.
- **Secretos en Secret Manager** (`airflow-admin-password`, `airflow-viewer-password`, `airflow-fernet-key`, `hmac-salt`),
  generados por Terraform y leídos por `vm/startup.sh` en el arranque. El repo solo contiene `.env.example`; `.gitignore`
  excluye `.env`, `*.tfvars`, `*.tfstate*`, `dbt/profiles.yml`, `datos_red/`. El estado de Terraform (que contiene los
  valores generados) vive en un bucket privado y versionado con acceso público bloqueado.
- **Verificación:** `make scan-secrets` (gitleaks sobre todo el historial) antes de la entrega; reporte en `docs/evidence/`.

## 2. Seudonimización de la llave de usuario antes de Gold
- **HMAC-SHA256 con sal secreta** (ADR-007): `usuario_sk = HMAC(sal, modo || llave_nativa)`. Un hash simple sin sal es
  reversible por diccionario cuando la llave tiene formato conocido; el propio dataset lo demuestra: el "hash" de Aerómetro
  es `md5("am" + i)[:12]` y se invirtió al 100 % con 60 000 candidatos (ADR-008).
- La sal (32 bytes aleatorios) nunca sale de Secret Manager en texto de consulta: `ingest/hmac_key_to_bq.py` deriva los
  bloques internos de HMAC y los guarda en `ops_secrets.hmac_key`, un dataset al que solo accede la cuenta de servicio del
  pipeline; el macro `hmac_sha256()` de dbt los lee con una subconsulta. Verificado: BigQuery y Python producen el mismo digest.
- **Dónde vive cada cosa:** Bronze y Silver conservan la llave nativa (necesaria para auditoría y conciliación).
  Gold y Features solo contienen `usuario_sk` / `usuario_unificado_sk`. El tablero sabe que dos viajes son de la misma
  persona, no de qué tarjeta.
- **Rotación:** cambiar la sal exige reconstruir Gold y Features (los seudónimos cambian); se documenta como ADR cuando ocurra.

## 3. Quién ve qué (implementado con IAM por dataset)
| Rol | Necesidad | Datasets visibles | Cómo |
|---|---|---|---|
| Analista / Tableau | Agregados por modo, zona, hora; transbordo; cobertura | `gold` | `roles/bigquery.dataViewer` solo en `gold` (`tableau_user_email` en Terraform) + `jobUser` |
| Científico de datos | Features por usuario seudonimizado | `features` (y `gold`) | dataViewer en `features` |
| Auditor de fraude | Detalle por individuo con llave nativa | `silver`, `quarantine` | dataViewer en `silver` (`auditor_email` en Terraform); nunca en `gold` hace falta |
| Ingeniería de datos (pipeline) | Todo | todos | `sa-pipeline-vm` dataEditor por dataset |
| Catedrático (revisión) | Ver corridas del DAG | UI de Airflow | usuario `catedratico`, rol Viewer (verificado: 403 al escribir) |
| Nadie más | — | `ops_secrets` | solo la SA del pipeline y el propietario del proyecto |

Regla: **el detalle por individuo (Silver) no se comparte con analistas**; ven Gold, donde la persona es un seudónimo.
El tráfico a Airflow va por HTTPS (Caddy + Let's Encrypt); Kafka y Postgres no tienen puertos públicos; SSH solo por IAP.

## 4. Retención
- **Detalle individual (Bronze y Silver): 24 meses** desde la fecha del evento. Es el horizonte que necesitan las features
  (90 días) y la estacionalidad anual con un año de comparación; más allá, el riesgo de reidentificación no se justifica.
  Implementación prevista: regla de ciclo de vida en el bucket (`lake_bronze_nearline_days` → Nearline a los 90 días,
  borrado a los 730) y `partition_expiration_days = 730` en las tablas particionadas de Silver.
- **Agregados (Gold): indefinido**, porque ya no identifican personas.
- **Cuarentena: 12 meses**, tiempo suficiente para que el operador corrija la fuente y se reprocese.
- **Padrón SCD2: mientras la tarjeta esté activa más 24 meses** tras la baja, para conservar el historial de sus viajes
  (exigencia del enunciado de no borrar tarjetas dadas de baja).
