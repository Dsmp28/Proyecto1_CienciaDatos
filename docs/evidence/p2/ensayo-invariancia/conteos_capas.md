### Conteos por capa · 2026-11-12T07:17:13+00:00

**bronze** (9 tablas, 4,557,870 filas)

| tabla | filas |
|---|---:|
| aerometro_boardings | 517,835 |
| am_estaciones | 14 |
| cdc_padron_usuarios | 102,952 |
| metroriel_viajes | 791,554 |
| mr_estaciones | 22 |
| tm_estaciones | 104 |
| transmetro_validaciones | 958,288 |
| transurbano_transacciones | 2,186,773 |
| tu_paradas | 328 |

**staging** (15 tablas, 4,741,063 filas)

| tabla | filas |
|---|---:|
| stg_aerometro_boardings | 517,835 |
| stg_am_estaciones | 14 |
| stg_catalogo_usuarios_am | 16,930 |
| stg_catalogo_usuarios_mr | 26,414 |
| stg_catalogo_usuarios_tm | 41,344 |
| stg_catalogo_usuarios_tu | 45,685 |
| stg_cdc_padron_usuarios | 102,952 |
| stg_metroriel_viajes | 791,554 |
| stg_mr_estaciones | 22 |
| stg_padron_cdc_aplicado | 52,819 |
| stg_padron_cdc_resumen | 1 |
| stg_tm_estaciones | 104 |
| stg_transmetro_validaciones | 958,288 |
| stg_transurbano_transacciones | 2,186,773 |
| stg_tu_paradas | 328 |

**silver** (20 tablas, 11,654,543 filas)

| tabla | filas |
|---|---:|
| feriados_gt | 13 |
| franjas_horarias | 24 |
| silver_abordajes | 3,232,200 |
| silver_aerometro_boardings | 387,053 |
| silver_am_hash_map | 100,000 |
| silver_estaciones | 468 |
| silver_metroriel_viajes | 583,745 |
| silver_padron_scd2 | 95,704 |
| silver_transmetro_validaciones | 711,684 |
| silver_transurbano_transacciones | 1,626,075 |
| silver_unidad_tarjetas_corte | 212,167 |
| silver_usuarios | 147,422 |
| val_aerometro_boardings | 517,835 |
| val_cdc_padron_usuarios | 102,952 |
| val_estaciones | 468 |
| val_metroriel_viajes | 791,554 |
| val_transmetro_validaciones | 958,288 |
| val_transurbano_transacciones | 2,186,773 |
| zonas | 26 |
| zonas_mapeo | 92 |

**quarantine** (2 tablas, 1,153,158 filas)

| tabla | filas |
|---|---:|
| registros_rechazados | 1,153,141 |
| resumen_por_regla | 17 |

**gold** (17 tablas, 6,210,531 filas)

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
| dim_padron_historia | 95,704 |
| dim_tiempo | 2,880 |
| dim_usuario | 147,422 |
| dim_zona | 26 |
| fct_abordaje | 3,232,200 |
| fct_cambio_padron | 95,704 |
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

**GCS `gs://cienciadatos-509301-lake/bronze/`**: 303 objetos, 811,110,381 bytes

| fuente | objetos | bytes |
|---|---:|---:|
| aerometro_boardings | 104 | 186,139,037 |
| am_estaciones | 1 | 687 |
| cdc_padron_usuarios | 1 | 7,129,032 |
| metroriel_viajes | 1 | 146,553,715 |
| mr_estaciones | 1 | 537 |
| tm_estaciones | 1 | 7,387 |
| transmetro_validaciones | 192 | 358,551,033 |
| transurbano_transacciones | 1 | 112,715,764 |
| tu_paradas | 1 | 13,189 |
