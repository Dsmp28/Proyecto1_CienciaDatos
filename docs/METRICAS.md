# Métricas medidas

Todas las cifras de este documento son **medidas** (no estimadas) y provienen de `ops.ingest_manifest`,
`ops.run_metrics`, `quarantine.registros_rechazados` y las consultas de `analysis/`. Cada tabla indica la
corrida (`run_id`) y la fecha de medición. Categorías exigidas por el enunciado: Volumen, Calidad, CDC,
Rendimiento, Idempotencia y Cobertura.

## Volumen
### Filas de origen frente a filas en Bronze (1.1)
Medido el 2026-09-20 con `ingest/conteos_bronze.py` (COUNT(*) sobre las tablas externas de Bronze frente a `ops.ingest_manifest`).
Corridas: batch `manual-20260920T221154-400c84`, streaming `f1-streaming-20260921T042051`.

| archivo | vía | filas_origen | filas_bronze | diferencia | objetos en GCS |
|---|---|---:|---:|---:|---:|
| tm_estaciones.csv | batch | 104 | 104 | 0 | 1 |
| tu_paradas.csv | batch | 328 | 328 | 0 | 1 |
| mr_estaciones.csv | batch | 22 | 22 | 0 | 1 |
| am_estaciones.csv | batch | 14 | 14 | 0 | 1 |
| metroriel_viajes.jsonl | batch | 299 100 | 299 100 | 0 | 1 |
| transurbano_transacciones.csv | batch (ADR-003) | 832 791 | 832 791 | 0 | 1 |
| transmetro_validaciones.csv | streaming (Kafka) | 363 221 | 363 221 | 0 | 73 |
| aerometro_boardings.csv | streaming (Kafka) | 203 554 | 203 554 | 0 | 41 |
| cdc_padron_usuarios.csv | cdc | 31 050 | 31 050 | 0 | 1 |
| **Total** | | **1 730 184** | **1 730 184** | **0** | **121** |

Tamaño en Bronze: batch 137 MB (copia byte a byte); streaming 209 MB (72 966 490 + 135 692 243 bytes: cada línea viaja en una envolvente JSON con offset, archivo, línea y marcas de tiempo).

Rendimiento de la vía streaming en la VM (e2-standard-2, Kafka de un nodo): productor 363 221 msgs en 5,8 s (63 084 msg/s) y 203 554 en 2,1 s (96 971 msg/s); consumidor 566 775 mensajes → 114 objetos en 77,8 s. Regeneración y verificación de los 9 archivos en la VM: 1 min 46 s.

### Filas por capa (Bronze → Staging → Silver → Gold)
| Capa | Filas | Detalle |
|---|---:|---|
| Bronze (9 tablas externas) | 1 730 184 | igual al origen |
| Staging (15 tablas) | 1 869 850 | 1 730 184 de las 9 fuentes + padrón aplicado, resumen y 4 catálogos de llaves |
| Silver (`silver_abordajes`, grano abordaje) | 1 647 569 | TM 362 106 · TU 786 398 (solo cobros exitosos) · MR 295 511 · AM 203 554 |
| Silver (`silver_usuarios`) | 117 205 | TM 43 257 · TU 36 567 · MR 22 885 · AM 14 496; 100 % con identidad unificada |
| Cuarentena | 11 913 | ver Calidad |
| Gold (`fct_abordaje`) | 1 647 569 | = `silver_abordajes` (prueba `assert_abordajes_gold_igual_silver`) |
| Gold (`fct_viaje_metroriel`) | 295 511 | viajes cerrados |
| Gold (`fct_uso_usuario_dia`) | 1 376 322 | usuario × día × modo |
| Gold (`dim_usuario`) | 117 205 | seudonimizada, sin llave nativa |
| Features (`usuario_features`) | 56 848 | una fila por persona, corte 2026-07-16 |

## Calidad
### Registros en cuarentena por regla y fuente
Medido el 2026-09-20 en `quarantine.resumen_por_regla` (reglas en `docs/governance/reglas_calidad.md`; detalle en `docs/evidence/calidad_resumen.md`).

| Fuente | Regla | Motivo | Rechazados | Total fuente | % |
|---|---|---|---:|---:|---:|
| transmetro_validaciones | R01 | duplicado de torniquete | 1 115 | 363 221 | 0,307 |
| transurbano_transacciones | R02 | código de parada nulo | 4 186 | 832 791 | 0,503 |
| transurbano_transacciones | R03 | fecha posterior a la fecha de referencia | 817 | 832 791 | 0,098 |
| metroriel_viajes | R04 | viaje sin salida | 3 589 | 299 100 | 1,200 |
| cdc_padron_usuarios | R07 | llave de usuario nula (`SIN-TARJETA`) | 2 206 | 31 050 | 7,105 |
| aerometro_boardings, 4 catálogos | — | sin rechazos | 0 | 203 554 / 468 | 0 |
| **Total** | | | **11 913** | **1 730 184** | **0,688** |

Duplicados detectados: 1 115 (R01, filas completas repetidas por el torniquete; se conserva la primera aparición) y 0 duplicados de entrega en streaming (R10).
Diferencia frente a lo inyectado por el generador: R02 muestra 4 186 y no 4 189 porque 3 filas con parada nula tienen además fecha del futuro y se etiquetan con R03 (una fila, una regla).
Transacciones de Transurbano con cobro rechazado (`SALDO_INSUF` 33 112, `TARJETA_INVALIDA` 8 278): se conservan en Silver con su estado y no cuentan como viaje; no son registros inválidos.

### Conciliación por fuente (staging = silver + cuarentena), prueba `assert_staging_igual_silver_mas_cuarentena`
| Fuente | Staging | Silver | Cuarentena |
|---|---:|---:|---:|
| transmetro_validaciones | 363 221 | 362 106 | 1 115 |
| transurbano_transacciones | 832 791 | 827 788 | 5 003 |
| metroriel_viajes | 299 100 | 295 511 | 3 589 |
| aerometro_boardings | 203 554 | 203 554 | 0 |
| cdc_padron_usuarios | 31 050 | 28 844 (SCD2) | 2 206 |
| catálogos (4) | 468 | 468 | 0 |
| **Total** | **1 730 184** | **1 718 271** | **11 913** |

## CDC
### Altas, cambios y bajas aplicadas; tarjetas activas antes y después de los DELETE
Medido el 2026-09-20 en `staging.stg_padron_cdc_resumen` (log completo de 31 050 operaciones aplicado en orden de `seq`, ADR-009). Detalle y cuadre en `docs/evidence/cdc_resumen.md`.

| Métrica | Valor |
|---|---:|
| Operaciones en el log (INSERT / UPDATE / DELETE) | 31 050 (10 800 / 16 200 / 4 050) |
| Filas sin llave (`SIN-TARJETA`, a cuarentena R07) | 2 206 |
| Tarjetas distintas con llave | 22 462 |
| Altas aplicadas (primera operación INSERT) | 7 845 |
| Altas implícitas (UPDATE o DELETE sin INSERT previo) | 14 617 |
| INSERT repetidos sobre llave existente (aplicados como cambio) | 2 158 |
| Cambios aplicados (UPDATE) | 15 069 |
| Bajas aplicadas (estado final INACTIVA) | 2 993 |
| DELETE sin alta previa (tarjetas) | 3 301 |
| **Tarjetas activas antes de aplicar los DELETE** | **20 148** |
| **Tarjetas activas después de aplicar los DELETE** | **19 469** |

Los DELETE marcan la tarjeta como inactiva y conservan perfil y zona previos; 635 tarjetas recibieron un INSERT/UPDATE posterior a su DELETE y quedaron activas (la última operación manda).

### Catálogos mínimos de usuarios (llaves distintas en los archivos de operación)
| Operador | Llaves distintas | Filas de operación |
|---|---:|---:|
| Transmetro (`tarjeta`) | 43 255 | 363 221 |
| Transurbano (`num_tarjeta`) | 36 567 | 832 791 |
| MetroRiel (`card`) | 22 885 | 299 100 |
| Aerómetro (`user_hash`) | 14 496 | 203 554 |

## Rendimiento
### Duración por etapa (DAG `red_metropolitana` en la VM e2-standard-2; `ops.run_metrics`, metrica `duracion_s`)
Corridas `demo-idempotencia-20260921T001141-1` y `-2` (2026-09-21). Duración total: 588 s y 558 s.

| Etapa | Corrida 1 (s) | Corrida 2 (s) |
|---|---:|---:|
| generar_o_verificar_datos | 2,7 | 2,7 |
| ingesta_batch (7 archivos ya en manifiesto → omitidos) | 15,4 | 13,6 |
| ingesta_cdc | 10,1 | 8,3 |
| kafka_productor (omitido por manifiesto) | 6,5 | 6,1 |
| kafka_consumidor (lag 0, espera de inactividad 30 s) | 35,0 | 34,8 |
| tablas_externas_bronze | 14,9 | 13,1 |
| conciliar_bronze | 13,0 | 14,7 |
| publicar_clave_hmac | 4,7 | 4,1 |
| dbt_deps / dbt_seed | 6,0 / 23,9 | 5,3 / 26,5 |
| dbt_staging (15 modelos + 79 pruebas) | 70,1 | 72,7 |
| dbt_silver (17 modelos + 161 pruebas) | 128,3 | 132,0 |
| dbt_gold (17 modelos + 197 pruebas) | 130,9 | 126,8 |
| dbt_features (2 modelos + 58 pruebas) | 44,9 | 41,4 |
| dbt_docs | 39,6 | 38,5 |
| pruebas_python | 7,3 | 7,1 |
| registrar_metricas | 16,5 | 12,7 |

Primera carga de Bronze (F1, sin manifiesto previo): batch 7 archivos ≈ 2 min; streaming productor 5,8 s + 2,1 s, consumidor 77,8 s (566 775 mensajes); regeneración y verificación de datos 1 min 46 s.

### Tamaño en almacenamiento por capa (`ops.run_metrics`, metrica `bytes_capa`, corrida 2)
| Capa | Filas | Tamaño |
|---|---:|---:|
| Bronze (GCS, 121 objetos) | 1 730 184 | 294,9 MiB |
| Staging (15 tablas) | 1 869 850 | 836,7 MiB |
| Silver (17 tablas, incluidas 6 de validación con todas las filas) | 5 283 384 | 2 414,2 MiB |
| Cuarentena (2 tablas) | 11 927 | 3,9 MiB |
| Gold (17 tablas) | 3 590 561 | 1 439,9 MiB |
| Features (2 tablas) | 56 882 | 17,5 MiB |

### Tiempo de las consultas del tablero (`analysis/*.sql`, sin caché, `bq show -j`)
| Hoja | Cifra principal | Job (ms) | Bytes |
|---|---|---:|---:|
| H1 demanda modo × hora | 55,05 % de abordajes en hora pico | 230 | 0,79 MB |
| H2 demanda por zona | Zona 17 = 148 554 (9,02 %) | 1 367 | 0,81 MB |
| H3 cobertura | 11 de 26 zonas sin servicio | 203 | 8,18 MB |
| H4 transbordo | 72,98 % multimodal | 190 | 1,32 MB |
| H5 caso MetroRiel | 5 zonas del trazado = top 5 (43,68 %) | 267 | 0,30 MB |
| H6 KPIs | viajes junio 1 093 235; 53 820 personas activas | 1 173 | 157,7 MB |
| H7 linaje de una cifra | 725 viajes → 2 objetos de Bronze | 173 | 4,23 MB |
| H8 estación candidata | Zona 17: 23 704 personas con ≥ 2 modos | 4 118 | 256,5 MB |
| viajes_del_mes A / B | 1 093 235 = 1 093 235 | 662 / 345 | 168,1 / 93,2 MB |

## Idempotencia
### Conteos de la primera y la segunda corrida (`make demo-idempotencia`, 2026-09-21)
Dos corridas completas del DAG en la nube (`demo-idempotencia-20260921T001141-1` y `-2`, 588 s y 558 s), 17 de 17 tareas
en success en ambas. `ingest/conteos_capas.py` comparó **64 tablas** de bronze, staging, silver, quarantine, gold y features
más los objetos y bytes de `gs://cienciadatos-509301-lake/bronze/`: **todo idéntico** (121 objetos, 309 266 388 bytes;
`fct_abordaje` 1 647 569 = 1 647 569; `registros_rechazados` 11 913 = 11 913; `usuario_features` 56 848 = 56 848).
Evidencia completa: `docs/evidence/idempotencia_20260921T001141.md` (+ instantáneas JSON de cada corrida).
Cómo se logra: manifiesto por sha256 en Bronze (segunda corrida: 9 archivos omitidos, 0 objetos nuevos), objetos de
streaming con nombre determinista por ventana de offsets, capas reconstruidas por completo con `fecha_referencia` fija.

## Cobertura
### Zonas con y sin servicio; usuarios que usan más de un modo
Medido en `gold.agg_cobertura_zona` y `gold.agg_transbordo_resumen` (detalle en `docs/evidence/gold_resumen.md`).

| Métrica | Valor |
|---|---:|
| Zonas del universo conformado (`dim_zona`) | 26 |
| Zonas con servicio de al menos un modo | 15 |
| Zonas sin servicio de ningún modo | 11 (Zonas 2, 3, 5, 14, 15, 16, 19, 21, 24, 25 y Santa Catarina Pinula) |
| Zonas por modo | Transmetro 15 · Transurbano 15 · Aerómetro 9 · MetroRiel 5 |
| Personas con abordajes (identidad unificada, ADR-008) | 56 848 |
| Usan 1 modo / 2 / 3 / 4 | 15 363 (27,0 %) / 25 048 (44,1 %) / 14 004 (24,6 %) / 2 433 (4,3 %) |
| **Usuarios que usan más de un sistema** | **41 485 (73,0 %)** |
| Viajes del mes (junio 2026), dos caminos independientes | 1 093 235 = 1 093 235 |
