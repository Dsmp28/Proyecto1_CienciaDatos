-- H6 · KPIs del tablero 2.1 (una fila): viajes del mes, viajes de los 45 días, usuarios activos, zonas sin servicio
-- y % multimodal. Cada KPI sale de la tabla Gold que usa su hoja, con las definiciones oficiales
-- (docs/governance/definiciones_oficiales.md): un viaje = un abordaje válido; usuario activo = tarjeta con al menos
-- un viaje en los 30 días anteriores a fecha_referencia = 2026-07-16 (ventana 2026-06-17 … 2026-07-16), excluyendo
-- las tarjetas de Transmetro dadas de baja en el padrón (estado_padron = 'INACTIVA').
-- Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/h6_kpis.sql
-- Cifra esperada: viajes_mes_junio = 1 093 235 (igual a viajes_del_mes_a/b.sql); viajes_45_dias = 1 647 569;
-- zonas_sin_servicio = 11; pct_multimodal = 72,98.
SELECT
  (SELECT SUM(abordajes) FROM `cienciadatos-509301.gold.fct_abordaje`)                       AS viajes_45_dias,
  (SELECT SUM(a.abordajes)
     FROM `cienciadatos-509301.gold.fct_abordaje` AS a
     JOIN `cienciadatos-509301.gold.dim_tiempo`   AS t USING (tiempo_sk)
    WHERE t.anio_mes = '2026-06')                                                             AS viajes_mes_junio,
  (SELECT SUM(a.abordajes)
     FROM `cienciadatos-509301.gold.fct_abordaje` AS a
     JOIN `cienciadatos-509301.gold.dim_tiempo`   AS t USING (tiempo_sk)
    WHERE t.anio_mes = '2026-07')                                                             AS viajes_mes_julio_parcial,
  -- Usuario activo (definición oficial §2): >= 1 viaje en los 30 días anteriores a la fecha de referencia
  -- (2026-06-16 … 2026-07-15) y no dado de baja en el padrón. Se reporta a nivel de PERSONA (identidad unificada,
  -- ADR-008; misma ventana y regla que features.usuario_features.es_usuario_activo_30d) y, como detalle, por tarjeta.
  (SELECT COUNT(DISTINCT a.usuario_unificado_sk)
     FROM `cienciadatos-509301.gold.fct_abordaje` AS a
     JOIN `cienciadatos-509301.gold.dim_usuario`  AS u USING (usuario_sk)
    WHERE a.fecha >= DATE_SUB(DATE '2026-07-16', INTERVAL 30 DAY)
      AND a.fecha <  DATE '2026-07-16'
      AND u.estado_padron != 'INACTIVA')                                                      AS personas_activas_30d,
  (SELECT COUNT(DISTINCT a.usuario_sk)
     FROM `cienciadatos-509301.gold.fct_abordaje` AS a
     JOIN `cienciadatos-509301.gold.dim_usuario`  AS u USING (usuario_sk)
    WHERE a.fecha >= DATE_SUB(DATE '2026-07-16', INTERVAL 30 DAY)
      AND a.fecha <  DATE '2026-07-16'
      AND u.estado_padron != 'INACTIVA')                                                      AS tarjetas_activas_30d,
  (SELECT COUNT(DISTINCT usuario_sk) FROM `cienciadatos-509301.gold.fct_abordaje`)           AS tarjetas_con_viajes_45_dias,
  (SELECT COUNTIF(sin_servicio) FROM `cienciadatos-509301.gold.agg_cobertura_zona`)         AS zonas_sin_servicio,
  (SELECT COUNT(*) FROM `cienciadatos-509301.gold.agg_cobertura_zona`)                       AS zonas_total,
  (SELECT SUM(IF(es_multimodal, usuarios, 0)) FROM `cienciadatos-509301.gold.agg_transbordo_resumen`) AS usuarios_multimodales,
  (SELECT SUM(usuarios) FROM `cienciadatos-509301.gold.agg_transbordo_resumen`)              AS personas_con_vinculo,
  (SELECT ROUND(100 * SUM(IF(es_multimodal, usuarios, 0)) / SUM(usuarios), 2)
     FROM `cienciadatos-509301.gold.agg_transbordo_resumen`)                                 AS pct_multimodal;

-- Resultado (ejecutado el 2026-09-20 con bq query --use_legacy_sql=false --location=us-central1 --nouse_cache):
--   viajes_45_dias = 1 647 569 · viajes_mes_junio = 1 093 235 (= viajes_del_mes_a/b.sql) · viajes_mes_julio_parcial = 554 334
--   personas_activas_30d = 53 820 (ventana 2026-06-16 … 2026-07-15, sin bajas del padrón; = features.usuario_features)
--   tarjetas_activas_30d = 110 762 (misma regla a nivel de tarjeta seudonimizada) de 117 203 tarjetas con viajes
--   zonas_sin_servicio = 11 de 26 · usuarios_multimodales = 41 485 de 56 848 personas · pct_multimodal = 72,98 %.
--   tiempo del job: 1,173 s (1 173 ms; 23 587 slot-ms; 157,7 MB procesados: lee fct_abordaje 4 veces). Tiempo total con
--   CLI (time): 2,51 s. Job: h6_kpis_1789968196 (ronda previa h6_kpis_1789968109: 1 167 ms).
