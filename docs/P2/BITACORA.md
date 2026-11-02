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
