# Grafo de linaje de dbt (evidencia 3.1)

Generado con `dbt docs generate` el 2026-09-21. Artefactos en `docs/evidence/dbt_docs/` (`index.html`, `manifest.json`,
`catalog.json`); abrir con `cd dbt && dbt docs serve` o `python -m http.server` dentro de esa carpeta.

| Elemento | Cantidad |
|---|---:|
| Sources (tablas externas de Bronze) | 9 |
| Seeds (catálogos de gobernanza versionados) | 4 |
| Modelos staging / silver / quarantine / gold / features | 15 / 15 / 2 / 17 / 2 (51) |
| Pruebas (genéricas + singulares, incluidas las de seeds) | 510 |

Ejemplo de trazabilidad: `gold.agg_demanda_modo_zona_hora` (base de la hoja de demanda del tablero) depende de 43 nodos
y alcanza las 9 fuentes de Bronze. Desde cualquier cifra del tablero se llega al objeto crudo en GCS por
`fct_abordaje.archivo / objeto_gcs / linea_num / kafka_offset` → `dim_fuente` → `bronze.<fuente>` (`_FILE_NAME`), como
muestra `analysis/h7_linaje_de_una_cifra.sql`. La restricción "Gold solo lee Silver" se verifica sobre este mismo
`manifest.json` con `tests/test_gold_lineage.py`.

Escaneo de secretos del historial (`make scan-secrets`, gitleaks): 44 commits, sin hallazgos (`docs/evidence/gitleaks_report.json`).
