-- H1 · Demanda por modo y hora (tablero 2.1, pregunta 1: ¿cuándo se concentra la demanda?).
-- Fuente: gold.agg_demanda_modo_zona_hora (fct_abordaje × dim_tiempo agrupado por fecha, hora, modo y zona).
-- Devuelve la matriz hora × modo del mapa de calor de la hoja H1 (45 días completos), el porcentaje de cada
-- hora sobre el total, y dos filas de subtotal (hora pico 05–08 y 16–19 según dim_tiempo.es_hora_pico) más el total.
-- Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/h1_demanda_modo_hora.sql
-- La cifra de la hoja H1 es SUM(abordajes) por (hora, modo); el total debe ser 1 647 569 = filas de fct_abordaje.
WITH base AS (
  SELECT es_hora_pico, hora, modo_id, SUM(abordajes) AS abordajes   -- medida aditiva
  FROM `cienciadatos-509301.gold.agg_demanda_modo_zona_hora`
  GROUP BY es_hora_pico, hora, modo_id
),
total AS (SELECT SUM(abordajes) AS abordajes FROM base)
SELECT
  CASE
    WHEN GROUPING(es_hora_pico) = 1 THEN 'TOTAL 45 días'
    WHEN GROUPING(hora) = 1 THEN IF(es_hora_pico, 'SUBTOTAL hora pico', 'SUBTOTAL fuera de pico')
    ELSE FORMAT('%02d:00', hora)
  END                                             AS hora_etiqueta,
  es_hora_pico,
  SUM(IF(modo_id = 'TM', abordajes, 0))           AS transmetro,
  SUM(IF(modo_id = 'TU', abordajes, 0))           AS transurbano,
  SUM(IF(modo_id = 'MR', abordajes, 0))           AS metroriel,
  SUM(IF(modo_id = 'AM', abordajes, 0))           AS aerometro,
  SUM(abordajes)                                  AS total,
  ROUND(100 * SUM(abordajes) / (SELECT abordajes FROM total), 2) AS pct_del_total   -- no aditiva
FROM base
GROUP BY ROLLUP (es_hora_pico, hora)
ORDER BY GROUPING(hora), GROUPING(es_hora_pico), es_hora_pico, hora;

-- Resultado (ejecutado el 2026-09-20 con bq query --use_legacy_sql=false --location=us-central1 --nouse_cache):
--   total 45 días = 1 647 569 (TM 362 106 · TU 786 398 · MR 295 511 · AM 203 554); hay servicio de 04:00 a 22:00.
--   hora pico (05–08, 16–19) = 906 950 abordajes (55,05 %); fuera de pico = 740 619 (44,95 %).
--   hora más cargada 07:00 = 197 491 (11,99 %); luego 17:00 = 167 251 (10,15 %), 18:00 = 139 136 (8,44 %),
--   06:00 = 132 023 (8,01 %). Valle 09:00–15:00 ≈ 58 400–59 400 por hora (3,55 %). El patrón es igual en los 4 modos.
--   tiempo del job: 0,230 s (230 ms; 372 slot-ms; 0,8 MB procesados). Tiempo total con CLI (time): 1,64 s.
--   Job: h1_demanda_modo_hora_1789968181 (ronda previa h1_demanda_modo_hora_1789968087: 314 ms).
