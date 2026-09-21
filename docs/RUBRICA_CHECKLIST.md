# Checklist de la rúbrica → entregables en el repo

Actualizado el 2026-09-20. "hecho" = existe la ruta y la cifra o prueba que lo demuestra; "hecho (`docs/evidence/idempotencia_20260921T001141.md`)" solo
para la demo de idempotencia del DAG completo (corriendo ahora en la nube) y para el tablero en Tableau Desktop (lo
construye el equipo a mano siguiendo `docs/tableau/GUIA_TABLERO.md`). Guía para la defensa: `docs/GUIA_DEFENSA.md`.

| Sección | Pts | Entregable exigido | Ruta en el repo | Estado y prueba |
|---|---|---|---|---|
| 1.1 Ingesta y Bronze | 8 | Scripts por vía (batch, streaming, CDC) | `ingest/batch_to_gcs.py`, `ingest/kafka_producer.py`, `ingest/kafka_consumer_gcs.py`, `ingest/bronze_external_tables.py` | **hecho**: 9 archivos en Bronze, 121 objetos, 346 MB; segunda corrida 0 objetos nuevos (`docs/evidence/f1_ingesta_bronze.md`) |
| | | Tabla de conteos por archivo (origen vs Bronze) | `docs/evidence/conteos_bronze.md`, `docs/METRICAS.md` §Volumen | **hecho**: 1 730 184 = 1 730 184, diferencia 0 en los 9 archivos |
| | | Justificación de la vía de Transurbano y lake vs warehouse | `docs/DECISIONS.md` (ADR-002, ADR-003) | **hecho** |
| 1.2 Staging y CDC | 9 | Modelo CDC con conteo de activas antes/después de los DELETE | `dbt/models/staging/stg_cdc_padron_usuarios.sql`, `stg_padron_cdc_aplicado.sql`, `stg_padron_cdc_resumen.sql`; `docs/evidence/cdc_resumen.md`; `docs/METRICAS.md` §CDC | **hecho**: 31 050 ops; activas 20 148 antes → 19 469 después; 9 identidades aritméticas cuadran |
| | | Catálogos mínimos de llaves con conteo de usuarios únicos | `dbt/models/staging/stg_catalogo_usuarios_{tm,tu,mr,am}.sql` | **hecho**: 43 255 / 36 567 / 22 885 / 14 496 llaves; solo llave, operador y n_registros |
| | | Staging tipado con linaje, sin filtrar | `dbt/models/staging/stg_*.sql`, `dbt/tests/staging/assert_staging_igual_bronze.sql` | **hecho**: 15 tablas, 1 869 850 filas; prueba PASS en las 9 fuentes |
| 1.3 Silver | 12 | Reglas de calidad documentadas antes del código | `docs/governance/reglas_calidad.md` | **hecho**: R01–R11 con orden de evaluación y esperado vs observado |
| | | Modelos Silver + cuarentena con motivo y registro original | `dbt/models/silver/`, `dbt/models/quarantine/registros_rechazados.sql`, `resumen_por_regla.sql` | **hecho**: 17 tablas; 11 913 en cuarentena (R01 1 115, R02 4 186, R03 817, R04 3 589, R07 2 206); 161 pruebas PASS = 178 (`docs/evidence/calidad_resumen.md`) |
| | | Conciliación staging = silver + cuarentena | `dbt/tests/silver/assert_staging_igual_silver_mas_cuarentena.sql`, `docs/METRICAS.md` §Calidad | **hecho**: 1 730 184 = 1 718 271 + 11 913 por fuente |
| | | SCD2 del padrón, identidad unificada, zonas conformadas | `dbt/models/silver/silver_padron_scd2.sql`, `silver_usuarios.sql`, `silver_am_hash_map.sql`, `silver_estaciones.sql`, `dbt/seeds/` | **hecho**: 28 844 versiones / 22 462 vigentes; 117 205 usuarios 100 % con `usuario_unificado_sk`; R05 = 0 |
| 1.4 Gold | 15 | Grano declarado, matriz del bus, clasificación de medidas | `docs/modelo/matriz_bus.md` | **hecho** (ADR-004) |
| | | Diagrama y DDL | `docs/modelo/modelo_gold.mmd`, `docs/modelo/ddl_gold.sql` | **hecho** |
| | | Dimensiones conformadas y hechos con usuario seudonimizado | `dbt/models/gold/` (7 `dim_*`, 5 `fct_*`, 5 `agg_*`) | **hecho**: 17 tablas, 3 590 561 filas; `fct_abordaje` 1 647 569 = Silver; 197 pruebas PASS = 214; `assert_gold_sin_llaves_nativas` PASS (`docs/evidence/gold_resumen.md`) |
| | | Gold nunca lee Bronze ni Staging | `tests/test_gold_lineage.py`, `dbt/dbt_project.yml` | **hecho**: 4 passed sobre `manifest.json`; corre en el DAG (`pruebas_python`) |
| | | Diccionario de datos de Gold | `docs/governance/diccionario_gold.md` (generado por `scripts/exportar_diccionario.py`) | **hecho**: 17 tablas, tipos reales de BigQuery, medidas clasificadas |
| 1.5 Orquestación | 5 | DAG con reintentos, bitácora y métricas por etapa | `airflow/dags/red_metropolitana_dag.py`, `ingest/run_metrics.py`, `tests/test_dag.py` | **hecho**: 18 tareas, 2 reintentos con backoff, `ops.run_metrics`, `doc_md` con la idempotencia por etapa; Airflow 3.3.2 en verde en la VM (`docs/evidence/f0_infraestructura.md`) |
| | | Evidencia de dos corridas del DAG completo con conteos idénticos | `scripts/demo_idempotencia.sh`, `ingest/conteos_capas.py`, `docs/evidence/idempotencia_<ts>.md` | hecho: `docs/evidence/idempotencia_20260921T001141.md` (64 tablas + 121 objetos idénticos; 17/17 tareas en success × 2) |
| 2.1 Tablero | 16 | Fuente de datos y guía hoja por hoja sobre Gold | `docs/tableau/red_metropolitana_gold.tds`, `docs/tableau/GUIA_TABLERO.md`, `docs/tableau/README.md` | **hecho** (insumos): 6 hojas + dashboard, campos calculados, cifra esperada por hoja |
| | | SQL de verificación con tiempos medidos | `analysis/h1…h8*.sql`, `analysis/README.md`, `docs/evidence/tablero_resumen.md` | **hecho**: 10 consultas, 0,17–4,1 s, 0,3–256 MB, sin caché |
| | | Cifra rastreable al archivo crudo | `analysis/h7_linaje_de_una_cifra.sql`, `docs/tableau/GUIA_TABLERO.md` §9 | **hecho**: 725 = 388 + 337 en 2 objetos `gs://` de Bronze |
| | | Tablero construido en Tableau Desktop | (archivo `.twb` a entregar por el equipo) | **pendiente de evidencia**: se construye a mano con la guía; cada cifra debe coincidir con el SQL |
| 2.2 Recomendación | 10 | Documento ≤ 2 páginas con cifra y consulta por afirmación | `docs/RECOMENDACION.md` | **hecho**: 4 hallazgos, 4 recomendaciones, dónde sí / dónde no, límites; cada cifra cita `analysis/*.sql` |
| 2.3 Features | 7 | Tabla desde Silver, fecha de corte, diccionario, frase de predicción, pruebas anti-fuga | `dbt/models/features/`, `docs/features/README.md`, `docs/features/diccionario_features.md`, `dbt/tests/features/` | **hecho**: 56 848 × 34, corte 2026-07-16, 58 pruebas PASS = 60, corte alternativo verificado (`docs/evidence/features_resumen.md`) |
| 3.1 Gobernanza | 8 | Diccionario de Gold | `docs/governance/diccionario_gold.md` | **hecho** |
| | | Definiciones oficiales con dueño por dominio | `docs/governance/definiciones_oficiales.md` | **hecho**: viaje, usuario activo, 7 dueños; prueba de fuego 1 093 235 = 1 093 235 (`assert_viajes_del_mes_dos_caminos`) |
| | | Grafo de linaje | `docs/evidence/dbt_docs/index.html`, `docs/evidence/linaje_dbt.md` | **hecho**: 9 sources, 4 seeds, 51 modelos, 510 pruebas |
| 3.2 Documentación | 5 | README completo | `README.md` | **hecho**: arquitectura, instalación desde cero, ejecución, estructura, entregables, costos, seguridad, pruebas, cómo retomar |
| | | Bitácora de decisiones | `docs/DECISIONS.md` | **hecho**: ADR-001…010 |
| | | Historial de git | `git log` | **hecho**: 45 commits en Conventional Commits en español |
| | | Guía de defensa | `docs/GUIA_DEFENSA.md` | **hecho**: guion de 10 min, 20 cifras con su fuente, preguntas por sección, penalizaciones, glosario |
| 3.3 Seguridad | 5 | Página con credenciales, seudonimización, quién ve qué, retención | `docs/governance/seguridad.md`, `docs/DECISIONS.md` (ADR-007) | **hecho**: 0 llaves JSON, 4 secretos, HMAC verificado BigQuery = Python, IAM por dataset, Viewer 403, retención 24/12 meses |
| | | Sin secretos en el historial | `scripts/scan_secrets.sh`, `docs/evidence/gitleaks_report.json` | **hecho**: gitleaks, 44 commits, 0 hallazgos |
| Métricas | — | Volumen, Calidad, CDC, Rendimiento, Idempotencia, Cobertura | `docs/METRICAS.md` | hecho: las 6 categorías con números medidos |

## Definición de terminado del proyecto

- [x] **Infraestructura reproducible con Terraform desde cero** — `infra/bootstrap` (14 recursos) + `infra/main` (49 + 2); outputs y pila Docker en `docs/evidence/f0_infraestructura.md`.
- [x] **DAG en verde en la nube, visible con usuario de solo lectura** — corridas `demo-idempotencia-20260921T001141-1/-2` con 17/17 tareas en success; usuario `catedratico` (Viewer, 403 al escribir) verificado en `docs/evidence/f0_infraestructura.md`
- [x] **`dbt build` en verde con las pruebas listadas** — staging 94/94; silver + quarantine 161 pruebas PASS = 178; gold 197 pruebas PASS = 214; features 58 pruebas PASS = 60 (`docs/evidence/cdc_resumen.md`, `calidad_resumen.md`, `gold_resumen.md`, `features_resumen.md`).
- [x] **Demo de idempotencia (`make demo-idempotencia`)** — `docs/evidence/idempotencia_20260921T001141.md`: 64 tablas y 121 objetos de Bronze idénticos entre las dos corridas (588 s y 558 s)
- [x] **`docs/METRICAS.md` completas (6 categorías)** — Volumen, Calidad, CDC, Rendimiento, Idempotencia y Cobertura con números medidos
- [x] **Grafo de linaje** — `docs/evidence/dbt_docs/` (`index.html`, `manifest.json`, `catalog.json`) y `docs/evidence/linaje_dbt.md`.
- [x] **Entregables mapeados a la rúbrica** — este archivo y `README.md` §Dónde están los entregables.
- [x] **Insumos de Tableau** — `docs/tableau/red_metropolitana_gold.tds`, `docs/tableau/GUIA_TABLERO.md`, `analysis/h1…h8*.sql` con cifras y tiempos. (El tablero en Tableau Desktop se construye a mano: pendiente.)
- [x] **Guía de defensa** — `docs/GUIA_DEFENSA.md`.
- [x] **Sin secretos en git** — `docs/evidence/gitleaks_report.json` = `[]` (44 commits); `.gitignore` excluye `.env`, `*.tfvars`, `*.tfstate*`, `datos_red/`.
- [x] **Reporte de costo acumulado y recursos encendidos** — `docs/PROGRESS.md` (sección Costo): consumo medido por recurso y horas; la cifra de la consola de facturación se anota cuando Google la publique (retraso de ~24 h)
