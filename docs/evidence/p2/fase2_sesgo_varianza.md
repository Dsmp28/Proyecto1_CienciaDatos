# Fase 2: sesgo y varianza (AP de entrenamiento contra validación)

| modelo | ap_train | ap_val | brecha | diagnostico |
|---|---|---|---|---|
| Baseline una feature (dias_desde_ultimo) | 0.4096 | 0.4101 | -0.0005 | equilibrado |
| Logística L2 (λ*) | 0.4506 | 0.4459 | 0.0048 | equilibrado |
| Logística L1 (λ*) | 0.4506 | 0.4459 | 0.0048 | equilibrado |
| Logística ElasticNet 0.5 (λ*) | 0.4506 | 0.4459 | 0.0048 | equilibrado |
| HistGradientBoosting (mejor de la grilla) | 0.6096 | 0.4680 | 0.1415 | varianza alta |
| RandomForest (400 árboles, min_samples_leaf=5) | 0.8092 | 0.4527 | 0.3565 | varianza alta |

Reglas automáticas (umbrales sobre AP en [0, 1]):

- **varianza alta**: brecha = AP train − AP val ≥ 0.1.
- **sesgo alto**: brecha < 0.05 y AP val − tasa positiva (0.1130) < 0.1 (rinde poco por encima del azar tanto en train como en val).
- **equilibrado**: el resto.

Las etiquetas son una guía automática; el informe debe interpretarlas.
