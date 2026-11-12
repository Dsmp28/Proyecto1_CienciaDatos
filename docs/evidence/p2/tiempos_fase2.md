# Tiempos por etapa

Generado por `ingest/evidencia_p2.py` · run_id `desde-cero-20261111T223850` · 2026-11-12T04:50:05+00:00

| etapa | segundos |
|---|---:|
| generar_o_verificar_datos | 6.9 |
| ingesta_bronze.ingesta_streaming.kafka_productor | 5.9 |
| ingesta_bronze.ingesta_cdc | 8.2 |
| ingesta_bronze.ingesta_batch | 12.4 |
| publicar_clave_hmac | 3.0 |
| ingesta_bronze.ingesta_streaming.kafka_consumidor | 35.3 |
| tablas_externas_bronze | 17.3 |
| conciliar_bronze | 11.9 |
| transformacion_dbt.dbt_deps | 7.9 |
| transformacion_dbt.dbt_seed | 19.0 |
| transformacion_dbt.dbt_staging | 60.8 |
| transformacion_dbt.dbt_silver | 109.8 |
| transformacion_dbt.dbt_gold | 109.8 |
| transformacion_dbt.dbt_features | 41.5 |
| transformacion_dbt.dbt_churn | 63.3 |
| transformacion_dbt.dbt_docs | 30.0 |
| pruebas_python | 53.3 |
| ml.ml_predecir_corte_c | 19.4 |
| ml.ml_invariancia | 1.6 |
| registrar_metricas | 12.3 |
| **TOTAL (suma de tareas)** | **629.4** |
| **TOTAL (reloj del DagRun)** | **622.4** |
