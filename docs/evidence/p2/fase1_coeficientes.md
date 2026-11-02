# Fase 1: coeficientes de la logística L2 (λ* = 0.3162)

Coeficientes sobre features estandarizadas (z) e indicadores one-hot; positivo = empuja hacia churn.

## Top 5 hacia churn

| feature | coeficiente |
|---|---|
| dias_desde_ultimo | 0.6239 |
| zona_principal_GT-Z13 | 0.3712 |
| zona_principal_GT-Z10 | 0.2996 |
| semanas_activas_4 | 0.1424 |
| share_am | 0.1139 |

## Top 5 protectores

| feature | coeficiente |
|---|---|
| perfil_padron_a_t_SIN_DATO | -0.9230 |
| dias_activos_7d | -0.5729 |
| tiene_padron_a_t | -0.5605 |
| modo_principal_AM | -0.4766 |
| perfil_padron_a_t_adulto_mayor | -0.4092 |
