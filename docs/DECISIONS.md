# Bitácora de decisiones (ADR)

Formato: contexto → decisión → alternativas descartadas → consecuencias. Este archivo es también el
entregable de 3.2 (decisiones de diseño). Las decisiones que dependen del generador real se marcan
*[verificar en generador]* y se revisan en F1.

---

## ADR-001 · Nube y sustituciones frente a la columna "Recomendada" del enunciado
**Contexto.** El enunciado recomienda carpetas + Parquet (lake), PostgreSQL/DuckDB (warehouse) y Prefect. Exige justificar cualquier sustitución. Se dispone de una cuenta de GCP con 300 USD de crédito y un objetivo de < 60 USD/mes.
**Decisión.** GCP con Cloud Storage (Bronze), BigQuery (staging, silver, cuarentena, gold, features, ops), Kafka y Airflow en una sola VM, dbt Core, Terraform para toda la infraestructura.
**Alternativas.** Todo local (DuckDB + carpetas): cero costo, pero sin demostrar despliegue en nube ni IAM real, y Tableau debería conectarse a un archivo. Cloud Composer y Kafka administrado: consumen el crédito en semanas. Redshift: no existe en GCP.
**Consecuencias.** Costo estimado 24–57 USD/mes según uso de la VM. BigQuery soporta JSON nativo, tiene adaptador oficial de dbt y conector nativo de Tableau; su nivel gratuito (1 TiB consulta, 10 GiB almacenamiento) cubre 200 MB con margen. Se fija `maximum_bytes_billed` en dbt.

## ADR-002 · Bronze en lake (GCS), no en el warehouse
**Contexto.** Uno de los archivos (`metroriel_viajes.jsonl`) es JSON anidado. Bronze debe conservar el dato tal como llegó, con marca de ingesta y partición por fecha.
**Decisión.** Bronze vive en `gs://<proyecto>-lake/bronze/<fuente>/ingest_date=YYYY-MM-DD/`. Los archivos batch se copian byte a byte; los eventos de Kafka se escriben como JSONL con la línea cruda más metadatos (tópico, partición, offset, `ingest_ts`). BigQuery los expone como tablas externas con particionado Hive, que dbt declara como `source`.
**Alternativas.** Cargar directo a tablas nativas de BigQuery: obligaría a tipar el JSON al entrar (deja de ser "tal como llegó") y mezcla almacenamiento crudo con cómputo.
**Consecuencias.** El dato crudo sobrevive aunque se recree el warehouse; el linaje llega hasta el objeto en GCS (columna `_FILE_NAME`). Costo de almacenamiento dentro del nivel gratuito.

## ADR-003 · Vía de ingesta de Transurbano: batch
**Contexto.** El enunciado deja Transurbano a criterio del equipo. Su archivo es un ledger de transacciones (montos en centavos, fecha y hora en columnas separadas) y la fuente de mayor volumen (270 000 pasajeros/día).
**Decisión.** Batch: el archivo entra por la misma vía que MetroRiel y los catálogos, con manifiesto por sha256.
**Alternativas.** Streaming (más "realista" para eventos de abordaje): duplicaría el trabajo de idempotencia sobre el archivo más grande y un broker de un nodo sería el cuello de botella.
**Consecuencias.** Latencia de un día para Transurbano (no hay tablero casi en tiempo real para ese modo). Idempotencia exacta por archivo. Reproceso trivial (recargar el archivo). Los duplicados se tratan en Silver con las mismas reglas que las fuentes de streaming.

## ADR-004 · Grano de la tabla de hechos principal: un abordaje
**Contexto.** MetroRiel entrega viajes completos (entrada y salida); los otros tres, abordajes sueltos. El enunciado advierte que el grano es la decisión más difícil.
**Decisión.** `fct_abordaje`: "una validación de una tarjeta de un usuario en un modo, en una estación o parada, en un instante". MetroRiel aporta su entrada como abordaje; el viaje completo se conserva en `fct_viaje_metroriel` (grano: un viaje cerrado).
**Alternativas.** "Viaje puerta a puerta": exige inferir el viaje para 3 de 4 sistemas con ventanas de tiempo y proximidad no verificables con datos generados; contaminaría el hecho atómico con supuestos.
**Consecuencias.** Hecho uniforme para los cuatro modos, al grano más atómico disponible (Kimball). MetroRiel no pierde información. La inferencia multimodal queda como extra opcional sin tocar el grano.

## ADR-005 · Orquestación con Airflow en vez de Prefect
**Contexto.** El enunciado recomienda Prefect; Airflow figura como alternativa ("estándar del mercado").
**Decisión.** Apache Airflow 3.3 en Docker Compose (LocalExecutor) en la misma VM que Kafka.
**Alternativas.** Prefect: arranca sin servidor, pero la UI compartible con roles exige Prefect Cloud o un servidor propio igual. Cloud Composer: > 300 USD/mes.
**Consecuencias.** Reintentos, bitácora y roles (usuario de solo lectura para el catedrático) nativos. Más memoria: se mitiga con LocalExecutor (sin Redis ni workers) en una e2-standard-2.

## ADR-006 · Idempotencia de Bronze y de las capas derivadas
**Contexto.** Dos corridas deben producir conteos idénticos en todas las capas; Bronze se acumula sin duplicarse; staging se vacía.
**Decisión.** (a) `ops.ingest_manifest` con sha256 por archivo: batch y productor de Kafka no reprocesan un archivo ya ingerido. (b) El consumidor escribe objetos con nombre determinista por tópico, partición y rango de offsets y confirma offsets solo después de escribir. (c) Staging, Silver, cuarentena y Gold se materializan como `table` (reconstrucción completa por corrida). (d) La fecha de referencia es una variable fija de dbt; prohibido `CURRENT_DATE`.
**Alternativas.** Modelos incrementales con `merge`: más eficientes, pero su idempotencia depende de llaves únicas por fuente; quedan como extra opcional.
**Consecuencias.** A 200 MB la reconstrucción completa tarda minutos y cuesta 0 dentro del nivel gratuito. La idempotencia se prueba con `make demo-idempotencia`.

## ADR-007 · Seudonimización con HMAC-SHA256 en BigQuery
**Contexto.** La llave de usuario debe seudonimizarse antes de Gold. Un hash sin sal es reversible por diccionario sobre llaves de formato conocido (`TC-00012345`). BigQuery no tiene función HMAC.
**Decisión.** HMAC-SHA256 en SQL puro: `SHA256(CONCAT(k_opad, SHA256(CONCAT(k_ipad, mensaje))))`. Airflow lee la sal de Secret Manager, deriva `k_ipad` y `k_opad` en Python y los escribe en `ops_secrets.hmac_key` (dataset con IAM restringido a la cuenta de servicio del pipeline). El macro de dbt los toma por subconsulta escalar, de modo que la sal nunca aparece en el texto de las consultas ni en el historial de jobs. Silver conserva la llave nativa (solo visible para el rol de auditoría).
**Alternativas.** `DETERMINISTIC_ENCRYPT` con keyset envuelto en Cloud KMS (más robusto; añade KMS y complejidad). JS UDF con la sal como argumento (la sal quedaría en el historial de jobs).
**Consecuencias.** Seudónimo estable entre corridas (idempotencia) mientras la sal no rote. Rotar la sal implica reconstruir Gold y features.

## ADR-008 · Estrategia de identidad del usuario (verificada en el generador el 2026-09-20)
**Contexto.** No existe tabla que relacione las cuatro tarjetas. El generador (`docs/generar_red_metropolitana.py`) crea 60 000 personas con un entero base `i` y emite, con probabilidad independiente por operador, `TC-{i:08d}` (Transmetro, 72 %), `{i:010d}` (Transurbano, 61 %), `MR{i:07d}` (MetroRiel, 38 %) y `md5("am"+i)[:12]` (Aerómetro, 24 %). Es decir, sí existe un identificador base compartido, y el "hash" de Aerómetro es un MD5 sin sal sobre un espacio de 60 000 valores.
**Decisión.**
1. Identidad base por (modo, llave nativa): `usuario_sk = HMAC-SHA256(sal, modo || llave)`. Se conserva siempre.
2. Vínculo entre modos por **identificador base**: `usuario_base_id = i`, extraído por formato (`TC-`, 10 dígitos, `MR`). Para Aerómetro se construye en Silver una tabla de correspondencia `hash_am → i` calculando `LEFT(TO_HEX(MD5(CONCAT('am', i))), 12)` para `i` en 1…N (ataque de diccionario sobre un hash sin sal). Verificado: 14 496 de 14 496 hashes observados se invierten. `usuario_unificado_sk = HMAC(sal, 'BASE' || i)`.
3. Supuesto declarado: "el mismo identificador base corresponde a la misma persona". En el mundo real equivaldría a que los cuatro operadores emitieran tarjetas contra un mismo registro (p. ej. DPI). Confianza `alta` para TM/TU/MR (relación estructural) y `alta` para AM (inversión exacta del esquema de hash), pero **el vínculo de AM es en sí una lección de seguridad**: un hash sin sal de una llave con formato conocido se revierte por diccionario; por eso la seudonimización de la Agencia usa HMAC con sal secreta (ADR-007).
4. Límite: fuera de este generador, sin un identificador base compartido el transbordo entre sistemas no sería medible; el diseño conserva `usuario_sk` por modo para que la Agencia pueda operar sin el vínculo.
**Resultado medido:** 56 848 usuarios base observados en operación; 41 485 (73 %) usan más de un sistema (2 sistemas: 25 048; 3: 14 004; 4: 2 433).
**Alternativas.** Coincidencia espacio-temporal de validaciones (inferencia, extra opcional). Ignorar el vínculo (perdería la pregunta de transbordo del enunciado).
**Consecuencias.** `dim_usuario` tiene grano tarjeta-por-modo y una columna `usuario_unificado_sk`; el transbordo se mide con `COUNT(DISTINCT modo)` por `usuario_unificado_sk`. Silver conserva la llave nativa y el `usuario_base_id` (solo auditoría).

## ADR-009 · De quién es el padrón de CDC y cómo se aplican operaciones fuera de orden
**Contexto.** `cdc_padron_usuarios.csv` (31 050 operaciones: 10 800 INSERT, 16 200 UPDATE, 4 050 DELETE) es, según el enunciado, el padrón de Transmetro. El generador introduce una ambigüedad deliberada: la columna `tarjeta` toma la primera tarjeta que la persona tenga entre TM, TU y MR (22 326 con formato TC-, 5 223 con formato Transurbano, 1 295 con formato MR y 2 206 `SIN-TARJETA`). Además el log no es "limpio": 14 617 tarjetas cuya primera operación no es INSERT, 827 con más de un INSERT (828 si se cuenta `SIN-TARJETA` como llave) y 3 301 DELETE sin INSERT previo.
**Decisión.** El padrón se trata como **registro central de personas de la Agencia** (no de un solo operador) identificado por `usuario_base_id`, porque su columna `tarjeta` mezcla formatos de tres operadores y sus atributos (`perfil`, `zona_residencia`) describen a la persona, no a la tarjeta. Reglas de aplicación en orden de `seq`:
- INSERT sobre llave existente → se aplica como UPDATE y se cuenta como "alta repetida".
- UPDATE sobre llave inexistente → se aplica como alta implícita (`alta_implicita = true`) y se cuenta aparte.
- DELETE (llega sin cuerpo) → marca `estado = INACTIVA` conservando los atributos previos; si no hay alta previa se crea la fila inactiva sin atributos y se cuenta como "baja sin alta previa".
- `SIN-TARJETA` → no hay llave: va a cuarentena con motivo `R07 llave nula`.
Se reportan altas, cambios, bajas, tarjetas activas antes y después de aplicar los DELETE, y los tres contadores de anomalías.
**Alternativas.** Tratarlo estrictamente como padrón de Transmetro y mandar a cuarentena las filas con formato TU/MR (perdería el 21 % del padrón por una decisión de nombre). Rechazar UPDATE/DELETE sin INSERT previo (perdería historia real que el log sí registra).
**Consecuencias.** Los atributos `perfil` y `zona_residencia` alimentan `dim_usuario` para cualquier modo mediante `usuario_base_id`, no solo para Transmetro. El SCD2 se construye con funciones de ventana sobre `seq`.

## ADR-010 · Parámetros fijados tras leer el generador
- `ESCALA` por defecto es 0.08 (≈ 137 MB reales, no 200), 45 días desde 2026-06-01, semilla 2026, 60 000 personas. La regeneración es determinista: los 9 archivos regenerados coinciden byte a byte (sha256) con los entregados, en 7 s.
- `fecha_referencia = 2026-07-16` (día siguiente a la última fecha legítima, 2026-07-15). Toda fecha local ≥ `fecha_referencia` es "del futuro" (Transurbano inyecta +400 días en ~0,1 % de filas: 817 observadas).
- Aerómetro: `timestamp_utc = hora local + 6 h`; se convierte con `DATETIME(ts, 'America/Guatemala')`.
- Transurbano `cod_estado` 7 (`SALDO_INSUF`) y 9 (`TARJETA_INVALIDA`) son transacciones **rechazadas por el sistema de cobro**: no son registros malos, son cobros fallidos. Se conservan en Silver con su estado y no cuentan como viaje (definición oficial); no van a cuarentena. Solo 1, 2 y 3 (`OK`) son abordajes.
- Anomalías inyectadas y verificadas: Transmetro duplica la fila completa (mismo `validacion_id`) en 1 115 casos; Transurbano deja `cod_parada` vacío en 4 189 filas; MetroRiel deja `exit = null` en 3 589 viajes; Aerómetro no tiene anomalías inyectadas más allá del UTC.
- Zonas en los datos: 12 zonas de la ciudad (1, 4, 6, 7, 8, 9, 10, 11, 12, 13, 17, 18) y 4 municipios (Mixco, Villa Nueva, San Miguel Petapa, Santa Catarina Pinula). Santa Catarina Pinula aparece solo como zona de residencia en el padrón: es la zona sin servicio de ningún modo. `dim_zona` incluirá además las zonas oficiales de la ciudad ausentes en los datos (2, 3, 5, 14, 15, 16, 19, 21, 24, 25) marcadas `presente_en_datos = false`, para que la pregunta de cobertura se responda contra la división territorial real y no solo contra lo que los operadores reportan.

## ADR-011 · Extra: `dbt test` en cada push con GitHub Actions y Workload Identity Federation
**Contexto.** El enunciado propone como extra "GitHub Actions que corra `dbt test` en cada push: el pipeline se valida solo". La restricción del proyecto prohíbe llaves JSON de cuentas de servicio, y el repositorio aún no tiene remoto.
**Decisión.** Workflow `.github/workflows/dbt_test.yml` con dos trabajos: (1) `pruebas-sin-nube`, siempre: `pytest` (linaje de Gold, `CURRENT_DATE`, ingesta, DAG), `dbt parse`, `terraform fmt/validate`, sintaxis de scripts y del compose; (2) `dbt-test`, solo cuando el repositorio tiene las variables `GCP_WIF_PROVIDER` y `GCP_CI_SERVICE_ACCOUNT`: se autentica por **Workload Identity Federation** (token OIDC de GitHub intercambiado por credenciales de `sa-ci-dbt`, sin llaves) y ejecuta las 510 pruebas de dbt contra BigQuery, publicando `run_results.json` como artefacto. La identidad se declara en `infra/main/ci.tf` detrás de `var.github_repo` (pool `github-actions`, proveedor OIDC con condición `assertion.repository == "<repo>"`, SA con `jobUser`, `dataViewer` en todos los datasets salvo `ops_secrets` y `dataEditor` solo en `ops` para `store_failures`).
**Alternativas.** Llave JSON en un secreto de GitHub: descartada por la restricción y por riesgo de fuga. Ejecutar `dbt build` completo en CI: reconstruiría las capas en cada push (≈ 8 min y consumo de cuota); `dbt test` valida el estado publicado sin recrearlo.
**Consecuencias.** Activación en tres pasos cuando exista el remoto: `github_repo = "propietario/nombre"` en `terraform.tfvars` → `make plan && make apply` → copiar los outputs `ci_workload_identity_provider` y `ci_service_account_email` a las variables del repositorio en GitHub. Mientras tanto el primer trabajo protege cada push sin tocar la nube. Costo 0 USD.
