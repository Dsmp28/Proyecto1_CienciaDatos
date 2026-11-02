# Checklist de la rúbrica del Proyecto 2 → entregables en el repo

"hecho" = existe la ruta y la cifra o prueba que lo demuestra. Guía para la defensa: `docs/GUIA_DEFENSA.md` (sección P2).
Informes: `docs/P2/INFORME_FASE1.md`, `docs/P2/INFORME_FASE2.md`. Bitácora: `docs/P2/BITACORA.md`.

| Sección | Pts | Entregable exigido | Ruta en el repo | Estado y prueba |
|---|---|---|---|---|
| 1.1 Datos nuevos desde cero | 5 | Comando único desde entorno vacío | `README.md` §Proyecto 2 → `make desde-cero CONFIRMAR=BORRAR-<proyecto>` (`scripts/desde_cero.sh`, `scripts/reset_p2.py`, `ingest/landing.py`) | en curso |
| | | Tabla de conteos (archivo, esperadas, cargadas, diferencia) | `docs/evidence/p2/conteos_bronze.md` | pendiente |
| | | Tabla de tiempos (etapa, segundos) | `docs/evidence/p2/tiempos.md` | pendiente |
| 1.2 Etiqueta, población y unidad | 8 | Definición de la etiqueta en una frase | `docs/P2/INFORME_FASE1.md` §1.2; `dbt/models/features/churn/churn_etiqueta.sql` | pendiente |
| | | Unidad elegida y justificación (3–5 líneas) | `docs/DECISIONS.md` ADR-014; informe §1.2 | hecho (ADR) |
| | | Tabla de población A y B con la cuenta escrita | `analysis/p2_poblacion.sql` → informe §1.2 | pendiente |
| | | Costo de la unidad (número y proporción) | `analysis/p2_costo_unidad.sql` → informe §1.2 | pendiente |
| 1.3 Features y auditoría de fuga | 12 | Corte como parámetro; tabla con A, B y C, una fila por unidad y corte | `dbt/models/features/churn/churn_dataset.sql` (var `fechas_corte`) | pendiente (build v2) |
| | | Diccionario (nombre, qué mide, ventana ≤ 28, tabla Silver) | `dbt/models/features/churn/churn_diccionario.sql` → `docs/P2/diccionario_churn.md` | pendiente |
| | | Prueba de recorte (0 diferencias + features que fallaron antes) | `make prueba-recorte` → `docs/evidence/p2/prueba_recorte.md`, `prueba_recorte_fallos.json` | pendiente |
| 1.4 Baseline y logística | 15 | Métrica elegida (3–5 líneas) | ADR-016; informe §1.4 | hecho (ADR) |
| | | Tabla ≥ 4 filas (2 baselines + logísticas) con media y sd, mismos folds | `make ml-entrenar FASE=1` → `docs/evidence/p2/fase1_modelos.md`; `ml/artefactos/folds_A.csv` | pendiente |
| | | Gráfica métrica vs λ | `docs/evidence/p2/figuras/ap_vs_lambda.png` | pendiente |
| | | 5 coeficientes hacia el abandono interpretados | `docs/evidence/p2/fase1_coeficientes.md` → informe §1.4 | pendiente |
| 2.1 Ensemble y sesgo-varianza | 10 | Tabla con ensemble, métrica train y val; línea sesgo-varianza por modelo; top-10 permutación en validación; decisión | `make ml-entrenar FASE=2` → `fase2_modelos.md`, `fase2_sesgo_varianza.md`, `fase2_importancias.md`, `fase2_decision.md` | pendiente |
| 2.2 Umbral por costo y test único | 12 | Fórmula de ganancia con la cuenta; curva ganancia vs umbral; test B (fecha, commit, métrica, matriz, ganancia) | `docs/evidence/p2/umbral.md`, `figuras/ganancia_vs_umbral.png`; `make ml-test-b` → `docs/evidence/p2/test_b.md`, `docs/P2/BITACORA.md` | pendiente |
| 2.3 KMeans y PCA | 8 | k por codo y silueta; PCA 2D con varianza; tabla de segmentos con nombre y tasa; ≥ 2 acciones | `make ml-segmentos` → `segmentos.md`, `segmentos_k.md`, `acciones.md`, `figuras/{codo,silueta,pca_segmentos}.png` | pendiente |
| 2.4 MLOps | 12 | `predecir.py --datos --fecha-corte 2026-08-30` → CSV `unidad_id,tarjetas,puntaje,contactar` | `predecir.py`, `ml/prediccion.py`; `predicciones/predicciones_corte_2026-08-30.csv` | código hecho; CSV pendiente |
| | | Modelo guardado con versión, cargado sin reentrenar | `ml/modelos/churn_persona_v1.0.0.joblib` + `.json` | pendiente |
| | | Entorno reproducible | `requirements.txt`, `vm/Dockerfile.airflow`, `ml/config.py` (semilla), `README.md` | hecho |
| | | Ficha del modelo | `docs/P2/FICHA_MODELO.md` | pendiente |
| | | Prueba de invariancia | `make ensayo-invariancia` → `docs/evidence/p2/invariancia_B.md`; tarea `ml.ml_invariancia` del DAG | pendiente |
| Defensa | 18 | Presentación 15 min, invariancia en vivo, decisión ajena por integrante | `docs/P2/PRESENTACION.md`, `docs/GUIA_DEFENSA.md` | pendiente |

## Métricas obligatorias (pág. 14 del enunciado) → `docs/METRICAS.md` §Proyecto 2
Problema · Validación (junto al baseline) · Decisión · Test · Fuga (recorte + invariancia) · Rendimiento (carga desde cero, features, entrenamiento, predicción).

## Penalizaciones vigiladas
- Fuga en features: `tests/test_ventanas_churn.py`, `assert_churn_*`, prueba de recorte, invariancia.
- B más de una vez: guardia en `ml/datos.py` y `ml/evaluar_b.py`, marcador en la bitácora.
- C cambia con más datos: `ml/invariancia.py` + tarea del DAG.
- Métrica sin baseline: toda tabla de `ml/entrenar.py` incluye las dos líneas base.
