# Plan del Proyecto 2 — ¿Quién deja de usar la red? (churn a 30 días sobre la plataforma del Proyecto 1)

## Contexto

El Proyecto 1 dejó una plataforma Bronze → Staging/CDC → Silver (+cuarentena) → Gold → Tableau en GCP (GCS +
BigQuery, Airflow 3 y Kafka en la VM, dbt Core, Terraform). El Proyecto 2 (`docs/Proyecto 2 Red Metropolitana.pdf`,
datos en `docs/P2_datos_red/datos_red/` + `LEEME.txt`) pide usarla para un problema de clasificación binaria: para
cada **persona** y fecha de corte, predecir si no tendrá ningún abordaje válido en los 30 días siguientes, y decidir a
quién contactar con un escenario de costos. Rúbrica de 100 pts, defensa oral el 9 de noviembre con prueba de
invariancia en vivo. Entregas: etiqueta `fase-1` (1.1–1.4 + informe; su plazo, 28 oct, ya pasó: se etiqueta apenas
cierre) y `fase-2` (2.1–2.4, informe, predicciones del corte C, presentación). Hoy es 2026-11-01: quedan 8 días.

Decisiones ya tomadas con el usuario: unidad = **persona** (`usuario_unificado_sk`, ADR-008); `predecir.py` lee
features de **BigQuery** (ADC) con respaldo `--origen csv`; el **entrenamiento corre en la laptop** con `make` y los
artefactos se versionan; el DAG agrega las tareas nuevas (dataset de cortes + predicción de C + invariancia); se
**etiqueta y hace push** al cerrar cada fase; el **vaciado** del lake/warehouse solo con OK explícito en el momento.

## Requerimientos del enunciado (resumen; checklist completo en `docs/RUBRICA_CHECKLIST_P2.md`)

- Datos v2: mismos 9 archivos, periodo **2026-06-01 → 2026-08-29**, ~525 MB; usuarios nuevos; los DELETE del CDC son
  bajas reales. **Reemplazan** a los del P1: vaciar lake, warehouse y snapshots; correr todo con **un solo comando**;
  comparar conteos de Bronze con los esperados (aerometro 387,053 · am_est 14 · cdc 77,636 · metroriel 590,844 ·
  mr_est 22 · tm_est 104 · transmetro 713,786 · transurbano 1,635,788 · tu_paradas 328; verificados localmente).
- Cortes (t = 00:00 local): **A = 2026-07-01** (entrena, CV 5 folds estratificada), **B = 2026-07-31** (test, una sola
  vez), **C = 2026-08-30** (predicciones entregadas, etiqueta oculta). Ventanas de features **≤ 28 días**, iguales en
  los tres cortes. Población: ≥ 2 abordajes válidos en los 28 días previos y sin DELETE del CDC aplicado antes de t.
  Etiqueta: 1 si no hay ningún abordaje válido en ningún operador en [t, t+30); 0 si viajó. Solo registros válidos.
- 1.1 (5) comando único + tabla conteos (archivo, esperadas, cargadas, diferencia) + tabla tiempos (etapa, segundos).
- 1.2 (8) etiqueta en una frase; unidad + justificación; tabla población A/B con la cuenta escrita; costo de la unidad.
- 1.3 (12) corte como parámetro; una tabla con filas de A, B y C (`unidad_id, fecha_corte, features…, etiqueta` vacía
  en C); diccionario (nombre, qué mide, ventana, tabla Silver); **prueba de recorte** (A con datos completos vs
  recortados al 30-jun → 0 diferencias, listando las features que fallaron antes de corregir).
- 1.4 (15) ≥ 2 baselines (constante = tasa positiva de A; una feature como puntaje); logística con ≥ 2 castigos, λ por
  CV, gráfica métrica vs λ; tabla ≥ 4 filas (modelo, media, sd); top-5 coeficientes interpretados; **nada con B**.
- 2.1 (10) ensemble (HistGradientBoosting) mismos folds; métrica train vs val; sesgo-varianza; top-10 importancia por
  permutación en validación; decisión. 2.2 (12) ganancia con Q5/25 %/Q60, curva ganancia vs umbral, umbral elegido con
  OOF de A, **una sola** evaluación en B (fecha, commit, métrica, matriz, ganancia en Q). 2.3 (8) KMeans+PCA sobre A
  escalado, k por codo y silueta, tabla de segmentos con nombre y tasa de abandono, ≥ 2 acciones. 2.4 (12)
  `python predecir.py --datos <carpeta> --fecha-corte 2026-08-30` → CSV `unidad_id,tarjetas(;),puntaje,contactar`
  versionado; modelo joblib con versión en el nombre, cargado sin reentrenar; entorno reproducible; ficha del modelo;
  **prueba de invariancia** (+30 días de datos → predicciones idénticas).
- Penalizaciones: fuga → 0 en 1.3 y métricas afectadas no cuentan; B dos veces → mitad de 2.2; C cambia → mitad de 2.4;
  métrica sin baseline no cuenta.

## Hallazgos de la exploración que condicionan el diseño

1. `fecha_referencia` = 2026-07-16 (`dbt/dbt_project.yml`) alimenta la regla R03: con v2 mandaría julio y agosto a
   cuarentena. Debe ser **2026-08-30** (día siguiente al último dato). El DAG no pasa esta var; se cambia el default.
2. `max_usuario_base_id` = 70000 (`silver_am_hash_map`): v2 llega a **84 882** y 11 283 personas lo superan. Medido en
   los archivos: los **16 930 hashes de Aerómetro se invierten todos** con N ≥ 84 882 → fijar **100000**.
3. No existe comando que vacíe lake/warehouse (solo `make destroy`); `vm-sync` no envía datos (`datos_red/` ignorado);
   `generar_o_verificar.py` exige sha256/filas de `ingest/expected_hashes.json` (P1) y, si faltan archivos, llama al
   generador de 45 días; Kafka conserva tópicos y offsets del grupo `bronze-writer` en volumen (72 h); el manifiesto
   `ops.ingest_manifest` es la llave de idempotencia; el marcador `bronze/` del bucket lo gestiona Terraform.
4. `usuario_features` (P1) es una sola fecha de corte, ventanas 7/30/90, tabla reconstruida por corrida; usa
   `silver_usuarios.estado/perfil` (estado FINAL → fuga si se reutiliza). `silver_padron_scd2` tiene `vigente_hasta` y
   `es_vigente` (miran al futuro). `silver_metroriel_viajes.duracion_s` usa la salida (puede ser ≥ t).
5. Llaves nativas solo en Bronze/Silver (`silver_usuarios.llave_nativa` por modo; AM = hash 12 hex). Seudónimos HMAC
   estables mientras no rote la sal (necesario para invariancia). `ops_secrets.hmac_key` lo recrea `publicar_clave_hmac`.
6. Entorno sin scikit-learn/joblib/matplotlib (ni en `requirements.txt` ni en `vm/Dockerfile.airflow`); pandas y
   pandas-gbq están como transitivas. Scheduler de la VM con límite 1.5 GiB (inferencia cabe; entrenamiento no).
7. `tests/test_dag.py` fija el conjunto exacto de tareas; `test_gold_lineage` ya exige features → solo Silver/seeds;
   `test_no_current_date` cubre modelos nuevos. `.gitignore` ignora `*.csv.gz` y `datos_red/`.
8. `ops.run_metrics` guarda `duracion_s` por tarea (etapa = task_id con prefijo de grupo): sirve para la tabla de
   tiempos. `conteos_bronze.py` usa el manifiesto como "esperado": para 1.1 hay que usar el LEEME.

## Diseño

### D1. Carga desde cero con un comando (1.1) — `make desde-cero CONFIRMAR=BORRAR-cienciadatos-509301`
- **Landing en el lake** (ADR-013): `make landing-subir VERSION=v2 ORIGEN=docs/P2_datos_red/datos_red` copia los 9
  archivos a `gs://cienciadatos-509301-lake/landing/datos_red/v2/` + `MANIFEST.json` (sha256, filas). Responde a la
  pregunta del usuario sobre un "bucket raw"; el día de la defensa el zip nuevo se sube como `VERSION=invariancia`.
- `ingest/generar_o_verificar.py`: nuevo `--origen {landing,generador,local}` (env `ORIGEN_DATOS`, default landing),
  `--version` (env `VERSION_DATOS`, default v2), `--sin-verificar` activable por env `VERIFICAR_HASHES=false`. Si falta
  un archivo o su sha difiere y el origen es landing → descarga a `DATOS_DIR`. `ingest/expected_hashes.json` se
  regenera para v2 (el de P1 pasa a `expected_hashes_p1.json`, usado por el modo generador). Prueba nueva
  `tests/test_expected_counts.py`: `filas_datos` de v2 == conteos del `LEEME.txt` (regex sobre el archivo).
- `scripts/reset_p2.py --confirmar BORRAR-<proyecto> [--dry-run]` (ADR-013): (1) exporta `ops.run_metrics` e
  `ops.ingest_manifest` a `docs/evidence/p1/*.csv`; (2) borra `bronze/**` del bucket menos el marcador `bronze/`;
  nunca `landing/` ni `ml/`; (3) borra las **tablas** (no datasets) de bronze, staging, silver, quarantine, gold,
  features, ops y `*_recorte`; conserva `ops_secrets.hmac_key` (misma sal → mismos seudónimos); (4) por IAP en la VM:
  `kafka-topics.sh --delete` de los dos tópicos y `kafka-consumer-groups.sh --delete --group bronze-writer`, y
  `rm /opt/red-metropolitana/datos_red/*`; (5) escribe `docs/evidence/p2/reset.md` (antes/después).
- `scripts/desde_cero.sh` (derivado de `scripts/demo_idempotencia.sh`): reset → `make vm-sync` → dispara el DAG por
  REST con `conf={origen_datos:landing, version_datos:v2, verificar_hashes:true}` → espera todas las tareas en
  success → `ingest/evidencia_p2.py --run-id` genera `docs/evidence/p2/conteos_bronze.md` (archivo | esperadas LEEME |
  cargadas `COUNT(*)` externa | diferencia) y `docs/evidence/p2/tiempos.md` (etapa | segundos desde `ops.run_metrics`,
  más total de reloj del DagRun y suma de tareas).

### D2. dbt (ADR-012, ADR-015)
- Vars: `fecha_referencia: "2026-08-30"`, `max_usuario_base_id: 100000`, `fechas_corte: ["2026-07-01","2026-07-31",
  "2026-08-30"]`, `horizonte_dias: 30`, `ventana_max_dias: 28`, `recorte_datos_hasta: null`. Tags `churn` en
  `models/features/churn/` y `models/silver/churn/`. `usuario_features` de P1 se conserva (sus pruebas siguen válidas).
- Macros: `cortes_cte()` (una fila por corte A/B/C desde `fechas_corte`); `filtro_recorte(expr_ts_local)` (si
  `recorte_datos_hasta` no es nulo añade `date(expr) <= recorte`; se aplica en **staging** a TM, TU, AM, MR entrada y
  salida, y CDC `commit_ts`; catálogos sin filtro); `generate_schema_name` con sufijo `_recorte` cuando
  `target.name == 'recorte'` (nuevo target en `dbt/profiles.yml`, mismo proyecto).
- Modelos nuevos (`features` salvo el primero):
  - `silver/churn/silver_unidad_tarjetas_corte` (unidad_id, fecha_corte, `tarjetas` = STRING_AGG de llaves nativas
    **observadas antes de t** ordenadas por modo, `n_tarjetas`). Vive en Silver porque lleva llaves nativas.
  - `churn_eventos`: abordajes válidos de `silver_abordajes` × cortes, en [t−28, t+30), con `dias_antes_corte` y
    `tramo` ∈ {ventana, horizonte}. Solo `churn_etiqueta` lee `horizonte`.
  - `churn_poblacion`: `n_abordajes_28d`, `tiene_delete_previo` (cualquier DELETE con `vigente_desde < t` en una
    tarjeta de padrón de la persona; lectura literal, alternativa "último estado" reportada), `en_poblacion`.
  - `churn_etiqueta`: 1/0 según abordajes en [t, t+30); **null** si `t + 30 > fecha_referencia` (C).
  - `churn_features`: solo `tramo='ventana'`; conteos 7/14/28 d, días activos, `dias_desde_ultimo` (1..28),
    semanas activas de 4, ratio últimos 14 vs 14 previos, CV semanal, n modos y shares por modo, % hora pico, % fin de
    semana/feriado (seeds), gasto 28 d, n estaciones/zonas, % transbordo interno, n tarjetas activas 28 d, hora media y
    sd, MetroRiel (entrada en ventana **y salida < t**: viajes y duración media), padrón **en t** desde
    `silver_padron_scd2` (`perfil_padron_a_t`, `tiene_padron_activo_a_t`, `n_eventos_padron_28d`; nunca
    `silver_usuarios.estado/perfil`, nunca `vigente_hasta/es_vigente`). Floats redondeados a 6 decimales.
  - `churn_dataset`: población ⋈ features ⋈ etiqueta; una fila por (unidad_id, fecha_corte); columnas de linaje
    `corte`, `fecha_referencia`, `run_id`; sin llaves nativas. `churn_diccionario` (nombre, qué mide, ventana, Silver).
  - `analyses/p2_poblacion.sql`, `analyses/p2_costo_unidad.sql` (cobertura AM, tarjetas sin vínculo, tarjetas por
    persona, contraste "positivos falsos con unidad tarjeta").
- Pruebas: unicidad (unidad_id, fecha_corte); not_null; `etiqueta` ∈ {0,1} y nula ⇔ sin horizonte; población
  recalculada desde Silver; `max(dias_antes_corte) ≤ 28` en ventana; rangos de shares; sin llaves nativas en
  `churn_dataset` (patrones de `assert_gold_sin_llaves_nativas`); diccionario cubre columnas; tarjetas cubren la
  población. Pytest `tests/test_ventanas_churn.py`: ningún `interval N day` > 28 en `churn_features`.
- **Prueba de recorte** (`make prueba-recorte`): `dbt run --target recorte --select tag:staging tag:silver
  tag:quarantine tag:churn --vars '{recorte_datos_hasta: "2026-06-30", fechas_corte: ["2026-07-01"]}'` →
  `ml/prueba_recorte.py` compara `features.churn_features` vs `features_recorte.churn_features` (mismo conjunto de
  unidades, `EXCEPT DISTINCT` en ambos sentidos, diferencias por columna) → `docs/evidence/p2/prueba_recorte.md`.
  Se ejecuta **primero con un borrador ingenuo** (perfil final, duración MR sin filtro de salida, `es_vigente`) para
  registrar las features que fallan, y luego con la versión corregida (0 diferencias), como pide la rúbrica.

### D3. Paquete `ml/` y `predecir.py` (ADR-016, ADR-017)
- Dependencias fijadas en `requirements.txt` (scikit-learn 1.x estable, numpy, pandas, matplotlib, joblib, db-dtypes);
  en `vm/Dockerfile.airflow` solo scikit-learn, joblib, numpy, pandas, db-dtypes con las mismas versiones.
- Módulos: `config.py` (SEMILLA 2026, costos Q5/0.25/Q60, VERSION), `datos.py` (carga desde BigQuery o CSV; **guardia**:
  cargar B lanza error salvo desde `evaluar_b.py`), `folds.py` (StratifiedKFold 5, shuffle, seed; `ml/artefactos/
  folds_A.csv` versionado), `pipeline.py` (ColumnTransformer: StandardScaler + OneHot), `baselines.py` (constante =
  tasa de A; `dias_desde_ultimo` como puntaje, justificado a priori), `lineales.py` (L2/L1/EN con saga, grid
  C = 1/λ log-espaciado, figura AP vs λ, coeficientes), `ensamble.py` (HistGradientBoosting mismos folds, train vs val,
  permutation_importance en validación), `umbral.py` (G(u) = Σ_{p≥u}(0.25·60·y − 5) = 15·TP − 5·(TP+FP); teórico
  p > 1/3; curva empírica OOF de A; u* = argmax; nota de calibración), `evaluar_b.py` (única evaluación: exige árbol
  limpio, aborta si existe `ml/artefactos/evaluacion_b.json` o el marcador en `docs/P2/BITACORA.md`; escribe el JSON
  antes de calcular; registra fecha, commit, sha del joblib, AP, ROC-AUC, matriz, ganancia en Q), `segmentos.py`
  (KMeans k=2..10, codo + silueta en muestra, PCA 2D, medianas, tasa de churn, nombres, acciones), `persistencia.py`
  (`ml/modelos/churn_persona_v1.0.0.joblib` + JSON de metadatos: versión, commit, features, umbral, versiones de
  librerías, sha256; `ml/modelos/ACTUAL`), `invariancia.py` (compara dos CSV: mismo conjunto de `unidad_id`, igualdad
  de `tarjetas`, `contactar` y `puntaje` redondeado; exit 1 si difieren), `entrenar.py` (CLI fase1 | fase2).
- **Métrica principal: Average Precision** (clases desbalanceadas; decisión de ranking; baseline constante = tasa
  positiva); secundarias ROC-AUC y Brier (calibración para el umbral). Siempre junto al baseline.
- Modelo entregado para C = el entrenado en todo A y evaluado en B (reentrenar con A∪B queda como mejora documentada).
- `predecir.py` (raíz): `--datos --fecha-corte [--origen bigquery|csv] [--salida] [--modelo] [--sin-verificar]
  [--sufijo-dataset]`: (1) sha256 de los 9 archivos vs `ops.ingest_manifest` (modo bigquery) o `expected_hashes.json`
  (modo csv), exit 2 si no coincide; (2) lee `features.churn_dataset` del corte ⋈ `silver_unidad_tarjetas_corte` (o
  `predicciones/features_corte_2026-08-30.csv` exportado por `make ml-exportar-features`); (3) carga joblib, verifica
  versión de sklearn y orden de columnas; (4) `puntaje = round(proba, 6)`, `contactar = puntaje ≥ umbral`; (5) CSV
  `unidad_id,tarjetas,puntaje,contactar` ordenado por `unidad_id`, una fila por unidad de la población de C, en
  `predicciones/predicciones_corte_2026-08-30.csv` (versionado; datos simulados).
- `make ensayo-invariancia`: target recorte hasta 2026-07-30 con corte B → `predecir.py` B con y sin sufijo →
  `invariancia.py` 0 diferencias (no mira etiquetas: no cuenta como usar B). Comparar una vez laptop vs VM; si difieren
  en flotantes, el CSV oficial se genera en la VM.
- Makefile: `landing-subir`, `reset`, `desde-cero`, `prueba-recorte`, `ml-dataset`, `ml-entrenar`, `ml-test-b`,
  `ml-segmentos`, `ml-exportar-features`, `ml-predecir`, `ml-invariancia`, `ensayo-invariancia`.

### D4. DAG `red_metropolitana` (`airflow/dags/red_metropolitana_dag.py`)
- Params nuevos (solo por entorno, como el ADR de seguridad): `origen_datos` (enum), `version_datos` (patrón),
  `verificar_hashes` (bool), `fecha_corte_prediccion` (fecha, default 2026-08-30).
- `dbt_features = build --select tag:features --exclude tag:churn`; nuevo `dbt_churn = build --select tag:churn`;
  orden `dbt_features >> dbt_churn >> dbt_docs`.
- Grupo `ml`: `ml_predecir_corte_c` (`python predecir.py --datos /opt/airflow/datos_red --fecha-corte
  $FECHA_CORTE_PREDICCION --salida /opt/airflow/salidas/…` + copia a `gs://<lake>/ml/predicciones/<run_id>/`; exit 99 →
  skip si no hay modelo) y `ml_invariancia` (compara con `predicciones/predicciones_corte_2026-08-30.csv`; skip 99 si
  no hay referencia o el corte no es C; falla si difiere). `pruebas_python >> ml_predecir_corte_c >> ml_invariancia >>
  registrar_metricas` con `trigger_rule="none_failed"` en `registrar_metricas`. Montaje escribible `airflow/salidas`.
- `tests/test_dag.py`: 21 tareas, nuevas dependencias, ningún `bash_command` con `{{ params.`. Pruebas nuevas:
  `test_predecir.py`, `test_ml_guardas.py`, `test_invariancia.py`, `test_expected_counts.py`, `test_ventanas_churn.py`.

### D5. Documentación
- `docs/P2/`: `INFORME_FASE1.md`, `INFORME_FASE2.md`, `FICHA_MODELO.md`, `BITACORA.md`, `PRESENTACION.md` (≈12 láminas),
  `diccionario_churn.md`. Evidencia en `docs/evidence/p2/` (conteos, tiempos, reset, prueba_recorte, figuras, invariancia).
- ADR-012 (datos v2, `fecha_referencia`, `max_usuario_base_id`), ADR-013 (landing y reset confirmado), ADR-014 (unidad
  persona y su costo), ADR-015 (población, etiqueta, ventanas ≤ 28, padrón en t, recorte), ADR-016 (AP, folds fijos,
  umbral por costo, B una vez), ADR-017 (`predecir.py`, versionado, invariancia, CSV oficial).
- `docs/METRICAS.md` §P2 (problema, validación, decisión, test, fuga, rendimiento); `docs/RUBRICA_CHECKLIST_P2.md`;
  `README.md` (comando único, `predecir.py`, entorno); `docs/GUIA_DEFENSA.md` (decisión ajena por integrante, fuga,
  métrica, umbral, guion de invariancia en vivo); `CLAUDE.md` (contexto P2, comandos, reglas duras: B una sola vez,
  ventanas ≤ 28 y solo Silver, CSV de C no se regenera salvo nueva versión, nunca estado final del padrón en features,
  reset solo con OK). `.gitignore`: versionar `ml/modelos/*.joblib|json`, `predicciones/*.csv`, `ml/artefactos/
  folds_A.csv`, `evaluacion_b.json`, `docs/evidence/p2/**`; ignorar `ml/artefactos/cache/`, `airflow/salidas/`.

## Fases con compuerta (8 días)

| Fase | Día | Contenido | Compuerta |
|---|---|---|---|
| F0 preparación | 1 nov | deps fijadas, vars dbt, ADR-012/013, `expected_hashes` v2 + prueba LEEME, landing + `--origen`, `reset_p2.py --dry-run`, export evidencia P1 | `make test` verde; dry-run revisado |
| F1 carga desde cero (1.1) | 1–2 nov | **OK del usuario** → `make desde-cero`; conteos y tiempos | diferencia 0 en 9 archivos; todas las tareas success; `dbt test` verde con v2 |
| F2 dataset y recorte (1.2, 1.3) | 2–3 nov | modelos churn + pruebas; población/costo; borrador ingenuo → recorte con fallos registrados → corrección → 0 diferencias | `prueba_recorte.md` 0 diferencias; tablas A/B |
| F3 ML fase 1 (1.4) | 3–4 nov | `ml/`, baselines, L2/L1/EN, figura λ, coeficientes, INFORME_FASE1 | sin acceso a B (prueba); **tag `fase-1` + push** |
| F4 ensemble (2.1) | 5 nov | HGB, train/val, permutación, decisión | tabla y decisión |
| F5 umbral + B (2.2) | 5 nov | curva de ganancia, u*, modelo v1.0.0 → `make ml-test-b` **una vez** | entrada en bitácora con commit |
| F6 segmentos (2.3) | 6 nov | KMeans, PCA, tabla, acciones | figuras y tabla |
| F7 MLOps (2.4) | 6–7 nov | `predecir.py`, Dockerfile, tareas DAG, CSV de C (laptop vs VM), ficha, ensayo de invariancia (recorte B) y ensayo de acumulación en la VM | `ml_invariancia` success en la VM; ensayo 0 diferencias |
| F8 docs y defensa | 8 nov | informe 2, presentación, checklist, guía | **tag `fase-2` + push**; ensayo en vivo |

## Verificación de punta a punta

```
make venv && make test                                   # pytest: DAG, linaje, ventanas, predecir, guardas, LEEME
python scripts/reset_p2.py --dry-run                     # revisar antes del OK
make desde-cero CONFIRMAR=BORRAR-cienciadatos-509301     # 1.1 → docs/evidence/p2/{conteos_bronze,tiempos}.md
make prueba-recorte                                      # 1.3 → 0 diferencias
make ml-entrenar FASE=1                                  # 1.4 sin B → tag fase-1
make ml-entrenar FASE=2 && make ml-segmentos             # 2.1, 2.3
make ml-test-b                                           # 2.2 UNA vez (bitácora con commit)
make ml-exportar-features && make ml-predecir            # CSV de C versionado
make ensayo-invariancia                                  # recorte B: 0 diferencias
# VM: disparar DAG → ml_predecir_corte_c + ml_invariancia en success
python predecir.py --datos docs/P2_datos_red/datos_red --fecha-corte 2026-08-30 --origen csv   # sin GCP
```

## Riesgos y mitigaciones

1. R03 con `fecha_referencia` vieja → F0 la cambia; `assert_fechas_dentro_de_referencia` lo verifica. El día de la
   defensa los datos de septiembre caen en cuarentena por R03 (coherente; C no cambia).
2. `max_usuario_base_id` → 100000; `assert_am_hash_invertible` vigila.
3. Estado residual de Kafka → reset borra tópicos y grupo; `conteos_bronze` diferencia 0 lo confirma.
4. Pérdida de `ops.run_metrics`/manifiesto de P1 → export previo a `docs/evidence/p1/`; la evidencia de idempotencia P1
   queda como histórica (el número de tablas cambia con los modelos nuevos).
5. Memoria del scheduler → inferencia en secuencia (< 300 MB + sklearn); registrar el pico una vez.
6. Invariancia: `unidad_id` depende de la sal HMAC (no rotar antes del 9 nov; va en la ficha); `tarjetas` solo con
   llaves observadas antes de t; `predecir.py` verifica el manifiesto (último sha por archivo).
7. Etiqueta de C nula por prueba singular; `entrenar.py` filtra `corte == 'A'` para todo `fit` (incluido KMeans).
8. B una sola vez: guardia por código + marcador en bitácora + árbol limpio; el JSON se escribe antes de calcular.
9. CI: no hacer push a `main` entre el reset y la reconstrucción (o relanzar el workflow tras F1).
10. Flotantes laptop/VM → redondeo a 6 decimales y comparación única; si difieren, CSV oficial desde la VM.
11. Ambigüedad "DELETE aplicado antes de t" → lectura literal + alternativa reportada (ADR-015).
12. Plazo: si F2 se atrasa, se simplifica F6 (k fijo justificado por silueta) antes que F7 (penalización de la mitad).
