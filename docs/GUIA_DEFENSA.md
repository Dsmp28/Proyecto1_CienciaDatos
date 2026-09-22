# Guía de defensa oral · Proyecto 1 Red Metropolitana

Documento para que **cualquier integrante** pueda explicar **cualquier parte** del proyecto ante el catedrático.
Cada afirmación lleva su número medido y la ruta del archivo que lo evidencia. Cuando una cifra todavía no existe
se dice "pendiente"; no se inventa.

Estado al escribir esta guía (2026-09-20): F0–F4 cerradas con evidencia, features cerradas, insumos de Tableau y
recomendación entregados. **La demo de idempotencia del DAG completo en la nube está corriendo**; su evidencia
quedará en `docs/evidence/idempotencia_<ts>.md` (pendiente de la corrida). El tablero en Tableau Desktop lo construye
el equipo a mano siguiendo `docs/tableau/GUIA_TABLERO.md`.

Convenciones de esta guía: **(a)** qué se hizo · **(b)** por qué (decisión y ADR) · **(c)** alternativa descartada ·
**(d)** dónde está la evidencia · **(e)** preguntas probables con respuesta corta.

---


> **Aviso de red para el día de la demo (visto el 2026-09-21).** Algunas redes institucionales interceptan HTTPS con un
> firewall (Fortinet) que sustituye el certificado y muestra una página de bloqueo al abrir
> `https://airflow.<IP_VM>.sslip.io`. El servidor está bien (desde la VM el certificado es de Let's Encrypt).
> Antes de presentar: comprobar el enlace desde el celular con datos móviles y tener ese hotspot como respaldo, o pedir
> con antelación que se permita el dominio `*.sslip.io`. La demo `make demo-idempotencia` usa la misma URL.

## 0. Guion de 10 minutos (demo en vivo)

Preparar antes: VM encendida (`make vm-start`, tarda ~2 min en levantar la pila), `.venv` creado (`make venv`),
`gcloud auth login` hecho, la contraseña del usuario `catedratico` a mano
(`gcloud secrets versions access latest --secret=airflow-viewer-password --project cienciadatos-509301`),
y el informe de idempotencia ya generado en `docs/evidence/`.

| Min | Qué se muestra | Comando / lugar | Qué se dice (una frase) |
|---|---|---|---|
| 0:00–1:00 | Arquitectura | `README.md` (diagrama) | "Cuatro operadores, tres vías de ingesta, Bronze en GCS, todo lo demás en BigQuery con dbt; Airflow orquesta; Tableau lee solo Gold." |
| 1:00–2:00 | Infraestructura viva | `make vm-status` → `RUNNING <IP_VM>` | "Todo salió de Terraform: 14 + 49 + 2 recursos (`docs/evidence/f0_infraestructura.md`); la VM corre Kafka y Airflow; solo el 443 está abierto." |
| 2:00–3:00 | Airflow con usuario de solo lectura | Abrir `https://airflow.<IP_VM>.sslip.io`, entrar como `catedratico`, abrir el DAG `red_metropolitana` (pestaña Docs = `doc_md`) | "El rol Viewer devuelve 403 al escribir; la última corrida en verde tiene 18 tareas, reintentos y métricas por etapa en `ops.run_metrics`." |
| 3:00–4:30 | Idempotencia | `make demo-idempotencia` (si hay tiempo: dos corridas completas) o, en vivo, la comparación instantánea: `bash scripts/demo_idempotencia.sh --sin-disparar docs/evidence/idempotencia_<ts>_corrida1.json docs/evidence/idempotencia_<ts>_corrida2.json` | "Dos corridas, mismas tablas, mismos conteos, mismos objetos en Bronze. Ya lo probamos por capa: Bronze 121 = 121 objetos, Silver 17 tablas idénticas, Gold 3 590 561 filas idénticas." |
| 4:30–6:00 | Linaje y restricción Gold→Silver | `cd docs/evidence/dbt_docs && python -m http.server 8080` → abrir `http://localhost:8080`, buscar `agg_demanda_modo_zona_hora`, botón de linaje; luego `make test` | "Gold desciende solo de Silver, seeds u otro Gold; `tests/test_gold_lineage.py` lo verifica sobre `manifest.json` en cada corrida." |
| 6:00–7:30 | Calidad, cuarentena y CDC | `docs/evidence/calidad_resumen.md` §2–§3 y `docs/evidence/cdc_resumen.md` | "11 913 filas en cuarentena con motivo y registro original; staging = silver + cuarentena en las 9 fuentes; el padrón pasa de 20 148 a 19 469 tarjetas activas tras los DELETE." |
| 7:30–9:00 | Una cifra del tablero y su linaje | Tablero (H2 filtrada a 2026-06-01, TM, Zona 17 = **725**) y `bq query --use_legacy_sql=false --location=us-central1 < analysis/h7_linaje_de_una_cifra.sql` | "725 = 388 + 337: dos objetos JSONL en `gs://cienciadatos-509301-lake/bronze/transmetro_validaciones/…`, con offsets de Kafka y línea del CSV original. 0,17 s y 4,2 MB." |
| 9:00–10:00 | Recomendación y cierre | `docs/RECOMENDACION.md` | "72,98 % de las personas usa más de un sistema; 11 zonas sin servicio, una con 1 261 residentes del padrón; estación de transbordo en Zona 17 (23 704 personas multimodales). Costo estimado < 60 USD/mes con presupuesto y alertas." |

Si algo falla en vivo: cada cifra tiene una copia en `docs/evidence/*.md`; se muestra el archivo y se explica el camino.

---

## 1. Tabla "cifra → dónde sale"

| # | Cifra | Valor medido | Tabla / consulta que la produce | Evidencia |
|---|---|---:|---|---|
| 1 | Filas de origen = filas en Bronze | 1 730 184 (9 archivos, diferencia 0) | `ops.ingest_manifest` vs `COUNT(*)` de `bronze.*` (`ingest/conteos_bronze.py`) | `docs/evidence/conteos_bronze.md`, `docs/METRICAS.md` §Volumen |
| 2 | Objetos y tamaño en Bronze | 121 objetos (7 batch/CDC + 73 TM + 41 AM), 346 MB | `gs://cienciadatos-509301-lake/bronze/**` | `docs/evidence/f1_ingesta_bronze.md`, `docs/PROGRESS.md` |
| 3 | Filas en Staging | 1 869 850 en 15 tablas | `staging.*`; prueba `assert_staging_igual_bronze` | `docs/METRICAS.md` §Filas por capa, `docs/evidence/cdc_resumen.md` |
| 4 | Filas en Silver (abordajes) | 1 647 569 (TM 362 106 · TU 786 398 · MR 295 511 · AM 203 554) | `silver.silver_abordajes` | `docs/evidence/calidad_resumen.md` §4.1 |
| 5 | Cuarentena total | 11 913 (0,688 % de 1 730 184) | `quarantine.registros_rechazados`, `quarantine.resumen_por_regla` | `docs/evidence/calidad_resumen.md` §2 |
| 6 | Cuarentena por regla | R01 1 115 · R02 4 186 · R03 817 · R04 3 589 · R07 2 206 | `quarantine.resumen_por_regla` | ídem; reglas en `docs/governance/reglas_calidad.md` |
| 7 | Conciliación (nada se descarta) | 1 730 184 = 1 718 271 + 11 913 en las 9 fuentes | prueba `dbt/tests/silver/assert_staging_igual_silver_mas_cuarentena.sql` | `docs/evidence/calidad_resumen.md` §3 |
| 8 | CDC: activas antes / después de los DELETE | 20 148 → 19 469 (31 050 ops: 10 800 INSERT, 16 200 UPDATE, 4 050 DELETE) | `staging.stg_padron_cdc_resumen` | `docs/evidence/cdc_resumen.md`, `docs/METRICAS.md` §CDC |
| 9 | Filas en Gold | `fct_abordaje` 1 647 569 (= Silver); 17 tablas, 3 590 561 filas | `gold.__TABLES__`; prueba `assert_abordajes_gold_igual_silver` | `docs/evidence/gold_resumen.md` §2–§3 |
| 10 | Viajes del mes (junio 2026), dos caminos | 1 093 235 = 1 093 235 | `analysis/viajes_del_mes_a.sql` (`fct_abordaje` × `dim_tiempo`) y `_b.sql` (`fct_uso_usuario_dia`) | `docs/evidence/gold_resumen.md` §4; prueba `assert_viajes_del_mes_dos_caminos` |
| 11 | Cobertura | 11 de 26 zonas sin servicio de ningún modo | `gold.agg_cobertura_zona`; `analysis/h3_cobertura.sql` | `docs/evidence/gold_resumen.md` §5 |
| 12 | Transbordo | 41 485 de 56 848 personas usan > 1 sistema = 72,98 % | `gold.agg_transbordo_resumen`; `analysis/h4_transbordo.sql` | `docs/evidence/gold_resumen.md` §6, ADR-008 |
| 13 | Hora pico | 906 950 / 1 647 569 = 55,05 %; 07:00 = 197 491 (11,99 %) | `gold.agg_demanda_modo_zona_hora`; `analysis/h1_demanda_modo_hora.sql` | `docs/evidence/tablero_resumen.md` |
| 14 | Zona con más demanda | Zona 17 = 148 554 (9,02 %); top 5 = 43,68 % | `analysis/h2_demanda_zona.sql` | `docs/evidence/tablero_resumen.md` |
| 15 | Usuarios activos (30 d a 2026-07-16) | 53 820 personas (110 762 tarjetas) | `analysis/h6_kpis.sql`; `features.usuario_features.es_usuario_activo_30d` | `docs/evidence/features_resumen.md` §4, `docs/governance/definiciones_oficiales.md` §2 |
| 16 | Features | 56 848 filas × 34 columnas, corte 2026-07-16 | `features.usuario_features`, `features.diccionario_features` | `docs/evidence/features_resumen.md` |
| 17 | Linaje de una cifra | 725 abordajes (TM, Zona 17, 2026-06-01) = 388 + 337 en 2 objetos de Bronze | `analysis/h7_linaje_de_una_cifra.sql` (0,17 s, 4,2 MB) | `docs/evidence/tablero_resumen.md`, `docs/tableau/GUIA_TABLERO.md` §9 |
| 18 | Identidad unificada | 117 205 tarjetas, 100 % con `usuario_unificado_sk`; 14 496 / 14 496 hashes de Aerómetro invertidos | `silver.silver_usuarios`, `silver.silver_am_hash_map` | `docs/evidence/calidad_resumen.md` §4.2, ADR-008 |
| 19 | Costo mensual | **Estimado** ~56 USD con la VM 24/7; ~20–25 USD apagándola fuera de horario; presupuesto 60 USD con alertas | precios de lista `us-central1` | `infra/README.md` §Costos, `docs/evidence/f0_infraestructura.md` §Presupuesto. **Costo medido acumulado: pendiente** (`docs/PROGRESS.md` solo registra ≈ 0 USD al 2026-09-20) |
| 20 | Idempotencia del DAG completo | pendiente de la corrida | `scripts/demo_idempotencia.sh` → `ingest/conteos_capas.py --comparar` | `docs/evidence/idempotencia_<ts>.md` (pendiente) |

---

## 2. Secciones de la rúbrica

### 1.1 Ingesta y Bronze (8 pts)

**(a) Qué se hizo.** Tres vías de ingesta a `gs://cienciadatos-509301-lake/bronze/<fuente>/ingest_date=YYYY-MM-DD/`:
batch (`ingest/batch_to_gcs.py --via batch`: 4 catálogos, `metroriel_viajes.jsonl`, `transurbano_transacciones.csv`,
copia byte a byte con md5 verificado), CDC (`--via cdc`: `cdc_padron_usuarios.csv`) y streaming (`ingest/kafka_producer.py`
publica línea a línea Transmetro y Aerómetro en los tópicos `transmetro.validaciones` y `aerometro.boardings`;
`ingest/kafka_consumer_gcs.py` escribe objetos JSONL con nombre determinista por tópico, partición y ventana de 5 000
offsets: 73 + 41 = 114 objetos). Resultado: 9 archivos, **1 730 184 filas de origen = 1 730 184 en Bronze, diferencia 0**
(`docs/evidence/conteos_bronze.md`); 121 objetos y 346 MB (137 batch + 209 streaming). Cada archivo se registra en
`ops.ingest_manifest` con su sha256. BigQuery expone Bronze como 9 tablas externas con particionado Hive
(`ingest/bronze_external_tables.py`, `ingest/sql/bronze_external_tables.sql`), declaradas como `source` en
`dbt/models/staging/sources.yml`. Rendimiento: productor 63 084 y 96 971 msg/s; consumidor 566 775 mensajes en 77,8 s.

**(b) Por qué.** ADR-002: Bronze en el lago (GCS) y no en el warehouse, para conservar el dato "tal como llegó"
(incluido el JSON anidado de MetroRiel) y que sobreviva a recrear BigQuery. ADR-003: Transurbano por batch. ADR-006:
manifiesto por sha256 y objetos deterministas para que Bronze se acumule sin duplicarse.

**(c) Alternativa descartada.** Cargar directo a tablas nativas de BigQuery: obliga a tipar al entrar (deja de ser
crudo) y mezcla almacenamiento con cómputo. Transurbano por streaming: duplicaría el trabajo de idempotencia sobre el
archivo más grande (832 791 filas) y un broker de un nodo sería el cuello de botella.

**(d) Evidencia.** `docs/evidence/f1_ingesta_bronze.md`, `docs/evidence/conteos_bronze.md`, `docs/METRICAS.md` §Volumen,
`ingest/expected_hashes.json`.

**(e) Preguntas probables.**
- *¿Por qué batch para Transurbano si es un ledger de abordajes?* Porque el archivo llega completo, con fecha y hora en
  columnas separadas y montos en centavos: es un cierre diario, no un flujo. Batch da idempotencia exacta por sha256 y
  reproceso trivial; la latencia de un día es aceptable para planificación (ADR-003). Los duplicados se tratan en Silver
  con las mismas reglas que las fuentes de streaming.
- *¿Qué pasa si republico el CSV en Kafka?* El productor consulta `ops.ingest_manifest` y omite el archivo si su sha256
  ya fue publicado (segunda corrida: `omitido … ya publicado (manifiesto)`, 0 mensajes, 0 objetos,
  `docs/evidence/f1_ingesta_bronze.md`). Si alguien forzara la republicación, el consumidor escribiría objetos con nombres
  distintos (offsets nuevos) y Silver los detectaría con la regla R10 `duplicado de entrega` por `(archivo, sha256, linea_num)`
  y los mandaría a cuarentena. Hoy R10 = 0.
- *¿Por qué lake y no directamente warehouse?* Porque Bronze debe ser inmutable y crudo; el linaje llega al objeto en GCS
  (`_FILE_NAME`, `objeto_gcs` en `dim_fuente`). El almacenamiento de 346 MB entra en el nivel gratuito.
- *¿"Tal como llegó" si el streaming envuelve cada línea en JSON?* La línea original va intacta en el campo `raw`; la
  envolvente añade tópico, partición, offset, archivo, `linea_num` e `ingest_ts`, que son metadatos de ingesta, no
  transformación. Por eso el streaming pesa 209 MB frente a 36 MB de los CSV.
- *¿Por qué 73 y 41 objetos?* Ventanas de 5 000 mensajes: 363 221 / 5 000 = 72,6 → 73; 203 554 / 5 000 = 40,7 → 41.
- *¿Cómo sabes que Bronze coincide con el origen?* `ingest/conteos_bronze.py` compara filas del manifiesto contra
  `COUNT(*)` de cada tabla externa: 9 de 9 con diferencia 0; el DAG lo repite en la tarea `conciliar_bronze`.

### 1.2 Staging y CDC (9 pts)

**(a) Qué se hizo.** 15 tablas en `dbt/models/staging/`: 9 `stg_*` tipadas con columnas de linaje (`fuente`, `archivo`,
`ingest_date`, `linea_num`, `kafka_offset`), `stg_cdc_padron_usuarios` (log tipado), `stg_padron_cdc_aplicado` (padrón
vigente por tarjeta), `stg_padron_cdc_resumen` y 4 `stg_catalogo_usuarios_*` (llave, operador, `n_registros`; nada más).
Total 1 869 850 filas; Staging no filtra ni deduplica (`assert_staging_igual_bronze`: 9 de 9 fuentes iguales a Bronze)
y se reconstruye completa en cada corrida (`+materialized: table`). CDC aplicado en orden de `seq`: 31 050 operaciones
(10 800 INSERT, 16 200 UPDATE, 4 050 DELETE), 22 462 tarjetas distintas, **20 148 activas antes de los DELETE y 19 469
después**; 7 845 altas limpias, 14 617 altas implícitas, 2 158 INSERT repetidos, 15 069 cambios, 2 993 bajas, 2 206 filas
`SIN-TARJETA` (a cuarentena R07). Catálogos de llaves: TM 43 255, TU 36 567, MR 22 885, AM 14 496.

**(b) Por qué.** ADR-009: el padrón es el registro central de personas de la Agencia (su columna `tarjeta` mezcla tres
formatos: 22 326 TC-, 5 223 TU, 1 295 MR), identificado por `usuario_base_id`; reglas explícitas para INSERT repetido,
UPDATE sin INSERT y DELETE sin INSERT. ADR-008: identidad por formato de llave.

**(c) Alternativa descartada.** Tratarlo como padrón exclusivo de Transmetro y mandar a cuarentena los formatos TU/MR:
perdería el 21 % del padrón por una decisión de nombre. Rechazar UPDATE/DELETE sin INSERT previo: perdería historia
real que el log sí registra.

**(d) Evidencia.** `docs/evidence/cdc_resumen.md` (con las 9 identidades aritméticas que cuadran las cifras),
`docs/METRICAS.md` §CDC, `dbt/tests/staging/assert_staging_igual_bronze.sql`.

**(e) Preguntas probables.**
- *¿Qué pasa con los DELETE del padrón?* No se borra nada: el DELETE marca `estado = INACTIVA` y conserva `perfil` y
  `zona_residencia` previos; si no hubo alta, se crea la fila inactiva sin atributos (2 314 tombstones). 635 tarjetas
  recibieron un INSERT/UPDATE después de su DELETE y quedaron activas (la última operación por `seq` manda). En Gold la
  historia completa está en `dim_padron_historia` (28 844 versiones) y `fct_cambio_padron`.
- *¿Por qué "antes" son 20 148 y no las 22 462 tarjetas?* Porque 2 314 tarjetas solo tienen DELETE: nunca estuvieron
  activas. 22 462 − 2 314 = 20 148; y 20 148 − 679 bajas reales = 19 469 (`docs/evidence/cdc_resumen.md` §Cómo cuadran).
- *¿Cómo aplicas en orden si `commit_ts` viene desordenado?* Por `seq`, no por `commit_ts`: 103 operaciones tienen
  `commit_ts_fuera_de_orden` (`silver_padron_scd2`), y `seq` es la secuencia del log.
- *¿Los catálogos mínimos inventan atributos?* No: solo `llave`, `operador` y `n_registros`; `SUM(n_registros)` reproduce
  las filas de cada fuente (restricción dura 8).
- *¿Por qué Staging no limpia nada?* Para que la conciliación posterior sea verificable: todo lo que entra a Staging
  sale a Silver o a cuarentena, y Staging se vacía en cada corrida (restricción dura 6).

### 1.3 Silver, calidad y cuarentena (12 pts)

**(a) Qué se hizo.** Reglas R01–R11 escritas **antes** del código en `docs/governance/reglas_calidad.md`, con orden de
evaluación fijo (una fila, una regla). 17 tablas (`dbt/models/silver/`: 6 `val_*` de validación, 9 `silver_*`;
`dbt/models/quarantine/`: `registros_rechazados`, `resumen_por_regla`), 161 pruebas, PASS = 178 en dos builds de
2 min 15 s y 2 min 33 s. Cuarentena **11 913** filas (0,688 %): R01 duplicado de torniquete 1 115, R02 parada nula 4 186,
R03 fecha del futuro 817, R04 viaje sin salida 3 589, R07 llave nula 2 206; R05, R06, R08–R11 = 0. Cada fila lleva
`registro_original`, `fuente`, `archivo`, `regla_id`, `motivo`, `llave_usuario`, `run_id`, `ts_cuarentena`. Conciliación
por fuente **staging = silver + cuarentena**: 1 730 184 = 1 718 271 + 11 913. Silver: `silver_abordajes` 1 647 569 (grano
abordaje, cuatro modos), `silver_usuarios` 117 205 (100 % con identidad unificada), `silver_padron_scd2` 28 844 filas y
22 462 vigentes, `silver_estaciones` 468 con zona conformada (R05 = 0), `silver_am_hash_map` 70 000. Seeds versionados:
`zonas` (26), `zonas_mapeo`, `franjas_horarias`, `feriados_gt`.

**(b) Por qué.** Restricción dura 2: nada se descarta. ADR-010: los cobros rechazados de Transurbano (`cod_estado` 7 y 9)
son hechos reales, se conservan y no cuentan como viaje. ADR-008: identidad unificada calculada en Silver (llave nativa
solo aquí, nunca en Gold). ADR-006: `table` y `fecha_referencia` fija.

**(c) Alternativa descartada.** Corregir o imputar registros (p. ej. asignar parada por cercanía): contamina el hecho con
supuestos. Descartar duplicados en silencio: pierde media sección de la rúbrica y la trazabilidad. Mandar a cuarentena los
cobros rechazados: confundiría "registro inválido" con "cobro fallido".

**(d) Evidencia.** `docs/evidence/calidad_resumen.md` (§2 por regla, §3 conciliación, §5 muestra de cuarentena, §6 dos
builds idénticos), `docs/METRICAS.md` §Calidad, `dbt/tests/silver/*.sql`.

**(e) Preguntas probables.**
- *¿Por qué R02 da 4 186 y no 4 189?* Hay 4 189 filas con `cod_parada` vacío, pero 3 tienen además fecha del futuro. El
  orden de evaluación es R07 → R08 → R03 → R06/R02 → …, así que esas 3 se etiquetan R03. Una fila, una regla:
  4 186 + 817 = 5 003 = filas de Transurbano en cuarentena. Si se etiquetaran con dos reglas, la suma por regla no cuadraría
  con el total.
- *¿Cómo resolviste la identidad si no hay tabla de cruce?* Verificamos en el generador que las cuatro llaves derivan de
  un mismo entero base `i`: `TC-{i:08d}`, `{i:010d}`, `MR{i:07d}` y `md5("am"+i)[:12]`. Para TM/TU/MR se extrae por
  formato; para Aerómetro se construyó `silver_am_hash_map` calculando el MD5 para `i` = 1…70 000 y se invirtieron
  14 496 de 14 496 hashes (`assert_am_hash_invertible`). `usuario_unificado_sk = HMAC(sal, 'BASE|i)`. Supuesto declarado:
  mismo identificador base = misma persona (ADR-008). Sin ese vínculo, el diseño sigue funcionando con `usuario_sk` por modo.
- *¿Por qué `SALDO_INSUF` no va a cuarentena?* Porque es un evento real del sistema de cobro (33 112 + 8 278 = 41 390 en
  Silver), no un registro malformado. Se conserva con su estado en `silver_transurbano_transacciones` y no cuenta como viaje.
- *¿Cómo pruebas que no descartaste nada?* `assert_staging_igual_silver_mas_cuarentena` falla el build si alguna fuente no
  cuadra; y `assert_staging_igual_bronze` garantiza que Staging tampoco filtró.
- *¿Por qué los duplicados cuentan como cuarentena y no se eliminan?* Porque el registro repetido es evidencia de un
  defecto del torniquete (1 115 casos, 0,307 %); se conserva la primera aparición por `(linea_num, kafka_offset)` y la
  repetida queda en cuarentena con su `registro_original` para auditar.
- *¿Qué es exactamente un registro inválido?* Uno que no puede representar un abordaje verificable: no se sabe quién
  (R07), dónde (R02, R06), cuándo (R03, R08) o es repetición exacta (R01, R10). Definición en `reglas_calidad.md`.

### 1.4 Gold (15 pts)

**(a) Qué se hizo.** Modelo dimensional en `dbt/models/gold/`: 7 dimensiones (`dim_tiempo` 1 080 = 45 días × 24 h,
`dim_modo` 4, `dim_zona` 26, `dim_estacion` 468, `dim_usuario` 117 205 seudonimizada, `dim_padron_historia` 28 844 SCD2,
`dim_fuente` 121 objetos crudos), 5 hechos (`fct_abordaje` 1 647 569, `fct_viaje_metroriel` 295 511, `fct_uso_usuario_dia`
1 376 322, `fct_cobertura_zona_modo` 44 factless, `fct_cambio_padron` 28 844) y 5 agregados para Tableau (`agg_*`).
197 pruebas, PASS = 214, dos builds idénticos (3 590 561 filas). `fct_abordaje` particionada por `fecha` y agrupada por
`modo_id, zona_id` (H7 lee 4,2 MB de 1,65 M de filas). Entregables: grano y matriz del bus (`docs/modelo/matriz_bus.md`),
diagrama ER Mermaid (`docs/modelo/modelo_gold.mmd`), DDL real (`docs/modelo/ddl_gold.sql`), diccionario generado desde
`manifest.json` + `catalog.json` (`docs/governance/diccionario_gold.md`, 17 tablas) y clasificación de medidas
(aditiva / semi aditiva / no aditiva / factless).

**(b) Por qué.** ADR-004: grano "una validación de una tarjeta de un usuario en un modo, en una estación o parada, en un
instante": es lo que entregan 3 de 4 operadores sin inferencia y el grano más atómico disponible (Kimball). ADR-007:
`usuario_sk = HMAC-SHA256(sal, modo|llave)` antes de Gold.

**(c) Alternativa descartada.** Grano "viaje puerta a puerta": exigiría inferir el viaje con ventanas de tiempo y
proximidad para Transmetro, Transurbano y Aerómetro, con datos generados que no lo permiten verificar; cada cifra
heredaría ese error y no se podría volver al detalle.

**(d) Evidencia.** `docs/evidence/gold_resumen.md`, `tests/test_gold_lineage.py` (4 passed), `dbt/tests/gold/*.sql`,
`docs/evidence/linaje_dbt.md`.

**(e) Preguntas probables.**
- *¿Por qué el grano es abordaje y no viaje?* Porque el abordaje es el hecho atómico que los cuatro sistemas entregan;
  el viaje se agrega desde él, nunca al revés. MetroRiel no pierde nada: su entrada es un abordaje y el viaje completo
  (entrada, salida, 21,42 min promedio) vive en `fct_viaje_metroriel`. Tabla comparativa en `matriz_bus.md` §1.
- *¿Cómo sabes que Gold no lee Bronze?* Tres capas de control: (1) `tests/test_gold_lineage.py` recorre `parent_map` de
  `manifest.json` y falla si un modelo de `gold/` tiene un padre `source.` o `staging` (4 passed; corre en la tarea
  `pruebas_python` del DAG); (2) el grafo de `dbt docs` (`docs/evidence/dbt_docs/index.html`) lo muestra visualmente;
  (3) `assert_gold_sin_llaves_nativas` verifica que ninguna columna de Gold sea `tarjeta`, `num_tarjeta`, `card`,
  `user_hash`, `llave_nativa` ni `usuario_base_id`.
- *Dame una medida semi aditiva y por qué.* `tarjetas_activas_despues` en `fct_cambio_padron`: es un saldo; se puede
  sumar entre usuarios en un instante pero no a lo largo del tiempo. Se valida con
  `assert_saldo_tarjetas_activas_igual_vigentes` (saldo final 19 469 = vigentes ACTIVA).
- *¿Qué es un hecho factless aquí?* `fct_cobertura_zona_modo`: 44 pares (zona, modo) con al menos una estación; no tiene
  medida numérica, se cuenta la existencia de la fila. `dim_zona LEFT JOIN` sin fila = zona sin servicio (11 de 26).
- *¿Por qué `dim_usuario` tiene grano tarjeta-por-modo y no persona?* Porque la tarjeta es lo que el operador conoce; la
  persona (`usuario_unificado_sk`) es una columna de vínculo que depende del supuesto de ADR-008. Así la Agencia puede
  operar aunque el vínculo no exista.
- *¿Dónde hay role-playing?* `fct_viaje_metroriel` usa `dim_tiempo`, `dim_estacion` y `dim_zona` dos veces (entrada/origen
  y salida/destino).
- *¿Por qué `fct_uso_usuario_dia` sale de Silver y no de `fct_abordaje`?* Para que "viajes del mes" tenga dos caminos
  independientes (1 093 235 = 1 093 235): si ambos salieran del mismo hecho, la prueba de fuego no probaría nada.

### 1.5 Orquestación e idempotencia (5 pts)

**(a) Qué se hizo.** DAG `red_metropolitana` (`airflow/dags/red_metropolitana_dag.py`) en Airflow 3.3.2 (LocalExecutor,
Docker Compose en la VM): 18 tareas en 4 grupos: `generar_o_verificar_datos` → `ingesta_bronze` (batch, cdc, productor →
consumidor en paralelo) → `tablas_externas_bronze` → `conciliar_bronze` → (junto con `publicar_clave_hmac`) →
`transformacion_dbt` (deps, seed, staging, silver+quarantine, gold, features, docs) → `pruebas_python` →
`registrar_metricas`; `registrar_fallo` con `trigger_rule=one_failed`. Reintentos 2 con espera exponencial desde 2 min,
`max_active_runs=1`, callbacks que escriben `duracion_s` por tarea en `ops.run_metrics`, `doc_md` con la tabla "por qué
cada etapa es idempotente". Demo: `make demo-idempotencia` (`scripts/demo_idempotencia.sh`) dispara dos corridas por la
REST API v2, toma una instantánea de `COUNT(*)` de todas las tablas de las 6 capas y de objetos/bytes en Bronze
(`ingest/conteos_capas.py`) y falla si difieren. Evidencia parcial ya medida: Bronze 121 = 121 objetos y 0 bytes subidos
en la segunda corrida (`f1_ingesta_bronze.md`); Silver 17 tablas con conteos idénticos en dos builds (`calidad_resumen.md`
§6); Gold 17 tablas, 3 590 561 filas idénticas (`gold_resumen.md` §3); features 56 848 / 1 647 569 / 53 820 idénticos
(`features_resumen.md` §5). **Evidencia del DAG completo en la nube: `docs/evidence/idempotencia_<ts>.md`, pendiente de
la corrida.**

**(b) Por qué.** ADR-005: Airflow (reintentos, bitácora, roles con usuario de solo lectura para el catedrático). ADR-006:
manifiesto por sha256, objetos deterministas, `table` en todas las capas, `fecha_referencia` fija, nunca `CURRENT_DATE`.

**(c) Alternativa descartada.** Prefect (la UI compartible con roles exige Prefect Cloud o un servidor propio igual);
Cloud Composer (> 300 USD/mes); modelos incrementales con `merge` (más eficientes, pero su idempotencia depende de llaves
únicas por fuente: quedan como extra).

**(d) Evidencia.** `airflow/dags/red_metropolitana_dag.py` (doc_md), `tests/test_dag.py`, `scripts/demo_idempotencia.sh`,
`ingest/conteos_capas.py`, evidencias parciales citadas; final pendiente.

**(e) Preguntas probables.**
- *¿Por qué Airflow y no Prefect, que era lo recomendado?* Necesitábamos una UI en la nube con un usuario de solo
  lectura para el catedrático, reintentos y bitácora por tarea. En Prefect eso exige Prefect Cloud o montar un servidor
  igual; Airflow lo trae nativo (rol Viewer verificado: 403 al escribir, `f0_infraestructura.md`). El costo de memoria se
  mitigó con LocalExecutor (sin Redis ni workers) en una e2-standard-2: 6 272 MiB comprometidos (`vm/README.md`).
- *¿Por qué no `CURRENT_DATE`?* Porque rompe la idempotencia: la regla R03 "fecha del futuro", el corte de features y
  `dim_tiempo` cambiarían de resultado según el día en que se corra. Se usa `var('fecha_referencia') = 2026-07-16` (día
  siguiente a la última fecha legítima, ADR-010); `tests/test_no_current_date.py` falla si algún SQL, macro o prueba usa la
  fecha del sistema; Tableau tampoco usa `TODAY()`.
- *¿Qué pasa si falla una tarea?* Reintenta 2 veces con backoff; si sigue fallando, `registrar_fallo` escribe `estado = 0`
  en `ops.run_metrics` para ese `run_id` y la UI marca la corrida en rojo. Como todo es `table`, la siguiente corrida
  reconstruye desde Bronze sin estado intermedio.
- *¿Qué compara exactamente la demo?* Mismas tablas, mismos `COUNT(*)` en bronze/staging/silver/quarantine/gold/features y
  mismos objetos y bytes en `gs://…/bronze/`. Códigos: 0 idénticas, 1 difieren. El informe queda en `docs/evidence/`.
- *¿Por qué `schedule=None`?* Es un lote de 45 días que se dispara a demanda; podría ser `@daily` sin cambios porque cada
  etapa es idempotente y `catchup=False`.
- *¿Y si dos corridas se solapan?* `max_active_runs=1` lo impide.

### 2.1 Tablero (16 pts)

**(a) Qué se hizo.** Tableau Desktop conecta **solo** a `cienciadatos-509301.gold` (fuente `.tds` sin credenciales:
`docs/tableau/red_metropolitana_gold.tds`, estrella `fct_abordaje` × 5 dimensiones; más los 5 `agg_*` como fuentes
rápidas). Guía hoja por hoja (`docs/tableau/GUIA_TABLERO.md`): H1 demanda modo × hora, H2 demanda por zona, H3
cobertura, H4 transbordo, H5 caso MetroRiel, H6 KPIs, dashboard con filtros globales y parámetro `[Fecha de referencia]`.
Cada hoja tiene su SQL en `analysis/h1…h6*.sql` con cifra esperada, tiempo del job y bytes medidos sin caché: 0,17–4,1 s,
0,3–256 MB (`analysis/README.md`). Linaje de una cifra al archivo crudo: `analysis/h7_linaje_de_una_cifra.sql`
(725 = 388 + 337, 0,17 s). Las cifras de las cuatro preguntas del enunciado: hora pico 55,05 %; Zona 17 148 554; 11 zonas
sin servicio; 72,98 % multimodal; las 5 zonas de MetroRiel ocupan los puestos 1–5 (43,68 %). **El tablero en Tableau
Desktop lo construye el equipo a mano** siguiendo la guía; desde este entorno no se abrió Tableau
(`docs/tableau/GUIA_TABLERO.md` §10).

**(b) Por qué.** Restricción del stack: Tableau → Gold únicamente; los agregados viven en Gold (no en Tableau ni en
Silver) para que cualquier cifra sea reproducible por SQL y trazable a Bronze (restricción dura 4).

**(c) Alternativa descartada.** Conectar Tableau a Silver (rompe la regla y expone llaves nativas); extractos obligatorios
(innecesarios: ninguna consulta pasa de 5 s en vivo).

**(d) Evidencia.** `docs/evidence/tablero_resumen.md`, `analysis/README.md`, `docs/tableau/README.md`.

**(e) Preguntas probables.**
- *¿Cómo rastreas una cifra del tablero al archivo crudo?* `fct_abordaje` lleva `fuente_sk`, `archivo`, `objeto_gcs`,
  `ingest_date`, `linea_num`, `kafka_offset`; `dim_fuente` (121 objetos) da el `gs://` exacto; la tabla externa de Bronze
  tiene el mismo nombre que `fuente`. H7: los 725 abordajes de TM en Zona 17 el 2026-06-01 se reparten sin pérdida en dos
  objetos JSONL (offsets 3…4 985 y 5 013…9 292; líneas 4…4 986 y 5 014…9 293 del CSV del operador).
- *¿Por qué el filtro de fecha no cambia H3, H4 y H5?* Porque cobertura, transbordo y el caso MetroRiel son agregados de
  los 45 días sin columna `fecha`; el subtítulo del dashboard lo declara. Solo H1, H2 y H6 responden a la fecha.
- *¿Y si Tableau muestra una cifra distinta al SQL?* Es un defecto (join que duplica filas, filtro de contexto, caché);
  la cifra correcta es la del SQL en `analysis/`, ejecutado sin caché.
- *¿Por qué no hay mapa?* Gold no tiene geometrías de zona (solo lat/lon de Transmetro en `dim_estacion`); se usa tabla
  con zonas en rojo o matriz zona × modo. Añadir geometrías es trabajo de Planificación territorial.
- *¿Por qué no usar `TODAY()` para "usuarios activos"?* Misma regla que el pipeline: parámetro `[Fecha de referencia]` =
  2026-07-16; así el KPI (53 820 personas) coincide con `h6_kpis.sql` y con `features.usuario_features`.

### 2.2 Recomendación (10 pts)

**(a) Qué se hizo.** `docs/RECOMENDACION.md` (≤ 2 páginas): 4 hallazgos y 4 recomendaciones, cada cifra con el SQL de
`analysis/` que la produce. Hallazgos: 55,05 % de los viajes en 8 horas pico y 43,68 % en las 5 zonas de MetroRiel; 11 de
26 zonas sin servicio, de las que solo Santa Catarina Pinula tiene residentes del padrón (1 261 personas, 2 677 tarjetas);
72,98 % de las personas usa más de un sistema (TM+TU la combinación más frecuente, 12 477); Aerómetro es el modo de menor
alcance (9 zonas, 12,35 % de los viajes). Recomendaciones: estación de transbordo en Zona 17 (23 704 personas usan ≥ 2
modos en la zona; estaciones MR 22 y Aerómetro Eje 1 - Torre 6, `analysis/h8_transbordo_estacion_candidata.sql`);
extender Transurbano a Santa Catarina Pinula; concentrar Aerómetro en Mixco y Zona 7; reforzar 06–08 y 17–18 (44,6 %).
Sección explícita "dónde sí y dónde no" y "límites de la evidencia".

**(b) Por qué.** El enunciado pide responder si los cuatro modos integrados resuelven la movilidad, con cifras; la
recomendación se apoya solo en Gold para que cada afirmación sea reproducible.

**(c) Alternativa descartada.** Recomendar ampliar Aerómetro (parece "moderno") sin mirar su uso: los datos muestran
≈ 320 viajes/día por torre fuera de Mixco y Zona 7. Elegir Zona 12 en vez de 17: la diferencia de viajes (651) no es
significativa, pero Zona 17 tiene más personas multimodales dentro de la zona (23 704 vs 23 004).

**(d) Evidencia.** `docs/RECOMENDACION.md`, `analysis/h1…h8*.sql`, `docs/evidence/tablero_resumen.md` §1.

**(e) Preguntas probables.**
- *¿Los datos son sintéticos; vale la recomendación?* Las distribuciones son más uniformes que en la realidad (≈ 1 250
  residentes por zona), así que las diferencias pequeñas no son significativas; las de orden (4 modos vs 2, pico vs valle,
  11 zonas sin servicio, 73 % multimodal) sí. El método es lo que se entrega: con datos reales las mismas consultas dan la
  respuesta real.
- *¿Por qué Transurbano para Santa Catarina Pinula?* Es el modo más barato de desplegar y el de mayor volumen (47,7 %);
  se propone medir el uso a los 30 días con las mismas tablas Gold.
- *¿Cuál es el límite principal?* La identidad de persona depende del vínculo determinista de ADR-008; sin él, el 72,98 %
  no sería medible. Y Gold no tiene distancias entre estaciones: la ubicación exacta de la estación exige estudio de sitio.
- *¿Por qué Aerómetro no está "perdiendo datos"?* 0 de 203 554 filas en cuarentena (`calidad_resumen.md`): su bajo
  volumen es demanda real.

### 2.3 Features (7 pts)

**(a) Qué se hizo.** `features.usuario_features` (`dbt/models/features/usuario_features.sql`): 56 848 filas (una por
persona, `usuario_unificado_sk`) × 34 columnas, construida **solo desde Silver y seeds** (`silver_abordajes`,
`silver_usuarios`, `silver_metroriel_viajes`, `silver_padron_scd2`, `franjas_horarias`, `feriados_gt`). Fecha de corte
declarada `fecha_corte = 2026-07-16` grabada en cada fila; toda fuente se filtra con `fecha < fecha_corte`. Ventanas 7/30/90
días, recencia, gasto, proporción hora pico, modo y franja más frecuentes, multimodalidad (41 485 = 72,98 %), estado del
padrón "as of". 58 pruebas, PASS = 60; `assert_features_sin_fuga` (recencia mínima 1 día, `SUM(viajes_total)` = 1 647 569
= abordajes antes del corte), `assert_features_ventanas_monotonas`, `assert_diccionario_cubre_columnas` (diccionario en
el warehouse, 34 filas). Prueba con corte alternativo 2026-06-16: 56 368 filas, 542 830 viajes, sigue cuadrando. Frase de
predicción: **abandono (churn) a 30 días**, útil para campañas de retención y tarifa integrada.

**(b) Por qué.** Restricción dura 5: features desde Silver, nunca desde Gold. Corte fijo para que la tabla sea
reproducible y no mezcle pasado y futuro. Grano persona porque la retención se decide por persona, no por tarjeta.

**(c) Alternativa descartada.** Derivarlas de `fct_uso_usuario_dia` (Gold): sería más rápido, pero heredaría las
decisiones de presentación de Gold y violaría la restricción. Calcular la etiqueta dentro del modelo: mezclaría futuro con
pasado.

**(d) Evidencia.** `docs/evidence/features_resumen.md`, `docs/features/README.md`, `docs/features/diccionario_features.md`,
`tests/test_gold_lineage.py::test_features_solo_referencia_silver`.

**(e) Preguntas probables.**
- *¿Por qué las features salen de Silver?* Porque Silver tiene el detalle limpio y validado sin las decisiones de
  presentación de Gold (agregaciones, seudónimos ya aplicados a nivel de tarjeta). Así el científico de datos puede
  cambiar ventanas sin tocar Gold, y se cumple la restricción 5, verificada sobre `manifest.json`.
- *¿Cómo evitas fuga de información?* Corte exclusivo (`fecha < fecha_corte`), `dias_desde_ultimo_viaje` mínimo = 1,
  padrón "as of" ordenado por `seq`, y la etiqueta nunca se calcula dentro del modelo. Split temporal, no aleatorio.
- *¿Por qué no hay etiqueta?* El lote termina el 2026-07-15 y el corte es el 2026-07-16: no hay futuro observado. Para
  entrenar se retrocede el corte (`--vars '{"fecha_corte": "2026-06-16"}'`) y la etiqueta se calcula con los 30 días
  siguientes desde `silver_abordajes`.
- *¿Por qué `viajes_90d` = `viajes_total`?* La ventana observada es de 45 días; la de 90 está truncada y se declara así.
  `tendencia_30_vs_anterior` queda sesgada al alza (mediana +9) por comparar 30 contra 15 días.
- *¿Qué predecirías y para qué?* `abandono_30d`: que la persona no vuelva a viajar en los 30 días siguientes; sirve para
  dirigir retención antes de perder demanda. Alternativa natural: viajes esperados a 7 días.

### 3.1 Gobernanza (8 pts)

**(a) Qué se hizo.** `docs/governance/definiciones_oficiales.md`: definición oficial de **un viaje** (= un abordaje
válido) con su traducción por operador, de **usuario activo** (≥ 1 viaje en los 30 días anteriores a la fecha de
referencia, no dado de baja en el padrón; 53 820 personas) y tabla de **dueños por dominio** (7 filas: `dim_zona` →
Planificación territorial; `dim_tiempo` → Planificación de operación; `dim_estacion` → operador + Agencia; sal HMAC →
Seguridad de la información / Oficial de protección de datos; etc.). `docs/governance/reglas_calidad.md` escrito antes
del código. `docs/governance/diccionario_gold.md` generado desde `manifest.json` + `catalog.json` (17 tablas; también
persistido en BigQuery con `persist_docs`). Prueba de fuego "viajes del mes" por dos caminos: 1 093 235 = 1 093 235
(`assert_viajes_del_mes_dos_caminos`). Grafo de linaje: `docs/evidence/dbt_docs/index.html` (9 sources, 4 seeds, 51 modelos,
510 pruebas; `docs/evidence/linaje_dbt.md`).

**(b) Por qué.** Los cuatro operadores miden distinto; sin definición única, "viajes del mes" daría cuatro números. La
prueba de fuego demuestra que la definición es operativa, no retórica.

**(c) Alternativa descartada.** Definir viaje como "puerta a puerta" (no comparable entre modos sin inferencia). Dejar el
diccionario a mano (se desincroniza; por eso se genera desde el YAML de dbt).

**(d) Evidencia.** `docs/governance/*.md`, `docs/evidence/gold_resumen.md` §4, `docs/evidence/linaje_dbt.md`,
`scripts/exportar_diccionario.py`.

**(e) Preguntas probables.**
- *¿Qué es un viaje?* Un abordaje válido: una validación de tarjeta de un usuario en un modo, en una estación o parada,
  en un instante, que pasó todas las reglas de calidad y existe en `silver_abordajes` y `gold.fct_abordaje`. TM: 1
  validación; TU: 1 transacción con cobro exitoso; MR: 1 viaje cerrado (su entrada); AM: 1 boarding. Un transbordo entre
  modos son 2 viajes. Junio 2026: 1 093 235 por dos caminos.
- *¿Qué pasa si cambia la definición de zona (p. ej. se subdivide la Zona 18)?* Planificación territorial propone, el
  Comité de datos autoriza, se versiona el seed `dbt/seeds/zonas_mapeo.csv` (y `zonas.csv`), se registra un ADR y se
  reconstruye Gold (todo es `table`, minutos). R05 y `assert_zonas_mapeadas` fallarían el build si un valor quedara sin
  mapear, así que el cambio no puede pasar a medias.
- *¿Quién es dueño de `dim_usuario`?* Transmetro para el padrón; la Agencia (Seguridad de la información) para la sal y su
  rotación; el Oficial de protección de datos autoriza cambios.
- *¿Cómo demuestras que la definición se aplica igual en todo el pipeline?* Dos caminos independientes (`fct_abordaje` ×
  `dim_tiempo` vs `fct_uso_usuario_dia`, este último construido desde Silver) dan 1 093 235; la prueba corre en cada build.
- *¿Dónde se ve el linaje?* `dbt docs` (grafo), `dim_fuente` (121 objetos), columnas `fuente/archivo/ingest_date/
  kafka_offset` en Silver y Gold, y H7 como ejemplo ejecutable.

### 3.2 Documentación (5 pts)

**(a) Qué se hizo.** `README.md` completo (arquitectura, instalación desde cero, ejecución, estructura, entregables,
costos, seguridad, pruebas, cómo retomar). `docs/DECISIONS.md` con 10 ADR (contexto → decisión → alternativas →
consecuencias). `docs/PLAN.md` por fases con compuerta, `docs/PROGRESS.md`, `docs/METRICAS.md` (solo cifras medidas),
9 evidencias en `docs/evidence/`, `docs/RUBRICA_CHECKLIST.md`, esta guía. Historial: 45 commits en Conventional Commits en
español, uno por entregable (`git log --oneline`).

**(b) Por qué.** La rúbrica pide README, bitácora de decisiones e historial; y el proyecto debe poder retomarse por
cualquier integrante leyendo cuatro archivos.

**(c) Alternativa descartada.** Un solo documento largo: se desactualiza. Se prefirió evidencia por fase con cifras
medidas y ADR cortos.

**(d) Evidencia.** `README.md`, `docs/DECISIONS.md`, `git log`, `docs/evidence/`.

**(e) Preguntas probables.**
- *¿Cuánto cuesta esto al mes?* Estimado con precios de lista (`infra/README.md`): VM e2-standard-2 ~49 USD si está 24/7
  (~16 USD a 8 h/día), disco 30 GB ~3 USD, IP estática 3,65–7,30 USD, Secret Manager 0,24 USD, BigQuery ~0 (346 MB en
  Bronze y 3,6 M filas en Gold entran en el nivel gratuito de 10 GiB y 1 TiB de consulta). **Total ~56 USD/mes 24/7 o
  ~20–25 USD apagando la VM** (`make vm-stop`). Presupuesto de 60 USD con alertas al 25/50/75/90/100 %. Todo sale de los
  300 USD de crédito de prueba. El costo real acumulado aún no se ha exportado (pendiente en `docs/PROGRESS.md`).
- *¿Cómo retomo el proyecto en seis meses?* Leer en orden `CLAUDE.md` (memoria del proyecto), `docs/PLAN.md`,
  `docs/PROGRESS.md`, `docs/DECISIONS.md`; luego `make venv`, `make init`, `make vm-start`, `make vm-sync`.
- *¿Por qué el historial tiene un solo autor?* El repositorio se administró desde una sola máquina y sin remoto; la
  trazabilidad del trabajo está en los 45 commits por entregable y en las evidencias por fase.
- *¿Qué decisión cambiarías?* Ninguna de las 10; lo primero que añadiríamos es modelos incrementales para Silver y
  `dbt source freshness` (extras listados en `docs/PLAN.md`).

### 3.3 Seguridad (5 pts)

**(a) Qué se hizo.** `docs/governance/seguridad.md` con las cuatro decisiones: (1) **credenciales**: ninguna llave JSON;
ADC en la laptop y cuenta de servicio `sa-pipeline-vm` por servidor de metadata en la VM; mínimo privilegio por bucket,
dataset y secreto (`infra/main/iam.tf`); 4 secretos en Secret Manager; `gitleaks` sobre todo el historial: **0 hallazgos
en 44 commits** (`docs/evidence/gitleaks_report.json` = `[]`). (2) **Seudonimización**: HMAC-SHA256 con sal secreta de
32 bytes; la sal nunca aparece en el SQL (los bloques `k_ipad`/`k_opad` viven en `ops_secrets.hmac_key`, dataset solo
accesible por la SA; macro `dbt/macros/hmac_sha256.sql`); verificado BigQuery = Python; Gold sin llaves nativas
(`assert_gold_sin_llaves_nativas`). (3) **Quién ve qué**: IAM por dataset (analista/Tableau → `gold`; científico →
`features`; auditor → `silver`; catedrático → UI de Airflow con rol Viewer, 403 al escribir); HTTPS con Caddy + Let's
Encrypt; Kafka y Postgres sin puertos públicos; SSH solo por IAP. (4) **Retención**: detalle 24 meses, cuarentena 12,
agregados indefinido, padrón mientras activo + 24 meses.

**(b) Por qué.** ADR-007: un hash sin sal es reversible por diccionario sobre llaves de formato conocido; ADR-008 lo
demuestra con el propio dataset.

**(c) Alternativa descartada.** `DETERMINISTIC_ENCRYPT` con Cloud KMS (más robusto, añade KMS y complejidad); JS UDF con
la sal como argumento (la sal quedaría en el historial de jobs); hash simple SHA256 (reversible).

**(d) Evidencia.** `docs/governance/seguridad.md`, `docs/evidence/f0_infraestructura.md` (tabla de 403),
`docs/evidence/gitleaks_report.json`, `ingest/hmac_key_to_bq.py`, `infra/main/iam.tf`.

**(e) Preguntas probables.**
- *¿Por qué el hash de Aerómetro es un problema de seguridad?* Porque `user_hash = md5("am" + i)[:12]` no lleva sal y el
  espacio de entrada son 60 000 enteros: con 70 000 candidatos invertimos el 100 % (14 496 / 14 496) en una consulta SQL
  (`silver_am_hash_map`). Un operador que crea que "hasheó" a sus usuarios los está exponiendo. Por eso la Agencia usa
  HMAC con sal secreta: sin la sal no se puede construir el diccionario.
- *¿La sal aparece en el historial de jobs de BigQuery?* No: el macro la toma por subconsulta escalar de
  `ops_secrets.hmac_key`, así que el texto de la consulta solo contiene la referencia a la tabla. En la VM la sal nunca
  se escribe en disco (`vm/README.md`).
- *¿Qué ve el analista?* Solo `gold`: sabe que dos viajes son de la misma persona (seudónimo), no de qué tarjeta. El
  detalle con llave nativa (Silver) es solo para auditoría de fraude.
- *¿Qué pasa si rotan la sal?* Cambian todos los seudónimos: hay que reconstruir Gold y features (minutos, todo es
  `table`) y registrar un ADR. Mientras no rote, el seudónimo es estable entre corridas (idempotencia).
- *¿Cómo sé que no hay secretos en git?* `make scan-secrets` (gitleaks sobre todo el historial) → reporte vacío;
  `.gitignore` excluye `.env`, `*.tfvars`, `*.tfstate*`, `datos_red/`; el repo solo lleva `.env.example`.

---

## 3. Penalizaciones: cómo se evita cada una

| Penalización | Cómo se evita | Prueba automática | Evidencia |
|---|---|---|---|
| **Gold que lee Bronze → pierde 1.4** | Gold solo hace `ref()` a Silver, seeds u otro Gold; ningún `source()` en `dbt/models/gold/` | `tests/test_gold_lineage.py` sobre `manifest.json` (4 passed; corre en la tarea `pruebas_python` del DAG) | `docs/evidence/gold_resumen.md` §1, `docs/evidence/linaje_dbt.md`, grafo en `docs/evidence/dbt_docs/index.html` |
| **Descartar registros sin cuarentena → pierde media 1.3** | Toda fila rechazada va a `quarantine.registros_rechazados` con `registro_original`, `fuente`, `archivo`, `regla_id`, `motivo`, `ts_cuarentena`; Staging no filtra | `assert_staging_igual_bronze` (9 fuentes) y `assert_staging_igual_silver_mas_cuarentena` (1 730 184 = 1 718 271 + 11 913) | `docs/evidence/calidad_resumen.md` §3 y §5 |
| **Flujo no idempotente → pierde 1.5** | Manifiesto sha256, objetos deterministas, `table` en todas las capas, `fecha_referencia` fija, HMAC estable | `make demo-idempotencia` (`ingest/conteos_capas.py --comparar`); `tests/test_no_current_date.py` | Parciales: Bronze 121 = 121, Silver 17 tablas idénticas, Gold 3 590 561 = 3 590 561, features 56 848 = 56 848. DAG completo: `docs/evidence/idempotencia_<ts>.md`, pendiente de la corrida |
| **Tablero no rastreable → pierde media 2.1** | Columnas de linaje en Silver y Gold (`fuente`, `archivo`, `objeto_gcs`, `ingest_date`, `linea_num`, `kafka_offset`) + `dim_fuente` (121 objetos) + grafo de dbt | `analysis/h7_linaje_de_una_cifra.sql`: 725 = 388 + 337 en dos objetos `gs://` | `docs/tableau/GUIA_TABLERO.md` §9, `docs/evidence/tablero_resumen.md` |

Pregunta incómoda transversal: *"Si mañana borro el dataset `gold`, ¿qué pierdo?"* Nada: `make dbt-build` (o la tarea
`dbt_gold` del DAG) lo reconstruye desde Silver en ~2 min 45 s con los mismos 3 590 561 registros. *"¿Y si borro Bronze?"*
Se pierde el crudo; por eso Bronze es inmutable, acumulativo y con retención de 24 meses.

---

## 4. Glosario (20 términos)

| Término | Qué es en este proyecto |
|---|---|
| **Bronze** | Capa cruda: los archivos tal como llegaron, en `gs://cienciadatos-509301-lake/bronze/<fuente>/ingest_date=…/` (121 objetos, 346 MB), expuestos en BigQuery como tablas externas. Inmutable y acumulativa. |
| **Silver** | Capa limpia y validada en BigQuery: tipos correctos, reglas R01–R11 aplicadas, zonas conformadas, identidad unificada, llave nativa todavía presente (solo auditoría). 1 647 569 abordajes. |
| **Grano** | Qué representa una fila de una tabla de hechos. `fct_abordaje`: una validación de una tarjeta de un usuario en un modo, en una estación o parada, en un instante. |
| **Matriz del bus** | Tabla procesos de negocio (hechos) × dimensiones conformadas que muestra qué dimensiones comparte cada hecho (`docs/modelo/matriz_bus.md` §3). |
| **SCD2** | Dimensión de cambio lento tipo 2: cada cambio crea una versión nueva con `vigente_desde` / `vigente_hasta` / `es_vigente`; nada se sobrescribe. `silver_padron_scd2`: 28 844 versiones de 22 462 tarjetas. |
| **CDC** | Change Data Capture: log de operaciones INSERT/UPDATE/DELETE (`cdc_padron_usuarios.csv`, 31 050) que se aplica en orden de `seq` para reconstruir el estado del padrón. |
| **Idempotencia** | Ejecutar el flujo dos veces produce exactamente el mismo resultado: mismos objetos en Bronze, mismos conteos en todas las capas. |
| **HMAC** | Código de autenticación con clave: `SHA256((K⊕opad) ‖ SHA256((K⊕ipad) ‖ m))`. Con sal secreta, el seudónimo no se puede invertir por diccionario. |
| **Seudonimización** | Sustituir la llave de usuario por un seudónimo estable (`usuario_sk`) que permite contar "la misma persona" sin saber quién es. Se aplica antes de Gold. |
| **Hive partitioning** | Convención de carpetas `clave=valor` (`ingest_date=2026-09-20`) que BigQuery interpreta como partición de la tabla externa. |
| **Tabla externa** | Tabla de BigQuery que no copia los datos: lee directamente los objetos de GCS. Así Bronze se consulta sin duplicarlo. |
| **Offset de Kafka** | Posición secuencial de un mensaje dentro de una partición de un tópico. Los objetos de Bronze se nombran por rango de offsets (`offsets=000000005000-000000009999.jsonl`) y cada abordaje conserva su `kafka_offset`. |
| **KRaft** | Modo de Kafka sin ZooKeeper: el propio broker guarda los metadatos (un nodo combinado broker+controller en la VM, `apache/kafka:4.3.1`). |
| **LocalExecutor** | Ejecutor de Airflow que corre las tareas como procesos del scheduler, sin Redis ni workers; suficiente para una VM de 8 GB. |
| **Seed** | CSV versionado en el repo que dbt carga como tabla: `zonas`, `zonas_mapeo`, `franjas_horarias`, `feriados_gt`. Son catálogos de gobernanza. |
| **ref / source** | En dbt, `source()` apunta a una tabla externa al proyecto (Bronze); `ref()` apunta a otro modelo. Gold solo usa `ref()` a Silver o Gold. |
| **Factless fact** | Hecho sin medida numérica: registra que algo existe (`fct_cobertura_zona_modo`: 44 pares zona-modo con estación). Se cuenta la fila. |
| **Medida semi aditiva** | Se puede sumar por algunas dimensiones pero no por otras; típico de saldos (`tarjetas_activas_despues`: se suma entre usuarios, no en el tiempo). |
| **IAP** | Identity-Aware Proxy de GCP: túnel autenticado para SSH sin abrir el puerto 22 a internet (`gcloud compute ssh --tunnel-through-iap`). |
| **ADC** | Application Default Credentials: forma en que las librerías de Google encuentran credenciales sin llaves JSON (usuario en la laptop, cuenta de servicio por metadata en la VM). |

---

## 5. Reparto sugerido para la defensa

Cada integrante domina una parte y conoce el resto por esta guía: (1) ingesta y Bronze + orquestación (1.1, 1.5, demo);
(2) Staging/CDC y Silver/cuarentena (1.2, 1.3); (3) Gold, gobernanza y seguridad (1.4, 3.1, 3.3); (4) tablero,
recomendación y features (2.1, 2.2, 2.3). Todos: guion de 10 minutos, tabla "cifra → dónde sale" y penalizaciones.
