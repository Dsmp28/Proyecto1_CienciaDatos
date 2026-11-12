# Segmentación: inercia y silueta por k

KMeans (n_init=10, semilla 2026) sobre las features numéricas de comportamiento de A, imputadas con la mediana y estandarizadas (mismo pipeline numérico del modelo); sin la etiqueta.

| k | inercia | silueta |
|---|---|---|
| 2 | 1256512.8450 | 0.1766 |
| 3 | 1143821.0707 | 0.1291 |
| 4 | 1058756.6788 | 0.1445 |
| 5 | 1002146.4662 | 0.1209 |
| 6 | 951767.7741 | 0.1159 |
| 7 | 906571.4804 | 0.1241 |
| 8 | 867051.7799 | 0.1373 |
| 9 | 836137.1823 | 0.1374 |
| 10 | 811816.6863 | 0.1184 |

Silueta calculada sobre una muestra de 10000 filas (estratificada por etiqueta, con semilla).
- k elegido por silueta máxima: **2**.
- Nota del codo (distancia máxima a la recta entre los extremos de la curva de inercia): k = 5 (difiere de la silueta: la inercia siempre baja con k; el codo es orientativo y la silueta decide).

Figuras: `figuras/codo.png`, `figuras/silueta.png`, `figuras/pca_segmentos.png` (PCA 2D explica 37.9% de la varianza: 27.9% + 10.0%).
