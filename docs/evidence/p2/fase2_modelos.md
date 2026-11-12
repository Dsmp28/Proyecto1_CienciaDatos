# Fase 2: comparación de modelos (tabla 1.4 más ensambles)

Corte A: 51955 unidades, tasa de churn 0.1130; CV estratificada 5 folds (semilla 2026, los mismos folds de la fase 1: `ml/artefactos/folds_A.csv`).

| modelo | AP train | AP val media | AP val sd | ROC-AUC media | Brier media |
|---|---|---|---|---|---|
| Baseline constante (tasa de A) | 0.1130 | 0.1130 | 0.0000 | 0.5000 | 0.1002 |
| Baseline una feature (dias_desde_ultimo) | 0.4096 | 0.4101 | 0.0186 | 0.8417 | 0.2597 |
| Logística L2 (λ*) | 0.4506 | 0.4459 | 0.0160 | 0.8501 | 0.0782 |
| Logística L1 (λ*) | 0.4506 | 0.4459 | 0.0160 | 0.8501 | 0.0782 |
| Logística ElasticNet 0.5 (λ*) | 0.4506 | 0.4459 | 0.0160 | 0.8501 | 0.0782 |
| HistGradientBoosting (mejor de la grilla) | 0.6096 | 0.4680 | 0.0205 | 0.8613 | 0.0768 |
| RandomForest (400 árboles, min_samples_leaf=5) | 0.8092 | 0.4527 | 0.0227 | 0.8587 | 0.0775 |

AP del baseline constante = tasa positiva = 0.1130. AP train = media en las filas de entrenamiento de cada fold. Grilla de HistGradientBoosting (★ = elegida por AP de validación):

| learning_rate | max_iter | max_leaf_nodes | l2_regularization | ap_val_media | ap_val_sd | ap_train_media | ★ |
|---|---|---|---|---|---|---|---|
| 0.05 | 200 | 15 | 0 | 0.46788 | 0.020488 | 0.54736 |  |
| 0.05 | 200 | 15 | 1 | 0.46711 | 0.019552 | 0.54333 |  |
| 0.05 | 200 | 31 | 0 | 0.46624 | 0.01874 | 0.62708 |  |
| 0.05 | 200 | 31 | 1 | 0.46677 | 0.020867 | 0.61425 |  |
| 0.05 | 400 | 15 | 0 | 0.46805 | 0.020538 | 0.60957 | ★ |
| 0.05 | 400 | 15 | 1 | 0.46692 | 0.021114 | 0.59782 |  |
| 0.05 | 400 | 31 | 0 | 0.46163 | 0.020061 | 0.74001 |  |
| 0.05 | 400 | 31 | 1 | 0.46066 | 0.022026 | 0.71484 |  |
| 0.1 | 200 | 15 | 0 | 0.46475 | 0.021391 | 0.60973 |  |
| 0.1 | 200 | 15 | 1 | 0.46779 | 0.02162 | 0.59966 |  |
| 0.1 | 200 | 31 | 0 | 0.46106 | 0.019668 | 0.74131 |  |
| 0.1 | 200 | 31 | 1 | 0.45817 | 0.021204 | 0.71472 |  |
| 0.1 | 400 | 15 | 0 | 0.46029 | 0.019525 | 0.70972 |  |
| 0.1 | 400 | 15 | 1 | 0.46181 | 0.020699 | 0.68966 |  |
| 0.1 | 400 | 31 | 0 | 0.45033 | 0.021081 | 0.88038 |  |
| 0.1 | 400 | 31 | 1 | 0.44595 | 0.020037 | 0.8485 |  |

RandomForest: n_estimators=400, min_samples_leaf=5, sin grilla.
