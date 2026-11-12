# Fase 2: decisión del modelo

- Modelo con mayor AP de validación: `hgb`; modelo final guardado: `hgb`.
- Mejor lineal: `logistica_l2` AP val 0.4459 ± 0.0160 (train 0.4506).
- HistGradientBoosting: AP val 0.4680 ± 0.0205 (train 0.6096); parámetros {'learning_rate': 0.05, 'max_iter': 400, 'max_leaf_nodes': 15, 'l2_regularization': 0.0}.
- RandomForest: AP val 0.4527 ± 0.0227 (train 0.8092).
- Baseline constante (tasa): 0.1130; baseline una feature: AP val 0.4101.
- Umbral u* = 0.340 (teórico 0.333); ganancia OOF Q12200.00 (Q234.82 por 1 000).
- Top 3 por permutación: dias_desde_ultimo, zona_principal, dias_activos_7d.

## Decisión

**Se entrega HistGradientBoosting** (learning_rate 0,05, 400 iteraciones, 15 hojas, sin L2), versión 1.0.0.

- **Rendimiento.** AP de validación 0,4680 ± 0,0205 frente a 0,4459 ± 0,0160 de la logística, 0,4101 de una sola
  feature y 0,1130 de la constante. La diferencia media (0,022) es del tamaño de una desviación entre folds, pero es
  consistente: con los mismos folds el ensamble gana en los 5 (diferencias 0,016 · 0,037 · 0,026 · 0,019 · 0,013).
- **Sesgo y varianza.** La logística tiene brecha train − val de 0,005: no sobreajusta y su límite es el sesgo de la
  forma lineal (por eso λ casi no mueve la métrica). El ensamble baja ese sesgo a cambio de varianza: brecha 0,14. Se
  eligió la configuración de árboles pequeños (15 hojas); las de 31 hojas suben el AP de entrenamiento hasta 0,88 y
  bajan el de validación a 0,45. RandomForest memoriza más (train 0,81) y valida peor (0,4527): se descarta.
- **Decisión económica.** Con las predicciones fuera de muestra de A, el ensamble da Q12 200 con u* = 0,340 y la
  logística Q11 465 con su mejor umbral (0,365): Q735 más (6 %) sobre 51 955 personas.
- **Calibración.** Brier 0,0768 (logística 0,0782, constante 0,1002); los deciles de probabilidad coinciden con la tasa
  observada y u* queda a 0,007 del umbral teórico 1/3, así que no se recalibra.
- **Costo de la decisión.** Se pierde la lectura directa de coeficientes; se compensa con la importancia por
  permutación en validación. `dias_desde_ultimo` concentra la señal (caída de AP 0,240; la siguiente, 0,015), lo que
  explica que la línea base de una sola feature ya llegue a 0,410: la ganancia del modelo sobre esa línea base es
  real pero moderada (+0,058 de AP).
- **Qué se descartó.** Logística (mejor interpretabilidad, menor AP y menor ganancia en todos los folds), RandomForest
  (más varianza, menor AP) y reentrenar con A ∪ B (el test de B dejaría de describir el modelo entregado).
