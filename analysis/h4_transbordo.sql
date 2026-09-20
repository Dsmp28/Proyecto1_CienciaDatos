-- H4 · Transbordo (tablero 2.1, pregunta 3: ¿cuántos usuarios usan más de un sistema?).
-- Fuente: gold.agg_transbordo_resumen (una fila por número de modos) y gold.agg_transbordo (una fila por persona
-- seudonimizada, ADR-008) para el detalle por combinación de modos. Se devuelven dos niveles en un mismo resultado:
--   nivel 'resumen'     : usuarios y % por n_modos (barras de la hoja H4) más el KPI % multimodal;
--   nivel 'combinacion' : usuarios por combinación exacta de modos (detalle de la hoja H4).
-- Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/h4_transbordo.sql
-- Cifra esperada: 56 848 personas; 41 485 (72,98 %) usan más de un sistema.
WITH resumen AS (
  SELECT
    'resumen'                                   AS nivel,
    n_modos,
    CAST(n_modos AS STRING) || ' modo(s)'       AS grupo,
    usuarios,
    pct_usuarios,
    abordajes,
    abordajes_por_usuario,
    combinacion_mas_frecuente,
    SUM(IF(es_multimodal, usuarios, 0)) OVER () AS usuarios_multimodales,
    SUM(usuarios) OVER ()                       AS usuarios_total,
    ROUND(100 * SUM(IF(es_multimodal, usuarios, 0)) OVER () / SUM(usuarios) OVER (), 2) AS pct_multimodal
  FROM `cienciadatos-509301.gold.agg_transbordo_resumen`
),
combinacion AS (
  SELECT
    'combinacion'                               AS nivel,
    n_modos,
    modos                                       AS grupo,
    COUNT(*)                                    AS usuarios,
    ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_usuarios,
    SUM(abordajes)                              AS abordajes,
    ROUND(SUM(abordajes) / COUNT(*), 2)         AS abordajes_por_usuario,
    CAST(NULL AS STRING)                        AS combinacion_mas_frecuente,
    CAST(NULL AS INT64)                         AS usuarios_multimodales,
    CAST(NULL AS INT64)                         AS usuarios_total,
    CAST(NULL AS FLOAT64)                       AS pct_multimodal
  FROM `cienciadatos-509301.gold.agg_transbordo`
  GROUP BY n_modos, modos
)
SELECT * FROM resumen
UNION ALL
SELECT * FROM combinacion
ORDER BY nivel DESC, n_modos, usuarios DESC;

-- Resultado (ejecutado el 2026-09-20 con bq query --use_legacy_sql=false --location=us-central1 --nouse_cache):
--   usuarios_total = 56 848 personas con vínculo; usuarios_multimodales = 41 485; pct_multimodal = 72,98 %.
--   1 modo 15 363 (27,02 %) · 2 modos 25 048 (44,06 %) · 3 modos 14 004 (24,63 %) · 4 modos 2 433 (4,28 %).
--   Combinaciones: TM,TU 12 477 (21,95 %) · MR,TM,TU 7 563 (13,30 %) · TM solo 7 822 · MR,TM 4 944 · TU solo 4 713 ·
--   AM,TM,TU 3 928 · MR,TU 2 969 · AM,TM 2 513 · AM,MR,TM,TU 2 433 · MR solo 1 864 · AM,MR,TM 1 575 · AM,TU 1 546 ·
--   AM solo 964 · AM,MR,TU 938 · AM,MR 599. Personas que usan Aerómetro = 14 496 (25,5 %); solo 964 lo usan en exclusiva.
--   Coincide con docs/evidence/gold_resumen.md §6 y ADR-008.
--   tiempo del job: 0,190 s (190 ms; 33 slot-ms; 1,3 MB procesados). Tiempo total con CLI (time): 1,43 s.
--   Job: h4_transbordo_1789968191 (ronda previa h4_transbordo_1789968101: 170 ms).
