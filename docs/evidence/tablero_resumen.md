# Evidencia F6 · Tablero 2.1 y recomendación 2.2 (insumos)

Fecha: 2026-09-20. BigQuery `cienciadatos-509301.gold` (`us-central1`), build de Gold de `docs/evidence/gold_resumen.md`.
Cada SQL de `analysis/` se ejecutó con `bq query --use_legacy_sql=false --location=us-central1 --nouse_cache
--job_id=<hoja>_<epoch>`; el tiempo del job es `endTime − startTime` de `bq show -j --location=us-central1
--format=prettyjson <job_id>`, los bytes son `statistics.query.totalBytesProcessed`, y "CLI" es el tiempo total
medido con `time` alrededor del comando. Se corrieron dos rondas completas sin caché; la tabla muestra la última
(ronda 3) y, entre paréntesis, el tiempo del job de la ronda 2.

## 1. Cifras de verificación

| Hoja | SQL | Cifra | Valor | Job (ms) | Slot-ms | Bytes | CLI (s) | Job id |
|---|---|---|---:|---:|---:|---:|---:|---|
| H1 | `h1_demanda_modo_hora.sql` | Viajes en hora pico (05–08, 16–19) / total | 906 950 / 1 647 569 = 55,05 % | 230 (314) | 372 | 789 999 | 1,64 | `h1_demanda_modo_hora_1789968181` |
| H1 | ídem | Hora más cargada | 07:00 = 197 491 (11,99 %) | | | | | |
| H1 | ídem | Viajes por modo, 45 días | TM 362 106 · TU 786 398 · MR 295 511 · AM 203 554 | | | | | |
| H2 | `h2_demanda_zona.sql` | Zona con más demanda | Zona 17 = 148 554 (9,02 %) | 1 367 (1 007) | 22 263 | 814 918 | 3,65 | `h2_demanda_zona_1789968184` |
| H2 | ídem | Top 5 (zonas 17, 12, 8, 6, 1) acumulado | 43,68 % | | | | | |
| H2 | ídem | Zonas con solo TM y TU (11, 4, 9, 10) | 315 528 (19,15 %) | | | | | |
| H3 | `h3_cobertura.sql` | Zonas sin servicio de ningún modo | 11 de 26 | 203 (265) | 107 | 8 182 306 | 1,55 | `h3_cobertura_1789968189` |
| H3 | ídem | Residentes del padrón en Santa Catarina Pinula | 1 261 personas (2 677 tarjetas) | | | | | |
| H3 | ídem | Zonas con estación sin demanda | 0 | | | | | |
| H4 | `h4_transbordo.sql` | Personas con vínculo / multimodales | 56 848 / 41 485 = 72,98 % | 190 (170) | 33 | 1 318 223 | 1,43 | `h4_transbordo_1789968191` |
| H4 | ídem | Por n_modos | 1: 15 363 · 2: 25 048 · 3: 14 004 · 4: 2 433 | | | | | |
| H4 | ídem | Combinación más frecuente | TM,TU = 12 477 | | | | | |
| H5 | `h5_caso_metroriel.sql` | Ranking de las 5 zonas del trazado | puestos 1–5 | 267 (226) | 306 | 298 030 | 1,54 | `h5_caso_metroriel_1789968194` |
| H5 | ídem | Viajes en las 5 zonas del trazado | 719 607 (43,68 %) | | | | | |
| H5 | ídem | Viajes de MetroRiel que cambian de zona | 83,54 % de 295 511 | | | | | |
| H6 | `h6_kpis.sql` | Viajes del mes (junio 2026) | 1 093 235 | 1 173 (1 167) | 23 587 | 157 736 270 | 2,51 | `h6_kpis_1789968196` |
| H6 | ídem | Usuarios activos (30 d a 2026-07-16) | 53 820 personas (110 762 tarjetas) tarjetas | | | | | |
| H6 | ídem | Zonas sin servicio · % multimodal | 11 · 72,98 % | | | | | |
| H7 | `h7_linaje_de_una_cifra.sql` | Viajes TM, Zona 17, 2026-06-01 → objetos de Bronze | 725 = 388 + 337 (2 jsonl) | 173 (209) | 41 | 4 227 590 | 1,42 | `h7_linaje_de_una_cifra_1789968200` |
| H8 | `h8_transbordo_estacion_candidata.sql` | Zona candidata a estación de transbordo | Zona 17: 23 704 personas con ≥ 2 modos en la zona | 4 118 (4 905) | 45 711 | 256 457 096 | 6,17 | `h8_transbordo_estacion_candidata_1789968202` |
| H8 | ídem | Estaciones más cargadas por multimodales en Zona 17 | AM Eje 1 - Torre 6 (13 380) · MR 22 (12 517) · TM Centra Sur - Centro 10 (2 936) · TU Parada 7 R-110 (2 188) | | | | | |
| Gob. | `viajes_del_mes_a.sql` / `_b.sql` | Viajes junio por dos caminos | 1 093 235 = 1 093 235 | 662 / 345 | 5 735 / 2 924 | 168,1 MB / 93,2 MB | 1,85 / 1,52 | (F4) |

Consistencia: H1 total = H6 viajes_45_dias = filas de `fct_abordaje` (1 647 569); H2 top 5 = H5 zonas MetroRiel;
H4 % multimodal = H6 pct_multimodal = ADR-008; H6 viajes del mes = prueba de fuego de gobernanza.

## 2. Rendimiento

- Agregados `agg_*` (H1–H5): 0,17–0,27 s y < 10 MB por consulta; H2 sube a 1,4 s por la ventana acumulada.
- Lecturas completas de `fct_abordaje` (H6: 4 subconsultas; H8: cruce con 41 485 personas): 1,2–4,1 s, 158–256 MB.
- Con filtros de partición y cluster (H7: un día, un modo, una zona): 0,17 s y 4,2 MB.
- Ninguna consulta supera los 5 s ni los 260 MB: conexión en vivo viable desde Tableau; costo por debajo del TB
  gratuito mensual.

## 3. Archivos entregados

| Archivo | Contenido |
|---|---|
| `docs/tableau/red_metropolitana_gold.tds` | Fuente de datos Tableau (XML, conector `bigquery`, sin credenciales): `fct_abordaje` × 5 dimensiones |
| `docs/tableau/README.md` | Cómo abrir el `.tds` (OAuth), conexión manual alternativa, roles IAM, notas de rendimiento |
| `docs/tableau/GUIA_TABLERO.md` | Hojas H1–H6 y dashboard: fuentes, filas/columnas, filtros, gráfico, campos calculados, cifra esperada, linaje |
| `analysis/h1_demanda_modo_hora.sql` … `h6_kpis.sql` | Un SQL por hoja, ejecutado, con resultado y tiempo anotados |
| `analysis/h7_linaje_de_una_cifra.sql` | De una cifra del tablero a los objetos `gs://` de Bronze vía `dim_fuente` |
| `analysis/h8_transbordo_estacion_candidata.sql` | Zonas y estaciones candidatas a estación de transbordo (multimodales de `agg_transbordo` × `fct_abordaje`) |
| `analysis/README.md` | Tabla hoja → SQL → cifra → tiempo → bytes |
| `docs/RECOMENDACION.md` | Recomendación 2.2 (≤ 2 páginas): 4 hallazgos, dónde sí / dónde no, estación de transbordo en Zona 17, corredor Santa Catarina Pinula, Aerómetro subutilizado, límites |
| `docs/evidence/tablero_resumen.md` | Este archivo |

## 4. No verificado

- Apertura del `.tds` en Tableau Desktop y construcción real del tablero: no hay Tableau en este entorno. El XML
  está bien formado (validado con `xml.dom.minidom`) y sigue el ejemplo oficial de atributos de conexión de BigQuery,
  pero Tableau podría exigir atributos adicionales; la guía documenta "Editar conexión" y la conexión manual.
- Tiempos de respuesta desde Tableau (el conector añade latencia de red y de OAuth sobre los tiempos del job).
- Rotación de la sal HMAC y reejecución de Gold desde Airflow (pendientes de F5/F7, `gold_resumen.md` §10).
