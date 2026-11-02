# Bitácora del Proyecto 2 (¿Quién deja de usar la red?)

Registro cronológico de corridas y decisiones. Toda corrida reportada debe poder repetirse con el comando indicado.
La evaluación única del corte B se registra aquí con el marcador `<!-- EVALUACION_B -->` (la escribe `ml/evaluar_b.py`).

| Fecha (local) | Commit | Qué se hizo | Comando / evidencia |
|---|---|---|---|
| 2026-11-01 | `a9ffb72`…`279bddd` | F0: enunciado y LEEME; huellas v2 (`ingest/expected_hashes.json`, 9 archivos = LEEME); landing en el lake; reset confirmado y `desde_cero.sh`; dependencias de ML fijadas; `fecha_referencia` 2026-08-30 y tope de identidad 100 000; target `recorte`; ADR-012/013 | `make landing-subir VERSION=v2` → `gs://cienciadatos-509301-lake/landing/datos_red/v2/` (10 objetos, 257,5 MiB) |
| 2026-11-01 | `9038692`, `bde4952` | Modelos dbt de churn (eventos, población, etiqueta, features ≤ 28 d, dataset, diccionario), recorte en staging, pruebas; seudónimo por tarjeta en lugar de la llave nativa; tarea `dbt_churn` en el DAG | `dbt parse`; `pytest` 76 ✓ |
| 2026-11-01 | `13840bc`, `6d8d4de`, `2263785` | Paquete `ml/` fase 1 y 2, `predecir.py`, invariancia, prueba de recorte, tareas `ml` del DAG (todo probado con datos sintéticos) | `pytest` 118 ✓ |
| 2026-11-01 | `fe6a7a6`, `bde4952` | Hallazgos de la revisión de seguridad corregidos: nombres de landing solo del catálogo; sin llaves nativas en `features` | — |
| 2026-11-01 | — | Imagen de Airflow reconstruida (constraints limitadas a `apache-airflow*`: la rama de constraints cambió y chocaba con dbt-core) | `make vm-sync && make vm-up` |
| 2026-11-01 | — | OK del propietario al vaciado; `make desde-cero CONFIRMAR=BORRAR-cienciadatos-509301` (reset de P1 + carga v2) | `docs/evidence/p2/reset_*.md`, `conteos_bronze.md`, `tiempos.md` (pendiente de completar al terminar) |
| 2026-11-01 | `bda04fc`, `eb42c69`, `3102775` | Tres defectos reales de "desde cero" corregidos: selección indirecta cautelosa en dbt; 409 al crear `ops` en paralelo; matplotlib y `predecir.py` en la VM | corridas `desde-cero-20261101T203117` (fallo en staging), `…T205808` (fallo en churn: prueba con llave nativa), `…T212525` (éxito tras limpiar `pruebas_python`) |
| 2026-11-01 | `deac113` | 1.1 cerrado: Bronze = LEEME (3 405 575, diferencia 0); tiempos por etapa (877 s) | `docs/evidence/p2/conteos_bronze.md`, `tiempos.md` |
| 2026-11-01 | `681ef8c`, `f08a88d` | 1.2 cerrado: población A/B/C, costo de la unidad | `analysis/p2_poblacion.sql`, `analysis/p2_costo_unidad.sql` |
| 2026-11-01 | `4752076` | 1.4: primera corrida de la fase 1 (594 s) sobre el dataset previo a la corrección de redondeo | `docs/evidence/p2/fase1_*.md` |
| 2026-11-01 | `acf425d` | 1.3 cerrado: prueba de recorte 0 diferencias; borrador ingenuo con 4 fugas; medias con sumas exactas | `make prueba-recorte` |
| 2026-11-01 | cierre `fase-1` | Reentrenamiento de la fase 1 sobre el dataset definitivo (mismos folds): métricas idénticas (AP 0,4459 ± 0,0160), 564 s | `make ml-entrenar FASE=1` → `docs/evidence/p2/fase1_*.md`, `ml/artefactos/fase1_resultados.json` |
