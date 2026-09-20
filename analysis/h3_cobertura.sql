-- H3 · Cobertura (tablero 2.1, pregunta 2: ¿qué zonas quedan sin servicio de ningún modo?).
-- Fuente: gold.agg_cobertura_zona (dim_zona con oferta de fct_cobertura_zona_modo y demanda de fct_abordaje),
-- enriquecida con los residentes del padrón por zona (gold.dim_usuario.zona_residencia_id, personas distintas por
-- usuario_unificado_sk) para saber si una zona sin servicio tiene demanda latente.
-- Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/h3_cobertura.sql
-- Cifra esperada: 11 zonas con sin_servicio = TRUE de 26; solo Santa Catarina Pinula tiene residentes en el padrón.
WITH residentes AS (
  SELECT
    zona_residencia_id                     AS zona_id,
    COUNT(DISTINCT usuario_unificado_sk)   AS personas_padron,   -- no aditiva
    COUNT(*)                               AS tarjetas_padron
  FROM `cienciadatos-509301.gold.dim_usuario`
  WHERE zona_residencia_id IS NOT NULL
  GROUP BY zona_residencia_id
)
SELECT
  c.orden,
  c.zona_id,
  c.zona_nombre,
  c.tipo,
  c.municipio,
  c.sin_servicio,
  c.n_modos_con_servicio,
  c.modos_con_servicio,
  c.n_estaciones,
  c.abordajes_totales,                       -- aditiva
  c.usuarios_distintos,                      -- no aditiva
  c.n_modos_con_demanda,
  c.tiene_estacion_sin_demanda,
  IFNULL(r.personas_padron, 0)               AS personas_padron_residentes,
  IFNULL(r.tarjetas_padron, 0)               AS tarjetas_padron_residentes,
  COUNTIF(c.sin_servicio) OVER ()            AS zonas_sin_servicio_total,
  COUNT(*) OVER ()                           AS zonas_total
FROM `cienciadatos-509301.gold.agg_cobertura_zona` AS c
LEFT JOIN residentes AS r USING (zona_id)
ORDER BY c.sin_servicio DESC, c.orden;

-- Resultado (ejecutado el 2026-09-20 con bq query --use_legacy_sql=false --location=us-central1 --nouse_cache):
--   zonas_sin_servicio_total = 11 de 26: Zonas 2, 3, 5, 14, 15, 16, 19, 21, 24, 25 y Santa Catarina Pinula.
--   Santa Catarina Pinula es la ÚNICA zona sin servicio con residentes en el padrón: 1 261 personas (2 677 tarjetas),
--   cifra comparable a cualquier zona con servicio (1 208 Mixco … 1 320 Zona 12). Las otras 10 tienen 0 residentes.
--   Ninguna zona tiene estación sin demanda (tiene_estacion_sin_demanda = false en las 15 zonas con servicio).
--   tiempo del job: 0,203 s (203 ms; 107 slot-ms; 8,2 MB procesados). Tiempo total con CLI (time): 1,55 s.
--   Job: h3_cobertura_1789968189 (ronda previa h3_cobertura_1789968096: 265 ms).
