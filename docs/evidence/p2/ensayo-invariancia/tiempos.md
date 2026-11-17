# Tiempos por etapa

Generado por `ingest/evidencia_p2.py` · run_id `desde-cero-20261112T005918` · 2026-11-12T07:16:46+00:00

| etapa | segundos |
|---|---:|
| generar_o_verificar_datos | 8.2 |
| publicar_clave_hmac | 6.5 |
| ingesta_bronze.ingesta_cdc | 12.7 |
| ingesta_bronze.ingesta_batch | 22.2 |
| ingesta_bronze.ingesta_streaming.kafka_productor | 24.6 |
| ingesta_bronze.ingesta_streaming.kafka_consumidor | 121.8 |
| tablas_externas_bronze | 22.9 |
| conciliar_bronze | 22.2 |
| transformacion_dbt.dbt_deps | 4.6 |
| transformacion_dbt.dbt_seed | 20.4 |
| transformacion_dbt.dbt_staging | 85.8 |
| transformacion_dbt.dbt_silver | 115.7 |
| transformacion_dbt.dbt_gold | 113.5 |
| transformacion_dbt.dbt_features | 39.8 |
| transformacion_dbt.dbt_churn | 65.3 |
| transformacion_dbt.dbt_docs | 31.2 |
| pruebas_python | 54.1 |
| ml.ml_predecir_corte_c | 22.1 |
| ml.ml_invariancia | 1.3 |
| registrar_metricas | 13.5 |
| **TOTAL (suma de tareas)** | **808.6** |
| **TOTAL (reloj del DagRun)** | **780.3** |
