# Conteos de Bronze vs. manifiesto

Generado por `ingest/conteos_bronze.py` · run_id `manual-20260920T221637-d096f3` · 2026-09-21T04:17:05+00:00

| archivo | vía | filas_origen | filas_bronze | diferencia | ok |
|---|---|---:|---:|---:|:---:|
| tm_estaciones.csv | batch | 104 | 104 | 0 | sí |
| tu_paradas.csv | batch | 328 | 328 | 0 | sí |
| mr_estaciones.csv | batch | 22 | 22 | 0 | sí |
| am_estaciones.csv | batch | 14 | 14 | 0 | sí |
| metroriel_viajes.jsonl | batch | 299,100 | 299,100 | 0 | sí |
| transurbano_transacciones.csv | batch | 832,791 | 832,791 | 0 | sí |
| transmetro_validaciones.csv | streaming | - | - | - | sí (sin ingesta en el manifiesto) |
| aerometro_boardings.csv | streaming | - | - | - | sí (sin ingesta en el manifiesto) |
| cdc_padron_usuarios.csv | cdc | 31,050 | 31,050 | 0 | sí |

Diferencia total: 0. Resultado: OK.
