# Fase 1: comparación de modelos (validación cruzada en A)

Corte A: 51955 unidades, tasa de churn 0.1130; CV estratificada 5 folds (semilla 2026, folds persistidos en `ml/artefactos/folds_A.csv`).

| modelo | AP media | AP sd | ROC-AUC media | Brier media |
|---|---|---|---|---|
| Baseline constante (tasa de A) | 0.1130 | 0.0000 | 0.5000 | 0.1002 |
| Baseline una feature (dias_desde_ultimo) | 0.4101 | 0.0186 | 0.8417 | 0.2597 |
| Logística L2 (λ*) | 0.4459 | 0.0160 | 0.8501 | 0.0782 |
| Logística L1 (λ*) | 0.4459 | 0.0160 | 0.8501 | 0.0782 |
| Logística ElasticNet 0.5 (λ*) | 0.4459 | 0.0160 | 0.8501 | 0.0782 |

Métrica principal: Average Precision. AP del baseline constante = tasa positiva = 0.1130. El Brier del baseline por ranking no es una probabilidad calibrada.
