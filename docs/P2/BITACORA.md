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

## Auditoría posterior a la entrega (2026-11-11)

| Qué se revisó | Resultado | Evidencia |
|---|---|---|
| Reproducibilidad en un entorno nuevo: clon de la etiqueta `fase-2`, entorno virtual creado solo con `requirements.txt`, `predecir.py --origen csv` | CSV del corte C idéntico byte a byte al oficial; 115 pruebas pasan | README §Proyecto 2, "En otra máquina" |
| Procedimiento de la prueba de invariancia en vivo | La guía indicaba disparar el DAG con el zip nuevo sin vaciar; eso habría duplicado los registros de las fuentes sin llave de negocio y cambiado las predicciones. Corregido: se corre con el comando único y vaciado (ADR-018); `scripts/desde_cero.sh` compara al final el CSV de la VM con el oficial | `docs/GUIA_DEFENSA.md` §P2.2; ADR-018 |
| Ficha del modelo contra los campos del enunciado | Faltaba la sección de fugas revisadas; agregada | `docs/P2/FICHA_MODELO.md` |
| Métricas obligatorias | Faltaban precisión y recall junto al umbral en `docs/METRICAS.md`; agregadas | `docs/METRICAS.md` §Proyecto 2 |
| Evaluación de B | Una sola (commit `29e8b14`); no se repitió ni se ajustó nada después | entrada de arriba |
| Predicciones del corte C | Sin cambios: mismo archivo, mismo modelo v1.0.0 | `git log -- predicciones/` |

## Ensayo y prueba de invariancia con 30 días más de datos (2026-11-12 y 2026-11-16)

| Fecha (local) | Commit | Qué se hizo | Resultado | Evidencia |
|---|---|---|---|---|
| 2026-11-11/12 | `d71bfbf` | Ensayo con un conjunto fabricado (v2 intacto más 30 días anexados). Primera corrida desde un entorno vacío: falló `dbt_features` porque el borrador ingenuo de la auditoría (`churn_features_ingenuo`) entraba al build de features y depende de tablas de churn que se construyen después | Defecto real del comando único (existía desde que se agregó ese modelo); corregido excluyendo `tag:auditoria_recorte` del flujo, con prueba | `tests/test_seleccion_dbt.py` |
| 2026-11-12 | `8d3cfeb` | Segunda corrida: falló `pruebas_python` porque la prueba nueva buscaba archivos que no están montados en el contenedor | Corregida (se omite donde el archivo no existe) | `tests/test_seleccion_dbt.py` |
| 2026-11-12 | `8d3cfeb` | Tercera corrida: las predicciones de C difirieron (548 puntajes, 59 decisiones, 7 personas de más). Causa: el conjunto fabricado elegía los registros de Aerómetro por fecha UTC y colocó 778 abordajes en la noche local del 29 de agosto, antes del corte | No era fuga del pipeline sino un defecto del conjunto de ensayo: eran datos nuevos anteriores a t. Corregido el fabricador (fecha local) | `scripts/fabricar_datos_ensayo.py` |
| 2026-11-12 | `8d3cfeb` | Cuarta corrida, desde un entorno vacío, con el conjunto corregido (`desde-cero-20261112T005918`) | 20 tareas en éxito; CSV de C **idéntico**: 49 853 filas, 0 diferencias | `docs/evidence/p2/ensayo-invariancia/` |
| 2026-11-16 | `8d3cfeb` + cambios de la entrega final | **Datos de 120 días de la cátedra** (`P2_datos_red_defensa_120dias.zip`, hasta el 28 de septiembre). Comprobado antes de cargar: los 9 archivos de 90 días son prefijo exacto de los de 120; 1 199 641 filas nuevas; 0 con fecha anterior al corte C. Flujo completo desde un entorno vacío (`desde-cero-20261116T214214`) | 20 tareas en éxito, 779 s; Bronze 4 605 216 filas; en cuarentena por R03: 257 420 + 572 416 + 137 807 + 208 530 = 1 176 173; último día válido en Silver 2026-08-29; CSV de C **idéntico** al entregado (49 853 filas, 0 diferencias); `predecir.py --datos <carpeta de 120 días>` da el mismo sha256 `2f0a5f76…4480b562` | `docs/evidence/p2/defensa-120/` |
| 2026-11-16 | cierre `entrega-final` | Restauración de los datos de 90 días con el comando único, para la demostración del video (`desde-cero-20261116T220008`) | 20 tareas en éxito, 749 s; Bronze = LEEME (3 405 575, diferencia 0); CSV de C idéntico (49 853 filas, 0 diferencias). En v2, R03 de Transurbano = 1 645, lo que explica 572 416 = 570 771 + 1 645 con 120 días | `docs/evidence/p2/restauracion-v2/` |

## Decisiones importantes: qué se decidió, quién la tomó y qué número la respalda

"Quién" es la persona que registró la decisión en el repositorio (autor del commit que la introdujo). El número sale del
repositorio y se puede volver a calcular con el comando o el archivo indicado.

| # | Decisión | Quién | Commit | Número que la respalda | Dónde se comprueba |
|---:|---|---|---|---|---|
| 1 | La unidad es la **persona** (`usuario_unificado_sk`), no la tarjeta | Dsmp28 (David Monje) | `24c28a0`, `f08a88d` | Con la tarjeta, 7 038 de 15 808 supuestos abandonos (0,445) son de personas que siguieron viajando con otra tarjeta; 16 930 de 16 930 hashes de Aerómetro invertidos | `analysis/p2_costo_unidad.sql`; informe fase 1 §1.2 |
| 2 | La llave de la persona se seudonimiza con HMAC-SHA256 y sal fija en Secret Manager | jralbizures | `69ed236` | 0 unidades faltantes o sobrantes y 0 diferencias en `tarjetas` al recalcular el corte C con 30 días más (49 853 filas) | `docs/evidence/p2/defensa-120/invariancia_C.md` |
| 3 | El CDC del padrón se aplica en orden de `seq`; un DELETE anterior a t saca a la persona de la población | erickkrv | `0d3671d` (base), `24c28a0` (regla del P2) | Excluidas por DELETE previo: 1 259 en A, 1 082 en B, 935 en C; 0 bajas reactivadas | `analysis/p2_poblacion.sql`; informe fase 1 §1.2 |
| 4 | Solo entran registros válidos: reglas R01 a R11 con cuarentena, y R03 corta en `fecha_referencia` = 2026-08-30 | erickkrv | `e6897cc`, `279bddd` | Con los datos de 120 días, los abordajes posteriores al 29 de agosto quedan en cuarentena por R03 y las predicciones de C no cambian (ver la corrida `defensa-120`) | `docs/evidence/p2/defensa-120/` |
| 5 | Las features salen de Silver con la fecha de corte como parámetro y ventanas ≤ 28 días | jralbizures | `2f35f93` (tabla del P1), `9038692` (churn) | Prueba de recorte: 51 955 filas, 0 diferencias en 39 columnas; el borrador ingenuo falló en 4 features (14 467 · 15 381 · 13 990 · 46 715 filas) | `make prueba-recorte`; `docs/evidence/p2/prueba_recorte*.md` |
| 6 | Bronze es idempotente por (archivo, sha256) y una versión nueva de los datos **reemplaza** a la anterior | ChrisYuman | `970d5be`, `879a0a2` | Bronze = LEEME: 3 405 575 filas esperadas y cargadas, diferencia 0 en los 9 archivos | `docs/evidence/p2/conteos_bronze.md`; ADR-018 |
| 7 | Un solo comando vacía, carga, predice y compara; las tareas de churn y de predicción viven en el DAG | Smorareq1 | `9a7b29f`, `966dbe2` | 20 tareas en éxito; la carga desde un entorno vacío termina en `IDÉNTICAS` | `make desde-cero`; `docs/evidence/p2/defensa-120/` |
| 8 | La métrica es Average Precision con los mismos 5 pliegues para todos los modelos | Dsmp28 (David Monje) | `8c0fb3d`, `13840bc` | Constante 0,1130 = tasa positiva de A; una feature 0,4101; logística 0,4459 ± 0,0160 | `docs/evidence/p2/fase1_modelos.md` |
| 9 | Va a producción HistGradientBoosting v1.0.0 y no la logística ni RandomForest | Dsmp28 (David Monje) | `7c888dc` | AP de validación 0,4680 ± 0,0205 contra 0,4459; gana en los 5 pliegues; brecha entrenamiento-validación 0,14 | `docs/evidence/p2/fase2_modelos.md`, `fase2_decision.md` |
| 10 | El umbral sale del costo (0,340; teórico 1/3) y B se evalúa una sola vez | Dsmp28 (David Monje) | `7c888dc`, evaluación en `29e8b14` | Q12 200 fuera de muestra en A; en B: AP 0,4214 y Q8 175 | `docs/evidence/p2/umbral.md`, `test_b.md` |
| 11 | Dos segmentos (k = 2 por silueta) con acciones distintas | Dsmp28 (David Monje) | `41f6eb1` | Silueta 0,1766; abandono 0,152 en ocasionales (70,2 %) y 0,021 en habituales (29,8 %) | `docs/evidence/p2/segmentos*.md`, `acciones.md` |

