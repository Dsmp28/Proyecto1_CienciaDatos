### Conteos por capa · 2026-09-21T06:31:25+00:00

**bronze** (9 tablas, 1,730,184 filas)

| tabla | filas |
|---|---:|
| aerometro_boardings | 203,554 |
| am_estaciones | 14 |
| cdc_padron_usuarios | 31,050 |
| metroriel_viajes | 299,100 |
| mr_estaciones | 22 |
| tm_estaciones | 104 |
| transmetro_validaciones | 363,221 |
| transurbano_transacciones | 832,791 |
| tu_paradas | 328 |

**staging** (15 tablas, 1,869,850 filas)

| tabla | filas |
|---|---:|
| stg_aerometro_boardings | 203,554 |
| stg_am_estaciones | 14 |
| stg_catalogo_usuarios_am | 14,496 |
| stg_catalogo_usuarios_mr | 22,885 |
| stg_catalogo_usuarios_tm | 43,255 |
| stg_catalogo_usuarios_tu | 36,567 |
| stg_cdc_padron_usuarios | 31,050 |
| stg_metroriel_viajes | 299,100 |
| stg_mr_estaciones | 22 |
| stg_padron_cdc_aplicado | 22,462 |
| stg_padron_cdc_resumen | 1 |
| stg_tm_estaciones | 104 |
| stg_transmetro_validaciones | 363,221 |
| stg_transurbano_transacciones | 832,791 |
| stg_tu_paradas | 328 |

**silver** (19 tablas, 5,283,384 filas)

| tabla | filas |
|---|---:|
| feriados_gt | 13 |
| franjas_horarias | 24 |
| silver_abordajes | 1,647,569 |
| silver_aerometro_boardings | 203,554 |
| silver_am_hash_map | 70,000 |
| silver_estaciones | 468 |
| silver_metroriel_viajes | 295,511 |
| silver_padron_scd2 | 28,844 |
| silver_transmetro_validaciones | 362,106 |
| silver_transurbano_transacciones | 827,788 |
| silver_usuarios | 117,205 |
| val_aerometro_boardings | 203,554 |
| val_cdc_padron_usuarios | 31,050 |
| val_estaciones | 468 |
| val_metroriel_viajes | 299,100 |
| val_transmetro_validaciones | 363,221 |
| val_transurbano_transacciones | 832,791 |
| zonas | 26 |
| zonas_mapeo | 92 |

**quarantine** (2 tablas, 11,927 filas)

| tabla | filas |
|---|---:|
| registros_rechazados | 11,913 |
| resumen_por_regla | 14 |

**gold** (17 tablas, 3,590,561 filas)

| tabla | filas |
|---|---:|
| agg_cobertura_zona | 26 |
| agg_demanda_modo_zona_hora | 37,619 |
| agg_metroriel_zonas | 26 |
| agg_transbordo | 56,848 |
| agg_transbordo_resumen | 4 |
| dim_estacion | 468 |
| dim_fuente | 121 |
| dim_modo | 4 |
| dim_padron_historia | 28,844 |
| dim_tiempo | 1,080 |
| dim_usuario | 117,205 |
| dim_zona | 26 |
| fct_abordaje | 1,647,569 |
| fct_cambio_padron | 28,844 |
| fct_cobertura_zona_modo | 44 |
| fct_uso_usuario_dia | 1,376,322 |
| fct_viaje_metroriel | 295,511 |

**features** (2 tablas, 56,882 filas)

| tabla | filas |
|---|---:|
| diccionario_features | 34 |
| usuario_features | 56,848 |

**GCS `gs://cienciadatos-509301-lake/bronze/`**: 121 objetos, 309,266,388 bytes

| fuente | objetos | bytes |
|---|---:|---:|
| aerometro_boardings | 41 | 72,966,490 |
| am_estaciones | 1 | 687 |
| cdc_padron_usuarios | 1 | 2,149,136 |
| metroriel_viajes | 1 | 55,311,001 |
| mr_estaciones | 1 | 537 |
| tm_estaciones | 1 | 7,387 |
| transmetro_validaciones | 73 | 135,692,243 |
| transurbano_transacciones | 1 | 43,125,718 |
| tu_paradas | 1 | 13,189 |
