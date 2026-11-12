# Nota de calibración (predicciones fuera de muestra de A)

- Brier del modelo: 0.0768; Brier del baseline constante (tasa de A): 0.1002.
- Umbral empírico u* = 0.340; umbral teórico (costo / (tasa · valor)) = 0.333; diferencia absoluta = 0.007.

Curva de calibración por deciles de la probabilidad predicha (un modelo calibrado tiene p media ≈ tasa observada):

| decil | p_media | tasa_observada |
|---|---|---|
| 1 | 0.0012 | 0.0008 |
| 2 | 0.0038 | 0.0038 |
| 3 | 0.0090 | 0.0112 |
| 4 | 0.0175 | 0.0191 |
| 5 | 0.0330 | 0.0362 |
| 6 | 0.0574 | 0.0651 |
| 7 | 0.0918 | 0.1005 |
| 8 | 0.1507 | 0.1524 |
| 9 | 0.2561 | 0.2512 |
| 10 | 0.4989 | 0.4894 |


u* queda a menos de 0.1 del umbral teórico: no se requiere comentario adicional ni recalibración.
