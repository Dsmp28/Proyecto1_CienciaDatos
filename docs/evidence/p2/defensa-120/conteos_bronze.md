# Conteos de Bronze vs. LEEME de la cátedra

Generado por `ingest/evidencia_p2.py` · run_id `desde-cero-20261116T214214` · 2026-11-17T03:58:41+00:00

| archivo | vía | filas esperadas (LEEME) | filas cargadas (Bronze) | diferencia | ok |
|---|---|---:|---:|---:|:---:|
| tm_estaciones.csv | batch | 104 | 104 | 0 | sí |
| tu_paradas.csv | batch | 328 | 328 | 0 | sí |
| mr_estaciones.csv | batch | 22 | 22 | 0 | sí |
| am_estaciones.csv | batch | 14 | 14 | 0 | sí |
| metroriel_viajes.jsonl | batch | 590,844 | 799,374 | 208,530 | NO |
| transurbano_transacciones.csv | batch | 1,635,788 | 2,206,559 | 570,771 | NO |
| transmetro_validaciones.csv | streaming | 713,786 | 971,206 (distintas: 971,206) | 257,420 | NO |
| aerometro_boardings.csv | streaming | 387,053 | 524,860 (distintas: 524,860) | 137,807 | NO |
| cdc_padron_usuarios.csv | cdc | 77,636 | 102,749 | 25,113 | NO |
| **Total** | | **3,405,575** | **4,605,216** | **1,199,641** | NO |

Resultado: HAY DIFERENCIAS.
