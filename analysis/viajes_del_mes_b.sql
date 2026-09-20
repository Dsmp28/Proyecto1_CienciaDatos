-- Viajes del mes · camino B (definiciones_oficiales.md §1, prueba de fuego de gobernanza).
-- Camino B: snapshot periódico gold.fct_uso_usuario_dia (usuario × día × modo), construido en dbt directamente desde
-- silver_abordajes (no desde fct_abordaje), sumando la medida aditiva `abordajes` de los días de junio 2026.
-- Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/viajes_del_mes_b.sql
-- Debe devolver el mismo total que analysis/viajes_del_mes_a.sql.
SELECT
  FORMAT_DATE('%Y-%m', u.fecha)  AS anio_mes,
  u.modo_id,
  SUM(u.abordajes)               AS viajes,            -- medida aditiva
  SUM(u.monto_q)                 AS monto_q,           -- medida aditiva
  COUNT(DISTINCT u.usuario_sk)   AS tarjetas_distintas -- no aditiva
FROM `cienciadatos-509301.gold.fct_uso_usuario_dia` AS u
WHERE u.fecha BETWEEN DATE '2026-06-01' AND DATE '2026-06-30'
GROUP BY ROLLUP (anio_mes, u.modo_id)   -- la fila con modo_id NULL es el total del mes
HAVING anio_mes IS NOT NULL
ORDER BY u.modo_id NULLS LAST;

-- Resultado (ejecutado el 2026-09-20 con bq query --use_legacy_sql=false --location=us-central1, sin caché):
--   viajes del mes 2026-06 = 1 093 235  (AM 133 892 · MR 195 236 · TM 243 073 · TU 521 034)
--   tiempo del job: 0,345 s (345 ms; 2 924 slot-ms; 93,2 MB procesados). Tiempo total con CLI: 1,52 s.
--   Coincide exactamente con viajes_del_mes_a.sql (camino A).
