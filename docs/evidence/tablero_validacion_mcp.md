# Evidencia 2.1 — Validación del tablero publicado contra Gold (2026-10-12)

Validación automática del libro **"Red Metropolitana - Tablero Gold"** (Tableau Cloud, sitio
`urlcienciadedatos-segundosemestre2026`, Espacio personal) usando el servidor MCP oficial de Tableau
(`@tableau/mcp-server` 4.22.3, autenticación por token de acceso personal). Se descargaron los datos de cada hoja con
`get-view-data` y se compararon con consultas en vivo a `cienciadatos-509301.gold` (`bq query --nouse_cache`).

Cómo se obtuvo: `list-workbooks` / `get-workbook` (id `414445a2-79d8-400c-8dc1-30406a8b6459`) → `list-views` (6 vistas:
H1–H5 y el dashboard) → `get-view-data` por hoja. El libro declara tres fuentes embebidas, todas del dataset `gold`:
`agg_demanda_modo_zona_hora+`, `agg_cobertura_zona+` (incluye `agg_metroriel_zonas`) y `agg_transbordo_resumen`.
No hay ninguna conexión a `silver`, `staging` ni `bronze` (restricción "Tableau → Gold únicamente").

| Hoja | Cifra descargada de Tableau (MCP) | Consulta en BigQuery `gold` | ¿Coincide? |
|---|---|---|---|
| H1 Demanda modo x hora | 76 celdas hora × modo; total 1 647 569; Transurbano 07:00 = 94 093 | `SUM(abordajes)` de `agg_demanda_modo_zona_hora` = 1 647 569; TU hora 7 = 94 093 | sí |
| H2 Demanda por zona | 44 filas modo × zona; total 1 647 569; ranking Zona 17 (148 554), 12 (147 903), 8 (147 081), 6 (138 899), 1 (137 170), Mixco (132 768) | mismo ranking y cifras con `dim_zona` | sí |
| H3 Cobertura por zona | 26 zonas × 3 medidas; 11 zonas con `Sin Servicio = True` (2, 3, 5, 14, 15, 16, 19, 21, 24, 25 y Santa Catarina Pinula), todas con 0 estaciones y 0 abordajes | `COUNTIF(sin_servicio)` de `agg_cobertura_zona` = 11 de 26 | sí |
| H4 Transbordo | 1 modo 15 363 · 2 modos 25 048 · 3 modos 14 004 · 4 modos 2 433 | `agg_transbordo_resumen`: 1:15 363 2:25 048 3:14 004 4:2 433; multimodal 72,98 % | sí |
| H5 Caso MetroRiel | 26 zonas; las 5 del trazado (1, 6, 8, 12, 17) suman 719 607 de 1 647 569 (43,68 %) | `agg_metroriel_zonas`: 719 607 / 1 647 569 | sí |

Resultado: **5 de 5 hojas coinciden** con Gold y con las cifras esperadas de `analysis/h1…h5*.sql` y de
`docs/evidence/tablero_tableau_cloud.md`. El dashboard (vista por defecto del libro) compone esas cinco hojas.

Notas operativas:
- El servidor MCP devolvió `401` en tres llamadas enviadas en paralelo dentro de un mismo proceso; reenviadas una por
  una respondieron bien. Para validaciones automáticas, enviar las llamadas en serie.
- Existe una segunda copia del libro, "Red Metropolitana - Tablero", en el proyecto `Samples` del sitio (misma
  estructura). La copia de referencia es la del Espacio personal, citada arriba.
- Cómo configurar el conector: `docs/tableau/README.md`, sección "Conector MCP de Tableau Cloud".
