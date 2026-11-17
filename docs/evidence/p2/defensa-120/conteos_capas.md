### Conteos por capa · 2026-11-17T03:59:07+00:00

**bronze** (9 tablas, 4,605,216 filas)

| tabla | filas |
|---|---:|
| aerometro_boardings | 524,860 |
| am_estaciones | 14 |
| cdc_padron_usuarios | 102,749 |
| metroriel_viajes | 799,374 |
| mr_estaciones | 22 |
| tm_estaciones | 104 |
| transmetro_validaciones | 971,206 |
| transurbano_transacciones | 2,206,559 |
| tu_paradas | 328 |

**staging** (15 tablas, 4,814,811 filas)

| tabla | filas |
|---|---:|
| stg_aerometro_boardings | 524,860 |
| stg_am_estaciones | 14 |
| stg_catalogo_usuarios_am | 18,674 |
| stg_catalogo_usuarios_mr | 29,036 |
| stg_catalogo_usuarios_tm | 46,122 |
| stg_catalogo_usuarios_tu | 50,136 |
| stg_cdc_padron_usuarios | 102,749 |
| stg_metroriel_viajes | 799,374 |
| stg_mr_estaciones | 22 |
| stg_padron_cdc_aplicado | 65,626 |
| stg_padron_cdc_resumen | 1 |
| stg_tm_estaciones | 104 |
| stg_transmetro_validaciones | 971,206 |
| stg_transurbano_transacciones | 2,206,559 |
| stg_tu_paradas | 328 |

**silver** (20 tablas, 11,718,090 filas)

| tabla | filas |
|---|---:|
| feriados_gt | 13 |
| franjas_horarias | 24 |
| silver_abordajes | 3,232,200 |
| silver_aerometro_boardings | 387,053 |
| silver_am_hash_map | 100,000 |
| silver_estaciones | 468 |
| silver_metroriel_viajes | 583,745 |
| silver_padron_scd2 | 95,506 |
| silver_transmetro_validaciones | 711,684 |
| silver_transurbano_transacciones | 1,626,075 |
| silver_unidad_tarjetas_corte | 212,167 |
| silver_usuarios | 163,821 |
| val_aerometro_boardings | 524,860 |
| val_cdc_padron_usuarios | 102,749 |
| val_estaciones | 468 |
| val_metroriel_viajes | 799,374 |
| val_transmetro_validaciones | 971,206 |
| val_transurbano_transacciones | 2,206,559 |
| zonas | 26 |
| zonas_mapeo | 92 |

**quarantine** (2 tablas, 1,200,702 filas)

| tabla | filas |
|---|---:|
| registros_rechazados | 1,200,685 |
| resumen_por_regla | 17 |

**gold** (17 tablas, 6,226,534 filas)

| tabla | filas |
|---|---:|
| agg_cobertura_zona | 26 |
| agg_demanda_modo_zona_hora | 74,420 |
| agg_metroriel_zonas | 26 |
| agg_transbordo | 72,304 |
| agg_transbordo_resumen | 4 |
| dim_estacion | 468 |
| dim_fuente | 228 |
| dim_modo | 4 |
| dim_padron_historia | 95,506 |
| dim_tiempo | 2,880 |
| dim_usuario | 163,821 |
| dim_zona | 26 |
| fct_abordaje | 3,232,200 |
| fct_cambio_padron | 95,506 |
| fct_cobertura_zona_modo | 44 |
| fct_uso_usuario_dia | 1,905,326 |
| fct_viaje_metroriel | 583,745 |

**features** (8 tablas, 5,875,034 filas)

| tabla | filas |
|---|---:|
| churn_dataset | 152,291 |
| churn_diccionario | 39 |
| churn_etiqueta | 152,291 |
| churn_eventos | 5,180,503 |
| churn_features | 152,291 |
| churn_poblacion | 165,281 |
| diccionario_features | 34 |
| usuario_features | 72,304 |

**GCS `gs://cienciadatos-509301-lake/bronze/`**: 307 objetos, 821,523,438 bytes

| fuente | objetos | bytes |
|---|---:|---:|
| aerometro_boardings | 105 | 188,668,589 |
| am_estaciones | 1 | 687 |
| cdc_padron_usuarios | 1 | 7,145,814 |
| metroriel_viajes | 1 | 148,003,016 |
| mr_estaciones | 1 | 537 |
| tm_estaciones | 1 | 7,387 |
| transmetro_validaciones | 195 | 363,391,638 |
| transurbano_transacciones | 1 | 114,292,581 |
| tu_paradas | 1 | 13,189 |
