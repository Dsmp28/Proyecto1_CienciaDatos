# Evidencia del Proyecto 2

| Comando | Produce |
|---|---|
| `make ml-dataset` | `ml/artefactos/cache/churn_dataset.csv` (ignorado por git; el corte B sale sin etiqueta) |
| `make ml-entrenar FASE=1` (`ML_ORIGEN=csv RUTA_CSV=...` para usar el CSV) | `fase1_modelos.md` (AP, ROC-AUC, Brier con las dos líneas base), `fase1_lambda.md` (grilla completa de λ), `fase1_coeficientes.md` (top 5 hacia churn y protectores), `fase1_tiempos.md`, `figuras/ap_vs_lambda.png` |
| (mismo comando) | en `ml/artefactos/`: `folds_A.csv`, `fase1_resultados.json` (métricas, versiones, semilla, tiempos), `oof_A_<modelo>.csv` (predicciones fuera de muestra para el umbral de la fase 2) |

Todo usa solo el corte A, semilla 2026 y los mismos folds para todos los modelos. La etiqueta de B no se lee en la fase 1.
