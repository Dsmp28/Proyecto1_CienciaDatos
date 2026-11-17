# Conteos de Bronze vs. LEEME de la cátedra

Generado por `ingest/evidencia_p2.py` · run_id `desde-cero-20261112T005918` · 2026-11-12T07:16:46+00:00

| archivo | vía | filas esperadas (LEEME) | filas cargadas (Bronze) | diferencia | ok |
|---|---|---:|---:|---:|:---:|
| tm_estaciones.csv | batch | 104 | 104 | 0 | sí |
| tu_paradas.csv | batch | 328 | 328 | 0 | sí |
| mr_estaciones.csv | batch | 22 | 22 | 0 | sí |
| am_estaciones.csv | batch | 14 | 14 | 0 | sí |
| metroriel_viajes.jsonl | batch | 590,844 | 791,554 | 200,710 | NO |
| transurbano_transacciones.csv | batch | 1,635,788 | 2,186,773 | 550,985 | NO |
| transmetro_validaciones.csv | streaming | 713,786 | 958,288 (distintas: 958,288) | 244,502 | NO |
| aerometro_boardings.csv | streaming | 387,053 | 517,835 (distintas: 517,835) | 130,782 | NO |
| cdc_padron_usuarios.csv | cdc | 77,636 | 102,952 | 25,316 | NO |
| **Total** | | **3,405,575** | **4,557,870** | **1,152,295** | NO |

Resultado: HAY DIFERENCIAS.
