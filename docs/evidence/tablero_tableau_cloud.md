# Evidencia 2.1 — Tablero construido en Tableau Cloud (2026-10-07)

Libro de trabajo **"Red Metropolitana - Tablero Gold"**, publicado en el Espacio personal del sitio
`urlcienciadedatos-segundosemestre2026` (Tableau Cloud, web authoring), conectado en tiempo real a BigQuery
`cienciadatos-509301.gold` con la cuenta de Google del propietario (OAuth, sin credenciales insertadas).

Captura: `tablero_tableau_cloud.jpg`.

| Hoja | Fuente (Gold) | Vista | Cifra verificada en pantalla |
|---|---|---|---|
| H1 Demanda modo x hora | `agg_demanda_modo_zona_hora` + `dim_modo` + `dim_zona` | tabla de resaltado hora × modo, color por abordajes | total 1 647 569; Transurbano 07:00 = 94 093 (= `analysis/h1_demanda_modo_hora.sql`) |
| H2 Demanda por zona | misma fuente | barras horizontales apiladas por modo, orden descendente | Zona 17 primera (148 554), luego 12, 8, 6, 1 (= `h2_demanda_zona.sql`) |
| H3 Cobertura por zona | `agg_cobertura_zona` | tabla: Sin Servicio, modos con servicio, abordajes, estaciones, n.º de modos | 11 zonas con `Sin Servicio = True`, Santa Catarina Pinula con 0 estaciones (= `h3_cobertura.sql`) |
| H4 Transbordo | `agg_transbordo_resumen` | barras apiladas multimodal sí/no, color por n.º de modos, etiquetas | 15 363 con 1 modo; 25 048 + 14 004 + 2 433 multimodales = 41 485 (72,98 %) (= `h4_transbordo.sql`) |
| H5 Caso MetroRiel | `agg_metroriel_zonas` (relacionada a `agg_cobertura_zona` por `zona_id`) | barras por zona agrupadas por "Es Zona Metroriel", orden descendente | las 5 zonas del trazado concentran 719 607 abordajes (43,68 %) (= `h5_caso_metroriel.sql`) |
| Dashboard | las cinco hojas | tamaño automático, título visible | — |

Pendiente para el equipo (afinado estético, según `docs/tableau/GUIA_TABLERO.md`): filtros globales de fecha y modo,
KPIs de la hoja H6, parámetro "Fecha de referencia" y acciones de resaltado entre hojas.
