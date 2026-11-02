### Conteos por capa · 2026-11-02T03:59:39+00:00

**bronze** (9 tablas, 3,405,575 filas)

| tabla | filas |
|---|---:|
| aerometro_boardings | 387,053 |
| am_estaciones | 14 |
| cdc_padron_usuarios | 77,636 |
| metroriel_viajes | 590,844 |
| mr_estaciones | 22 |
| tm_estaciones | 104 |
| transmetro_validaciones | 713,786 |
| transurbano_transacciones | 1,635,788 |
| tu_paradas | 328 |

**staging** (15 tablas, 3,588,768 filas)

| tabla | filas |
|---|---:|
| stg_aerometro_boardings | 387,053 |
| stg_am_estaciones | 14 |
| stg_catalogo_usuarios_am | 16,930 |
| stg_catalogo_usuarios_mr | 26,414 |
| stg_catalogo_usuarios_tm | 41,344 |
| stg_catalogo_usuarios_tu | 45,685 |
| stg_cdc_padron_usuarios | 77,636 |
| stg_metroriel_viajes | 590,844 |
| stg_mr_estaciones | 22 |
| stg_padron_cdc_aplicado | 52,819 |
| stg_padron_cdc_resumen | 1 |
| stg_tm_estaciones | 104 |
| stg_transmetro_validaciones | 713,786 |
| stg_transurbano_transacciones | 1,635,788 |
| stg_tu_paradas | 328 |

**silver** (20 tablas, 10,478,670 filas)

| tabla | filas |
|---|---:|
| feriados_gt | 13 |
| franjas_horarias | 24 |
| silver_abordajes | 3,232,200 |
| silver_aerometro_boardings | 387,053 |
| silver_am_hash_map | 100,000 |
| silver_estaciones | 468 |
| silver_metroriel_viajes | 583,745 |
| silver_padron_scd2 | 72,126 |
| silver_transmetro_validaciones | 711,684 |
| silver_transurbano_transacciones | 1,626,075 |
| silver_unidad_tarjetas_corte | 212,167 |
| silver_usuarios | 147,422 |
| val_aerometro_boardings | 387,053 |
| val_cdc_padron_usuarios | 77,636 |
| val_estaciones | 468 |
| val_metroriel_viajes | 590,844 |
| val_transmetro_validaciones | 713,786 |
| val_transurbano_transacciones | 1,635,788 |
| zonas | 26 |
| zonas_mapeo | 92 |

**quarantine** (2 tablas, 24,438 filas)

| tabla | filas |
|---|---:|
| registros_rechazados | 24,424 |
| resumen_por_regla | 14 |

**gold** (17 tablas, 6,162,655 filas)

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
| dim_padron_historia | 72,126 |
| dim_tiempo | 2,160 |
| dim_usuario | 147,422 |
| dim_zona | 26 |
| fct_abordaje | 3,232,200 |
| fct_cambio_padron | 72,126 |
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

**GCS `gs://cienciadatos-509301-lake/bronze/`**: 228 objetos, 605,526,776 bytes

| fuente | objetos | bytes |
|---|---:|---:|
| aerometro_boardings | 78 | 139,044,426 |
| am_estaciones | 1 | 687 |
| cdc_padron_usuarios | 1 | 5,386,252 |
| metroriel_viajes | 1 | 109,365,069 |
| mr_estaciones | 1 | 537 |
| tm_estaciones | 1 | 7,387 |
| transmetro_validaciones | 143 | 266,983,436 |
| transurbano_transacciones | 1 | 84,725,793 |
| tu_paradas | 1 | 13,189 |
