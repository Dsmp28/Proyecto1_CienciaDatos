-- H5 · Caso MetroRiel (tablero 2.1, pregunta 4: ¿el trazado por las zonas 12, 8, 1, 6 y 17 atiende donde más se necesita?).
-- Fuente: gold.agg_metroriel_zonas (ranking de zonas por demanda total con es_zona_metroriel) y, como contraste de
-- origen–destino, gold.fct_viaje_metroriel (porcentaje de viajes que cambian de zona).
-- Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/h5_caso_metroriel.sql
-- Cifra esperada: las 5 zonas de MetroRiel ocupan los puestos 1–5 del ranking (148 554 … 137 170 abordajes) y
-- concentran 719 607 abordajes (43,68 % del total); MetroRiel aporta entre 36 % y 48 % de la demanda de cada una.
WITH total AS (
  SELECT
    SUM(abordajes_totales)                               AS abordajes,
    SUM(IF(es_zona_metroriel, abordajes_totales, 0))     AS abordajes_zonas_mr,
    COUNTIF(es_zona_metroriel)                           AS n_zonas_mr
  FROM `cienciadatos-509301.gold.agg_metroriel_zonas`
),
od AS (   -- contraste con el viaje completo de MetroRiel (origen–destino real)
  SELECT COUNT(*) AS viajes_mr, ROUND(100 * COUNTIF(cambia_de_zona) / COUNT(*), 2) AS pct_cambia_zona
  FROM `cienciadatos-509301.gold.fct_viaje_metroriel`
)
SELECT
  m.ranking,
  m.zona_id,
  m.zona_nombre,
  m.es_zona_metroriel,
  m.n_estaciones_mr,
  m.abordajes_tm, m.abordajes_tu, m.abordajes_mr, m.abordajes_am,   -- aditivas
  m.abordajes_totales,
  m.usuarios_distintos, m.personas_distintas,                        -- no aditivas
  m.pct_metroriel,
  ROUND(100 * m.abordajes_totales / t.abordajes, 2)                  AS pct_del_total,
  t.abordajes_zonas_mr                                               AS abordajes_5_zonas_mr,
  ROUND(100 * t.abordajes_zonas_mr / t.abordajes, 2)                 AS pct_5_zonas_mr,
  od.viajes_mr,
  od.pct_cambia_zona                                                 AS pct_viajes_mr_cambian_zona
FROM `cienciadatos-509301.gold.agg_metroriel_zonas` AS m
CROSS JOIN total AS t
CROSS JOIN od
WHERE m.abordajes_totales > 0
ORDER BY m.ranking;

-- Resultado (ejecutado el 2026-09-20 con bq query --use_legacy_sql=false --location=us-central1 --nouse_cache):
--   ranking 1–5 = las 5 zonas del trazado (17, 12, 8, 6, 1): 148 554 · 147 903 · 147 081 · 138 899 · 137 170.
--   abordajes_5_zonas_mr = 719 607 = 43,68 % del total; pct_metroriel por zona: 36,19 · 36,49 · 45,50 · 48,28 · 39,22.
--   Primera zona fuera del trazado: Mixco (6.º, 132 768, sin MetroRiel, 57 907 de Aerómetro).
--   viajes_mr = 295 511; 83,54 % cambian de zona entre origen y destino (MetroRiel funciona como corredor, no como
--   servicio intrazona).
--   tiempo del job: 0,267 s (267 ms; 306 slot-ms; 0,3 MB procesados). Tiempo total con CLI (time): 1,54 s.
--   Job: h5_caso_metroriel_1789968194 (ronda previa h5_caso_metroriel_1789968105: 226 ms).
