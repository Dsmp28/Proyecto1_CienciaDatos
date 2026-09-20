-- Viajes del mes · camino A (definiciones_oficiales.md §1, prueba de fuego de gobernanza).
-- Definición oficial: un viaje = un abordaje válido. Camino A: hecho atómico gold.fct_abordaje × gold.dim_tiempo,
-- filtrando el mes por la dimensión de tiempo (anio_mes = '2026-06'). Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/viajes_del_mes_a.sql
-- Debe devolver el mismo total que analysis/viajes_del_mes_b.sql (misma cifra que la prueba
-- dbt/tests/gold/assert_viajes_del_mes_dos_caminos.sql).
SELECT
  t.anio_mes,
  a.modo_id,
  SUM(a.abordajes)            AS viajes,           -- medida aditiva (constante 1 por abordaje)
  SUM(a.monto_q)              AS monto_q,          -- medida aditiva
  COUNT(DISTINCT a.usuario_sk) AS tarjetas_distintas -- no aditiva
FROM `cienciadatos-509301.gold.fct_abordaje` AS a
JOIN `cienciadatos-509301.gold.dim_tiempo`   AS t
  ON t.tiempo_sk = a.tiempo_sk
WHERE t.anio_mes = '2026-06'
GROUP BY ROLLUP (t.anio_mes, a.modo_id)   -- la fila con modo_id NULL es el total del mes
HAVING t.anio_mes IS NOT NULL
ORDER BY a.modo_id NULLS LAST;

-- Resultado (ejecutado el 2026-09-20 con bq query --use_legacy_sql=false --location=us-central1, sin caché):
--   viajes del mes 2026-06 = 1 093 235  (AM 133 892 · MR 195 236 · TM 243 073 · TU 521 034)
--   tiempo del job: 0,662 s (662 ms; 5 735 slot-ms; 168,1 MB procesados). Tiempo total con CLI: 1,85 s.
--   Coincide exactamente con viajes_del_mes_b.sql (camino B).
