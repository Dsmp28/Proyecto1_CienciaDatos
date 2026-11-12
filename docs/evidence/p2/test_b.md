# Evaluación única en el corte B

Fecha 2026-11-12T04:36:54+00:00; commit `29e8b14ac5202d7dd81a4fd4f812583a28e2fce0`; modelo `churn_persona_v1.0.0.joblib` (sha256 `350b8fcadae48144571b18ade1a6b8e8cd25b10ab7b0a2e6ab704602bd68770b`); umbral 0.3400 (fijado con A, antes de ver B).

| métrica | valor |
|---|---|
| AP | 0.4214 |
| ROC-AUC | 0.8591 |
| Brier | 0.0731 |
| precisión | 0.4357 |
| recall | 0.4497 |

Tasa de churn en B: 0.1022 (50483 unidades; AP del azar = esa tasa).

Matriz de confusión (filas = real, columnas = predicho):

| | pred 0 | pred 1 |
|---|---|---|
| real 0 | 42319 | 3005 |
| real 1 | 2839 | 2320 |

Ganancia en Q = 15·TP − 5·(TP+FP) = 15·2320 − 5·5325 = 8175.00; por cada 1 000 personas: 161.94.
