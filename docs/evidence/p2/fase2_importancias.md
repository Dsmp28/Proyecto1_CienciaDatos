# Fase 2: importancia por permutación (HistGradientBoosting, top 10)

Caída media de Average Precision al permutar cada feature en el fold de validación (10 repeticiones por fold, promedio entre los 5 folds); sd = desviación entre folds.

| feature | importancia_media | sd |
|---|---|---|
| dias_desde_ultimo | 0.23982 | 0.01723 |
| zona_principal | 0.01537 | 0.00312 |
| dias_activos_7d | 0.01450 | 0.00758 |
| n_abordajes_7d | 0.01393 | 0.00800 |
| ratio_ult14_prev14 | 0.01347 | 0.00464 |
| perfil_padron_a_t | 0.00957 | 0.00198 |
| gasto_q_28d | 0.00943 | 0.00282 |
| hora_sd | 0.00720 | 0.00334 |
| n_abordajes_28d | 0.00704 | 0.00431 |
| n_zonas_28d | 0.00650 | 0.00641 |
