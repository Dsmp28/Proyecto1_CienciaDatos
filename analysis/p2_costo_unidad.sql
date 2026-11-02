-- P2 · Costo de la unidad "persona" frente a la tarjeta (ADR-015). Cuatro bloques en un solo resultado (columna `bloque`):
--  1) am_hashes: hashes de Aerómetro observados vs invertidos a usuario_base_id (silver_am_hash_map).
--  2) sin_base_por_modo: abordajes y tarjetas sin usuario_base_id por modo (no entran al dataset: unidad_id nulo).
--  3) tarjetas_por_persona: distribución de tarjetas por persona al corte A (silver_unidad_tarjetas_corte).
--  4) falsos_churn_corte_A: tarjetas activas en [t-28, t) de la población del corte A sin abordajes en el horizonte
--     cuya PERSONA sí viajó con otra tarjeta: serían falsos churn con unidad = tarjeta y los evita la unidad persona.
-- Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/p2_costo_unidad.sql
WITH am AS (
  SELECT
    'am_hashes' AS bloque, 'AM' AS detalle,
    COUNT(*) AS valor_1, COUNTIF(usuario_base_id IS NOT NULL) AS valor_2,
    COUNTIF(usuario_base_id IS NULL) AS valor_3
  FROM `cienciadatos-509301.silver.silver_usuarios`
  WHERE modo_id = 'AM'
),
sin_base AS (
  SELECT
    'sin_base_por_modo' AS bloque, a.modo_id AS detalle,
    COUNT(*) AS valor_1,
    COUNTIF(a.usuario_base_id IS NULL) AS valor_2,
    COUNT(DISTINCT IF(a.usuario_base_id IS NULL, a.llave_nativa, NULL)) AS valor_3
  FROM `cienciadatos-509301.silver.silver_abordajes` AS a
  GROUP BY a.modo_id
),
tarjetas AS (
  SELECT
    'tarjetas_por_persona' AS bloque, CAST(n_tarjetas AS STRING) AS detalle,
    COUNT(*) AS valor_1, NULL AS valor_2, NULL AS valor_3
  FROM `cienciadatos-509301.silver.silver_unidad_tarjetas_corte`
  WHERE corte = 'A'
  GROUP BY n_tarjetas
),
corte_a AS (
  SELECT DISTINCT fecha_corte FROM `cienciadatos-509301.features.churn_poblacion` WHERE corte = 'A'
),
tarjetas_activas AS (
  SELECT DISTINCT e.unidad_id, e.modo_id, e.tarjeta_sk
  FROM `cienciadatos-509301.features.churn_eventos` AS e
  JOIN `cienciadatos-509301.features.churn_poblacion` AS p
    ON p.corte = e.corte AND p.unidad_id = e.unidad_id AND p.en_poblacion
  WHERE e.corte = 'A' AND e.tramo = 'ventana'
),
tarjetas_horizonte AS (
  SELECT DISTINCT unidad_id, modo_id, tarjeta_sk
  FROM `cienciadatos-509301.features.churn_eventos`
  WHERE corte = 'A' AND tramo = 'horizonte'
),
personas_horizonte AS (
  SELECT DISTINCT unidad_id FROM tarjetas_horizonte
),
falsos AS (
  SELECT
    'falsos_churn_corte_A' AS bloque, 'tarjetas' AS detalle,
    COUNT(*) AS valor_1,
    COUNTIF(th.tarjeta_sk IS NULL) AS valor_2,                              -- tarjetas sin abordajes en el horizonte
    COUNTIF(th.tarjeta_sk IS NULL AND ph.unidad_id IS NOT NULL) AS valor_3  -- ... de personas que sí viajaron (falso churn)
  FROM tarjetas_activas AS ta
  LEFT JOIN tarjetas_horizonte AS th
    ON th.unidad_id = ta.unidad_id AND th.modo_id = ta.modo_id AND th.tarjeta_sk = ta.tarjeta_sk
  LEFT JOIN personas_horizonte AS ph ON ph.unidad_id = ta.unidad_id
)
-- valor_1 / valor_2 / valor_3 por bloque:
--   am_hashes: hashes observados / invertidos / sin invertir
--   sin_base_por_modo: abordajes / abordajes sin usuario_base_id / tarjetas distintas sin usuario_base_id
--   tarjetas_por_persona: (detalle = n tarjetas) personas
--   falsos_churn_corte_A: tarjetas activas en la ventana / sin abordajes en el horizonte / de ellas, persona sí viajó
SELECT * FROM am
UNION ALL SELECT * FROM sin_base
UNION ALL SELECT * FROM tarjetas
UNION ALL SELECT * FROM falsos
ORDER BY bloque, detalle;
