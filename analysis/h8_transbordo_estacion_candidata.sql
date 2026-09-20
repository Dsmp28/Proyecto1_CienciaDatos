-- H8 · Estación de transbordo candidata (insumo de la recomendación 2.2).
-- Cruza gold.fct_abordaje (zona, modo, estación, persona) con las personas multimodales de gold.agg_transbordo
-- (es_multimodal, ADR-008). Para cada zona: personas multimodales que abordaron ahí, personas que usaron 2 o más
-- modos DENTRO de la misma zona (transbordo local: la señal más directa para ubicar una estación de transbordo),
-- abordajes de esas personas y su peso sobre la demanda de la zona, y la estación más cargada de cada modo.
-- Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/h8_transbordo_estacion_candidata.sql
-- Cifra esperada: la zona con más personas que usan ≥ 2 modos en la misma zona es la candidata (ranking = 1).
WITH multimodales AS (
  SELECT usuario_unificado_sk
  FROM `cienciadatos-509301.gold.agg_transbordo`
  WHERE es_multimodal
),
ab AS (   -- abordajes de personas multimodales, con zona, modo y estación
  SELECT a.zona_id, a.modo_id, a.estacion_sk, a.usuario_unificado_sk, a.abordajes
  FROM `cienciadatos-509301.gold.fct_abordaje` AS a
  JOIN multimodales USING (usuario_unificado_sk)
),
persona_zona AS (
  SELECT zona_id, usuario_unificado_sk, COUNT(DISTINCT modo_id) AS n_modos_en_zona, SUM(abordajes) AS abordajes
  FROM ab
  GROUP BY zona_id, usuario_unificado_sk
),
zona AS (
  SELECT
    zona_id,
    COUNT(*)                        AS personas_multimodales,          -- no aditiva
    COUNTIF(n_modos_en_zona >= 2)   AS personas_2mas_modos_en_zona,    -- no aditiva
    SUM(abordajes)                  AS abordajes_multimodales          -- aditiva
  FROM persona_zona
  GROUP BY zona_id
),
estacion AS (
  SELECT e.zona_id, e.modo_id, e.estacion_sk, s.nombre, SUM(e.abordajes) AS abordajes,
         ROW_NUMBER() OVER (PARTITION BY e.zona_id, e.modo_id ORDER BY SUM(e.abordajes) DESC) AS rn
  FROM ab AS e
  JOIN `cienciadatos-509301.gold.dim_estacion` AS s USING (estacion_sk)
  GROUP BY e.zona_id, e.modo_id, e.estacion_sk, s.nombre
),
top_estacion_por_modo AS (
  SELECT zona_id,
         STRING_AGG(FORMAT('%s: %s (%d)', modo_id, nombre, abordajes), ' | ' ORDER BY abordajes DESC) AS estacion_top_por_modo
  FROM estacion
  WHERE rn = 1
  GROUP BY zona_id
)
SELECT
  RANK() OVER (ORDER BY z.personas_2mas_modos_en_zona DESC)             AS ranking,
  z.zona_id,
  dz.zona_nombre,
  dz.n_modos_con_servicio,
  dz.modos_con_servicio,
  z.personas_multimodales,
  z.personas_2mas_modos_en_zona,
  z.abordajes_multimodales,
  c.abordajes_totales,
  ROUND(100 * z.abordajes_multimodales / c.abordajes_totales, 2)        AS pct_abordajes_de_multimodales,
  t.estacion_top_por_modo
FROM zona AS z
JOIN `cienciadatos-509301.gold.dim_zona`            AS dz USING (zona_id)
JOIN `cienciadatos-509301.gold.agg_cobertura_zona`  AS c  USING (zona_id)
JOIN top_estacion_por_modo                          AS t  USING (zona_id)
ORDER BY ranking;

-- Resultado (ejecutado el 2026-09-20 con bq query --use_legacy_sql=false --location=us-central1 --nouse_cache):
--   ranking 1 = Zona 17: 23 704 personas usan 2 o más modos dentro de la zona; 38 678 personas multimodales abordan ahí;
--   131 404 abordajes de multimodales = 88,46 % de los 148 554 de la zona. Estaciones más cargadas por multimodales:
--   AM Aerometro Eje 1 - Torre 6 (13 380) · MR 22 (12 517) · TM Estación Centra Sur - Centro 10 (2 936) · TU Parada 7 ruta R-110 (2 188).
--   2 = Zona 12: 23 004 personas (AM Eje 1 - Torre 4 13 623 · MR 03 12 661) · 3 = Zona 1: 21 487 · 4 = Zona 8: 20 028 ·
--   5 = Zona 6: 18 079 · 6 = Mixco: 15 477. Las zonas con solo TM y TU quedan al final (Zona 10: 7 835).
--   Las 3 zonas con los 4 modos (17, 12, 1) son las 3 primeras: la candidata a estación de transbordo es la Zona 17.
--   tiempo del job: 4,118 s (4 118 ms; 45 711 slot-ms; 256,5 MB procesados: cruza los 1,65 M de abordajes con 41 485
--   personas). Tiempo total con CLI (time): 6,17 s. Job: h8_transbordo_estacion_candidata_1789968202 (ronda previa …_1789968117: 4 905 ms).
