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

## ADR-008 · Estrategia de identidad del usuario *[verificar en generador]*
**Contexto.** No existe tabla que relacione las cuatro tarjetas. El enunciado muestra `TC-00012345`, `0000012345`, `MR0012345` (mismo sufijo numérico) y un hash de 12 caracteres para Aerómetro.
**Decisión.** Identidad base por (modo, llave nativa) → `usuario_sk = HMAC(modo || llave)`. Vínculo entre modos **solo** si el generador lo produce de forma determinista (mismo entero base o hash reproducible); en ese caso se declara el supuesto "misma persona = mismo identificador base" con confianza `alta`. Si el generador no vincula, `dim_usuario` queda por modo, el transbordo se reporta como no medible con los datos entregados y se ofrece la coincidencia de sufijo como aproximación de confianza `baja`, reportando ambos números.
**Alternativas.** Vincular por coincidencia espacio-temporal de validaciones (extra opcional, inferencia, no identidad).
**Consecuencias.** Nunca se fabrican coincidencias. Límite declarado: sin padrón unificado la Agencia no puede medir transbordo real. Se confirma en F1 leyendo el generador.
