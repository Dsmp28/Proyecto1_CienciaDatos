# Checklist de la rúbrica → entregables en el repo

| Sección | Pts | Entregable exigido | Ruta en el repo | Estado |
|---|---|---|---|---|
| 1.1 Ingesta y Bronze | 8 | Scripts por vía | `ingest/batch_to_gcs.py`, `ingest/kafka_producer.py`, `ingest/kafka_consumer_gcs.py` | en curso |
| | | Tabla de conteos por archivo | `docs/evidence/conteos_bronze.md`, `docs/METRICAS.md` | en curso |
| | | Justificación de la vía de Transurbano y lake vs warehouse | `docs/DECISIONS.md` (ADR-002, ADR-003) | hecho |
| 1.2 Staging y CDC | 9 | Modelo CDC con conteo antes/después de los DELETE | `dbt/models/staging/`, `docs/METRICAS.md` | pendiente |
| | | Catálogos mínimos de llaves con conteo de usuarios únicos | `dbt/models/staging/` | pendiente |
| 1.3 Silver | 12 | Modelos Silver, cuarentena con motivo, conteo por regla | `dbt/models/silver/`, `dbt/models/quarantine/`, `docs/governance/reglas_calidad.md` | pendiente |
| 1.4 Gold | 15 | Grano, matriz del bus, diagrama, DDL, clasificación de medidas | `docs/modelo/matriz_bus.md`, `docs/modelo/modelo_gold.mmd`, `docs/modelo/ddl_gold.sql` | matriz hecha |
| 1.5 Orquestación | 5 | Evidencia de dos corridas con conteos idénticos | `airflow/dags/`, `docs/evidence/idempotencia_*.md` | pendiente |
| 2.1 Tablero | 16 | Tablero en Tableau sobre Gold | `docs/tableau/GUIA_TABLERO.md`, `docs/tableau/*.tds`, `analysis/*.sql` | pendiente |
| 2.2 Recomendación | 10 | Documento ≤ 2 páginas con cifras | `docs/RECOMENDACION.md` | pendiente |
| 2.3 Features | 7 | Tabla, diccionario, fecha de corte, frase de predicción | `dbt/models/features/`, `docs/features/` | pendiente |
| 3.1 Gobernanza | 8 | Diccionario de Gold, definiciones oficiales con dueño, grafo de linaje | `docs/governance/diccionario_gold.md`, `docs/governance/definiciones_oficiales.md`, `docs/evidence/dbt_docs/` | definiciones hechas |
| 3.2 Documentación | 5 | README, bitácora de decisiones, historial de git | `README.md`, `docs/DECISIONS.md`, `git log` | en curso |
| 3.3 Seguridad | 5 | Página con credenciales, seudonimización, quién ve qué, retención | `docs/governance/seguridad.md` | pendiente |
| Métricas | — | Volumen, Calidad, CDC, Rendimiento, Idempotencia, Cobertura | `docs/METRICAS.md` | en curso |
