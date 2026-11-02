# Tiempos por etapa

Generado por `ingest/evidencia_p2.py` · run_id `desde-cero-20261101T212525` · 2026-11-02T03:59:15+00:00

| etapa | segundos |
|---|---:|
| generar_o_verificar_datos | 6.3 |
| ingesta_bronze.ingesta_cdc | 11.2 |
| publicar_clave_hmac | 8.4 |
| ingesta_bronze.ingesta_batch | 22.9 |
| ingesta_bronze.ingesta_streaming.kafka_productor | 26.0 |
| ingesta_bronze.ingesta_streaming.kafka_consumidor | 107.5 |
| tablas_externas_bronze | 21.1 |
| conciliar_bronze | 17.6 |
| transformacion_dbt.dbt_deps | 5.5 |
| transformacion_dbt.dbt_seed | 21.5 |
| transformacion_dbt.dbt_staging | 66.4 |
| transformacion_dbt.dbt_silver | 122.1 |
| transformacion_dbt.dbt_gold | 120.0 |
| transformacion_dbt.dbt_features | 41.3 |
| transformacion_dbt.dbt_churn | 91.7 |
| transformacion_dbt.dbt_docs | 102.7 |
| registrar_fallo | 3.7 |
| pruebas_python | 64.6 |
| registrar_metricas | 16.7 |
| **TOTAL (suma de tareas)** | **877.3** |
