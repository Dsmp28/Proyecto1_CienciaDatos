-- H2 · Demanda por zona con modo apilado (tablero 2.1, pregunta 1: ¿dónde se concentra la demanda?).
-- Fuente: gold.agg_demanda_modo_zona_hora × gold.dim_zona. Una fila por zona con demanda, abordajes por modo
-- (barras apiladas de la hoja H2), ranking, porcentaje del total y porcentaje acumulado (concentración).
-- Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/h2_demanda_zona.sql
-- Cifra esperada: Zona 17 primera con 148 554 abordajes; las 5 zonas de MetroRiel (17, 12, 8, 6, 1) son el top 5.
WITH total AS (
  SELECT SUM(abordajes) AS abordajes FROM `cienciadatos-509301.gold.agg_demanda_modo_zona_hora`
)
SELECT
  RANK() OVER (ORDER BY SUM(d.abordajes) DESC)                 AS ranking,
  d.zona_id,
  z.zona_nombre,
  z.tipo,
  z.modos_con_servicio,
  SUM(IF(d.modo_id = 'TM', d.abordajes, 0))                    AS transmetro,   -- aditivas
  SUM(IF(d.modo_id = 'TU', d.abordajes, 0))                    AS transurbano,
  SUM(IF(d.modo_id = 'MR', d.abordajes, 0))                    AS metroriel,
  SUM(IF(d.modo_id = 'AM', d.abordajes, 0))                    AS aerometro,
  SUM(d.abordajes)                                             AS total,
  COUNT(DISTINCT d.modo_id)                                    AS n_modos_con_demanda,
  ROUND(100 * SUM(d.abordajes) / (SELECT abordajes FROM total), 2)  AS pct_del_total,      -- no aditiva
  ROUND(100 * SUM(SUM(d.abordajes)) OVER (ORDER BY SUM(d.abordajes) DESC ROWS UNBOUNDED PRECEDING)
        / (SELECT abordajes FROM total), 2)                    AS pct_acumulado       -- no aditiva
FROM `cienciadatos-509301.gold.agg_demanda_modo_zona_hora` AS d
JOIN `cienciadatos-509301.gold.dim_zona`                   AS z USING (zona_id)
GROUP BY d.zona_id, z.zona_nombre, z.tipo, z.modos_con_servicio
ORDER BY ranking;

-- Resultado (ejecutado el 2026-09-20 con bq query --use_legacy_sql=false --location=us-central1 --nouse_cache):
--   15 zonas con demanda (las otras 11 no tienen estación). Ranking: 1 Zona 17 = 148 554 (9,02 %) · 2 Zona 12 = 147 903 ·
--   3 Zona 8 = 147 081 · 4 Zona 6 = 138 899 · 5 Zona 1 = 137 170 → top 5 (= zonas MetroRiel) acumulan 43,68 %.
--   6 Mixco = 132 768 (AM 57 907, la zona con más Aerómetro) · 7 Zona 7 = 117 431. Últimas: Zona 4 = 77 918,
--   Zona 9 = 76 363, Zona 10 = 75 304 (solo TM y TU). Las 4 zonas con solo 2 modos (11, 4, 9, 10) suman 315 528 (19,15 %).
--   tiempo del job: 1,367 s (1 367 ms; 22 263 slot-ms; 0,8 MB procesados). Tiempo total con CLI (time): 3,65 s.
--   Job: h2_demanda_zona_1789968184 (ronda previa h2_demanda_zona_1789968091: 1 007 ms).
