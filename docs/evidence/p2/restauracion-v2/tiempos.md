# Tiempos por etapa

Generado por `ingest/evidencia_p2.py` · run_id `desde-cero-20261116T220008` · 2026-11-17T04:16:47+00:00

| etapa | segundos |
|---|---:|
| generar_o_verificar_datos | 7.9 |
| ingesta_bronze.ingesta_cdc | 11.3 |
| publicar_clave_hmac | 5.3 |
| ingesta_bronze.ingesta_batch | 18.7 |
| ingesta_bronze.ingesta_streaming.kafka_productor | 22.4 |
| ingesta_bronze.ingesta_streaming.kafka_consumidor | 104.4 |
| tablas_externas_bronze | 21.5 |
| conciliar_bronze | 17.0 |
| transformacion_dbt.dbt_deps | 7.3 |
| transformacion_dbt.dbt_seed | 22.2 |
| transformacion_dbt.dbt_staging | 63.0 |
| transformacion_dbt.dbt_silver | 116.0 |
| transformacion_dbt.dbt_gold | 115.0 |
| transformacion_dbt.dbt_features | 39.4 |
| transformacion_dbt.dbt_churn | 65.3 |
| transformacion_dbt.dbt_docs | 33.9 |
| pruebas_python | 60.3 |
| ml.ml_predecir_corte_c | 22.8 |
| ml.ml_invariancia | 1.2 |
| registrar_metricas | 14.3 |
| **TOTAL (suma de tareas)** | **769.4** |
| **TOTAL (reloj del DagRun)** | **748.7** |
