# Bitácora del Proyecto 2 (¿Quién deja de usar la red?)

Registro cronológico de corridas y decisiones. Toda corrida reportada debe poder repetirse con el comando indicado.
La evaluación única del corte B se registra aquí con un marcador HTML que escribe `ml/evaluar_b.py` (constante `MARCADOR`).

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

<!-- EVALUACION_B -->
## Evaluación en el corte B

- Fecha: 2026-11-12T04:36:54+00:00
- Commit: `29e8b14ac5202d7dd81a4fd4f812583a28e2fce0`
- Modelo: `churn_persona_v1.0.0.joblib` (sha256 `350b8fcadae48144571b18ade1a6b8e8cd25b10ab7b0a2e6ab704602bd68770b`)
- Umbral (metadatos del modelo): 0.3400; unidades en B: 50483; tasa de churn en B: 0.1022

AP 0.4214 | ROC-AUC 0.8591 | Brier 0.0731 | precisión 0.4357 | recall 0.4497

Matriz de confusión (filas = real 0/1, columnas = predicho 0/1):

| | pred 0 | pred 1 |
|---|---|---|
| real 0 | 42319 | 3005 |
| real 1 | 2839 | 2320 |

Ganancia en Q (15·TP − 5·contactados): 8175.00 en total; 161.94 por cada 1 000 personas.

## Cierre de la fase 2 (2026-11-11, hora local)

| Commit | Qué se hizo | Comando / evidencia |
|---|---|---|
| `41f6eb1` | 2.3: segmentos del corte A (k = 2 por silueta 0,1766; PCA 2D 37,9 %) y acciones | `make ml-segmentos` → `docs/evidence/p2/segmentos*.md`, `acciones.md` |
| `7c888dc` | 2.1 y umbral: HistGradientBoosting AP 0,4680 ± 0,0205 con los mismos pliegues; u* = 0,340 (Q12 200 fuera de muestra); modelo v1.0.0 | `make ml-entrenar FASE=2` (229 s) → `docs/evidence/p2/fase2_*.md`, `umbral.md`, `calibracion.md` |
| `29e8b14` | La cabecera de esta bitácora contenía el texto del marcador y la guardia abortaba; se corrigió la cabecera (la guardia no se tocó ni se forzó) | — |
| `29e8b14` | 2.2: evaluación única en B (entrada de arriba) | `make ml-test-b` → `docs/evidence/p2/test_b.md`, `ml/artefactos/evaluacion_b.json` |
| `e8af355` | 2.4: CSV oficial del corte C (49 853 filas, 6 052 a contactar); respaldo CSV idéntico al de BigQuery; ensayo de invariancia en B (datos hasta el 30-jul contra completos): 0 diferencias en 50 483 filas | `python predecir.py --datos docs/P2_datos_red/datos_red --fecha-corte 2026-08-30`; `docs/evidence/p2/invariancia_B.md` |
| `4a7bde5` | Informe de la fase 2, ficha del modelo, presentación, guía de entrega | `docs/P2/` |
| cierre `fase-2` | Corrida completa del DAG en la VM (`desde-cero-20261111T223850`, sin vaciado): 20 tareas en success, 622 s de reloj; `ml.ml_predecir_corte_c` (19 s) y `ml.ml_invariancia` en success; el CSV generado en la VM es idéntico byte a byte al oficial | `scripts/desde_cero.sh --sin-reset`; `docs/evidence/p2/tiempos_fase2.md`, `invariancia_C_vm.md` |

