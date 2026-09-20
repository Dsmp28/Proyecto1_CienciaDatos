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
### Duración por etapa, tamaño en almacenamiento por capa, tiempo de las consultas del tablero
*Pendiente (F5, F6).*

## Idempotencia
### Conteos de la primera y la segunda corrida
*Pendiente (F5): `make demo-idempotencia`, evidencia en `docs/evidence/`.*

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
