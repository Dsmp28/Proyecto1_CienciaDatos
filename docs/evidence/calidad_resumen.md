# Evidencia F3 · Silver, calidad y cuarentena

Corrida: `dbt build --select tag:silver tag:quarantine` (dbt-core 1.12.5, BigQuery `cienciadatos-509301`, `us-central1`),
2026-09-20, `fecha_referencia = 2026-07-16`, `run_id = manual`. Fuente de las cifras: consultas directas a
`silver.*` y `quarantine.*` tras la corrida 1 (la corrida 2 produjo conteos idénticos, ver §6).

## 1. Resultado del build (dos corridas)

| Corrida | Modelos | Pruebas | Resultado | Tiempo |
|---|---|---|---|---|
| 1 | 17 tablas (6 `val_*`, 9 `silver_*`, 2 `quarantine.*`) | 161 (155 genéricas + 6 singulares) | PASS=178 WARN=0 ERROR=0 SKIP=0 | 2 min 15 s (135,0 s) |
| 2 | 17 tablas | 161 | PASS=178 WARN=0 ERROR=0 SKIP=0 | 2 min 33 s (153,4 s) |

`dbt parse` sin errores (solo la advertencia esperada por las carpetas vacías gold/features/ops).
`pytest -q tests/test_no_current_date.py`: 1 passed (ningún modelo, macro ni prueba usa la fecha del sistema).

## 2. Cuarentena por regla y fuente (`quarantine.resumen_por_regla`)

| Fuente | Regla | Motivo | Rechazados | Total fuente (staging) | % |
|---|---|---|---:|---:|---:|
| transmetro_validaciones | R01 | R01 duplicado de torniquete | 1 115 | 363 221 | 0,307 |
| transmetro_validaciones | TOTAL | Total en cuarentena | 1 115 | 363 221 | 0,307 |
| transurbano_transacciones | R02 | R02 codigo de parada nulo | 4 186 | 832 791 | 0,503 |
| transurbano_transacciones | R03 | R03 fecha posterior a la fecha de referencia | 817 | 832 791 | 0,098 |
| transurbano_transacciones | TOTAL | Total en cuarentena | 5 003 | 832 791 | 0,601 |
| metroriel_viajes | R04 | R04 viaje sin salida | 3 589 | 299 100 | 1,200 |
| metroriel_viajes | TOTAL | Total en cuarentena | 3 589 | 299 100 | 1,200 |
| aerometro_boardings | TOTAL | Total en cuarentena | 0 | 203 554 | 0,000 |
| cdc_padron_usuarios | R07 | R07 llave de usuario nula | 2 206 | 31 050 | 7,105 |
| cdc_padron_usuarios | TOTAL | Total en cuarentena | 2 206 | 31 050 | 7,105 |
| tm_estaciones | TOTAL | Total en cuarentena | 0 | 104 | 0,000 |
| tu_paradas | TOTAL | Total en cuarentena | 0 | 328 | 0,000 |
| mr_estaciones | TOTAL | Total en cuarentena | 0 | 22 | 0,000 |
| am_estaciones | TOTAL | Total en cuarentena | 0 | 14 | 0,000 |

Total en `quarantine.registros_rechazados`: **11 913** filas. Duplicados detectados (R01 + R10): 1 115 + 0.
Reglas sin ocurrencias (R05, R06, R08, R09, R10, R11): 0, como anticipa `reglas_calidad.md` ("no inyectado").

### Contraste con lo esperado en `docs/governance/reglas_calidad.md`

| Regla | Esperado | Observado | Diferencia | Explicación |
|---|---:|---:|---:|---|
| R01 duplicado de torniquete | 1 115 | 1 115 | 0 | 363 221 filas, 362 106 `validacion_id` distintos; se conserva la primera aparición por `(linea_num, kafka_offset)`. |
| R02 parada nula | 4 189 | 4 186 | −3 | Hay 4 189 filas con `cod_parada` vacío, pero 3 de ellas tienen además fecha del futuro. Por el orden de evaluación (R03 antes que R02/R06) esas 3 se etiquetan R03. Una fila, una regla: 4 186 + 817 = 5 003 = filas de Transurbano en cuarentena. |
| R03 fecha del futuro | 817 | 817 | 0 | Todas de Transurbano (+400 días: `2027-08-19` máximo). Ninguna en TM, MR ni AM. |
| R04 viaje sin salida | 3 589 | 3 589 | 0 | `exit = null` en el JSON. |
| R07 llave nula | 2 206 | 2 206 | 0 | Todas del padrón (`SIN-TARJETA`); ninguna fuente de operación tiene llave nula. |

## 3. Conciliación por fuente: staging = silver + cuarentena (prueba `assert_staging_igual_silver_mas_cuarentena`)

| Fuente | Staging | Silver | Cuarentena | Diferencia |
|---|---:|---:|---:|---:|
| transmetro_validaciones | 363 221 | 362 106 | 1 115 | 0 |
| transurbano_transacciones | 832 791 | 827 788 | 5 003 | 0 |
| metroriel_viajes | 299 100 | 295 511 | 3 589 | 0 |
| aerometro_boardings | 203 554 | 203 554 | 0 | 0 |
| cdc_padron_usuarios (silver = `silver_padron_scd2`) | 31 050 | 28 844 | 2 206 | 0 |
| tm_estaciones (silver = `silver_estaciones`, modo TM) | 104 | 104 | 0 | 0 |
| tu_paradas (modo TU) | 328 | 328 | 0 | 0 |
| mr_estaciones (modo MR) | 22 | 22 | 0 | 0 |
| am_estaciones (modo AM) | 14 | 14 | 0 | 0 |

Ningún registro se descarta: 1 730 184 filas de staging = 1 718 271 en Silver + 11 913 en cuarentena.

## 4. Silver

### 4.1 `silver_abordajes` por modo (grano: un abordaje; total 1 647 569)

| Modo | Abordajes | Llaves distintas | Personas (`usuario_base_id`) | Monto Q | Fechas | Nota |
|---|---:|---:|---:|---:|---|---|
| TM | 362 106 | 43 255 | 43 255 | 296 397,00 | 2026-06-01 → 2026-07-15 | 90 434 son `TRANSBORDO` (transbordo interno, válido) |
| TU | 786 398 | 36 567 | 36 567 | 930 162,35 | 2026-06-01 → 2026-07-15 | solo `es_cobro_exitoso`; los 33 112 `SALDO_INSUF` + 8 278 `TARJETA_INVALIDA` (41 390) quedan en `silver_transurbano_transacciones` y no cuentan como viaje |
| MR | 295 511 | 22 885 | 22 885 | 807 132,00 | 2026-06-01 → 2026-07-15 | la entrada de cada viaje cerrado; el viaje completo está en `silver_metroriel_viajes` |
| AM | 203 554 | 14 496 | 14 496 | 712 439,00 | 2026-06-01 → 2026-07-15 | hora local convertida desde UTC |

`usuario_base_id` es NOT NULL en el 100 % de los abordajes (prueba `not_null_silver_abordajes_usuario_base_id` en verde).
Nota: `reglas_calidad.md` cita 41 649 cobros no exitosos sobre staging; en Silver quedan 41 390 porque 259 de ellos
cayeron antes en R02/R03 (parada vacía o fecha del futuro).

### 4.2 `silver_usuarios` (117 205 filas: una por (modo, llave))

| Modo | Usuarios | Con `usuario_unificado_sk` | En padrón | Solo en padrón (sin operación) | ACTIVA | INACTIVA |
|---|---:|---:|---:|---:|---:|---:|
| TM | 43 257 | 43 257 | 17 432 | 2 | 15 096 | 2 336 |
| TU | 36 567 | 36 567 | 14 637 | 0 | 12 668 | 1 969 |
| MR | 22 885 | 22 885 | 9 213 | 0 | 7 975 | 1 238 |
| AM | 14 496 | 14 496 | 5 397 | 0 | 4 668 | 729 |

| `metodo_vinculo` | Usuarios | Sin `usuario_base_id` |
|---|---:|---:|
| formato (TM/TU/MR por regex) | 102 709 | 0 |
| inversion_md5 (AM por `silver_am_hash_map`) | 14 496 | 0 |

Vínculo entre modos: 117 205 / 117 205 (100 %) tienen `usuario_unificado_sk`. Las 2 llaves TM "solo en padrón" son
tarjetas `TC-` del CDC que nunca aparecen en la operación de Transmetro (reciben `n_registros_operacion = 0`).
`en_padron` se une por `usuario_base_id` (ADR-009): por eso usuarios TU/MR/AM también reciben perfil, zona y estado.

Usuarios con más de un modo (`COUNT(DISTINCT modo_id)` por `usuario_unificado_sk`, solo llaves con operación):

| Modos usados | Personas |
|---:|---:|
| 1 | 15 363 |
| 2 | 25 048 |
| 3 | 14 004 |
| 4 | 2 433 |
| **Total personas** | **56 848** |
| **Más de un modo** | **41 485 (73,0 %)** |

Coincide exactamente con el resultado medido en ADR-008 (56 848 / 41 485 / 25 048 / 14 004 / 2 433).

### 4.3 `silver_padron_scd2`

| Métrica | Valor |
|---|---:|
| Filas (una por operación con llave) | 28 844 |
| Tarjetas distintas | 22 462 |
| Filas vigentes (`es_vigente`) | 22 462 (una por tarjeta; prueba singular en verde) |
| Vigentes ACTIVA / INACTIVA | 19 469 / 2 993 |
| `commit_ts_fuera_de_orden` | 103 (la siguiente `seq` tiene `commit_ts` anterior; la vigencia sigue `seq`) |
| `alta_implicita` (primera op no es INSERT) | 14 617 |
| `alta_repetida` (INSERT sobre llave existente) | 2 158 |
| `baja_sin_alta_previa` (DELETE sin INSERT anterior) | 3 430 operaciones |

Coincide con `docs/evidence/cdc_resumen.md` (14 617 altas implícitas, 2 158 altas repetidas, 3 430 DELETE sin alta previa,
19 469 activas y 2 993 inactivas). La fila vigente de cada tarjeta coincide en `estado`, `perfil` y `zona_residencia`
con `stg_padron_cdc_aplicado` (prueba `assert_padron_scd2_vigente_igual_aplicado` en verde).

### 4.4 `silver_estaciones` (468 filas, `zona_id` NOT NULL en todas)

| Modo | Estaciones/paradas | Zonas conformadas distintas |
|---|---:|---:|
| TM | 104 | 15 |
| TU | 328 | 15 |
| MR | 22 | 5 (12, 8, 1, 6, 17) |
| AM | 14 | 9 |

Ningún valor de zona/sector/district sin mapear (R05 = 0; `assert_zonas_mapeadas` en verde).

## 5. Muestra de `quarantine.registros_rechazados` (una fila por fuente y regla)

| fuente | regla_id | llave_usuario | linea_num | kafka_offset | registro_original (recortado) | run_id | ts_cuarentena |
|---|---|---|---:|---:|---|---|---|
| cdc_padron_usuarios | R07 | SIN-TARJETA | – | – | `1000,2026-06-02T09:27:00,UPDATE,SIN-TARJETA,trabajador,Zona 12,ACTIVA` | manual | 2026-07-16 00:00:00 UTC |
| metroriel_viajes | R04 | MR…53756 | – | – | `{"trip_id": 100046, "card": "MR…53756", "entry": {"station": 7, …` | manual | 2026-07-16 00:00:00 UTC |
| transmetro_validaciones | R01 | TC-…46121 | 10046 | 10045 | `10008,TC-…46121,TM-L12-02,L12,2026-06-02 05:27:16,1.00,ENTRADA` | manual | 2026-07-16 00:00:00 UTC |
| transurbano_transacciones | R02 | …045574 | – | – | `01/06/2026,04:00:30,…045574,,R-102,130,1` | manual | 2026-07-16 00:00:00 UTC |
| transurbano_transacciones | R03 | …006929 | – | – | `01/08/2027,04:09:02,…006929,R-104-3,R-104,130,2` | manual | 2026-07-16 00:00:00 UTC |

`ts_cuarentena` = `TIMESTAMP(fecha_referencia)` porque `var('run_ts')` no se pasó (corrida manual); Airflow la pasará
por `--vars` junto con `run_id`. Nunca `CURRENT_TIMESTAMP`. `linea_num`/`kafka_offset` solo existen en streaming.

## 6. Idempotencia: conteos de las dos corridas

| Tabla | Corrida 1 | Corrida 2 |
|---|---:|---:|
| quarantine.registros_rechazados | 11 913 | 11 913 |
| quarantine.resumen_por_regla | 14 | 14 |
| silver.silver_abordajes | 1 647 569 | 1 647 569 |
| silver.silver_aerometro_boardings | 203 554 | 203 554 |
| silver.silver_am_hash_map | 70 000 | 70 000 |
| silver.silver_estaciones | 468 | 468 |
| silver.silver_metroriel_viajes | 295 511 | 295 511 |
| silver.silver_padron_scd2 | 28 844 | 28 844 |
| silver.silver_transmetro_validaciones | 362 106 | 362 106 |
| silver.silver_transurbano_transacciones | 827 788 | 827 788 |
| silver.silver_usuarios | 117 205 | 117 205 |
| silver.val_aerometro_boardings | 203 554 | 203 554 |
| silver.val_cdc_padron_usuarios | 31 050 | 31 050 |
| silver.val_estaciones | 468 | 468 |
| silver.val_metroriel_viajes | 299 100 | 299 100 |
| silver.val_transmetro_validaciones | 363 221 | 363 221 |
| silver.val_transurbano_transacciones | 832 791 | 832 791 |

`diff` de ambas listas: vacío (idénticas). Todas las tablas se reconstruyen completas (`table`), las llaves son
deterministas (hash del registro crudo, `validacion_id`, `trip_id`, `boarding_id`, HMAC estable) y ninguna consulta usa la
fecha del sistema.

## 7. Pruebas de dbt incluidas en el build (161)

- Singulares (`dbt/tests/silver/`): `assert_staging_igual_silver_mas_cuarentena`, `assert_zonas_mapeadas`,
  `assert_fechas_dentro_de_referencia`, `assert_padron_scd2_una_vigente_por_tarjeta`,
  `assert_padron_scd2_vigente_igual_aplicado`, `assert_am_hash_invertible`.
- Genéricas: `unique`/`not_null` en `silver_abordajes.abordaje_id`, `silver_usuarios.usuario_sk`, `silver_estaciones.estacion_sk`,
  `silver_am_hash_map.user_hash`, ids nativos por modo; `dbt_utils.unique_combination_of_columns` en
  `silver_usuarios (modo_id, llave_nativa)`, `silver_padron_scd2 (tarjeta, seq)`, `resumen_por_regla (fuente, regla_id)`;
  `relationships` de `estacion_sk` → `silver_estaciones` y `zona_id` → `zonas`; `accepted_values` de `modo_id`, `regla_id`,
  `estado_padron`, `metodo_vinculo`, `tipo_validacion`, `estado_desc`, `op`, `estado`; `not_null` en `zona_id`,
  `fecha_hora_local`, `monto_q`, `usuario_base_id` de `silver_abordajes`.
