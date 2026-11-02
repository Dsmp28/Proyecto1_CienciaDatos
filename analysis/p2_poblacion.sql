-- P2 · Embudo de población del dataset de churn por corte (ADR-015): personas con >= 1 abordaje en [t-28, t),
-- con >= 2, excluidas por baja (DELETE) del CDC previa a t, población final, positivos (churn = 1) y tasa.
-- Incluye la lectura alternativa del padrón: excluidas cuya baja ya no es el último estado (estado_padron_ultimo_a_t = 'ACTIVA',
-- p. ej. reactivadas) frente a las que siguen INACTIVA en t. Corte C no tiene etiqueta (horizonte no observado).
-- Fuente: features.churn_poblacion, churn_etiqueta. Requiere dbt build --select tag:churn.
-- Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/p2_poblacion.sql
SELECT
  p.corte,
  ANY_VALUE(p.fecha_corte)                                                              AS fecha_corte,
  COUNT(*)                                                                              AS personas_con_1_abordaje,
  COUNTIF(p.n_abordajes_28d >= 2)                                                       AS personas_con_2_o_mas,
  COUNTIF(p.n_abordajes_28d >= 2 AND p.tiene_delete_previo)                             AS excluidas_por_delete,
  COUNTIF(p.n_abordajes_28d >= 2 AND p.tiene_delete_previo
          AND p.estado_padron_ultimo_a_t = 'INACTIVA')                                  AS excluidas_delete_aun_inactivas,
  COUNTIF(p.n_abordajes_28d >= 2 AND p.tiene_delete_previo
          AND p.estado_padron_ultimo_a_t = 'ACTIVA')                                    AS excluidas_delete_reactivadas,
  COUNTIF(p.en_poblacion)                                                               AS poblacion,
  COUNTIF(e.etiqueta = 1)                                                               AS positivos,
  COUNTIF(e.etiqueta = 0)                                                               AS negativos,
  COUNTIF(p.en_poblacion AND e.etiqueta IS NULL)                                        AS sin_etiqueta,
  ROUND(SAFE_DIVIDE(COUNTIF(e.etiqueta = 1), COUNTIF(e.etiqueta IS NOT NULL)), 4)       AS tasa_churn
FROM `cienciadatos-509301.features.churn_poblacion` AS p
LEFT JOIN `cienciadatos-509301.features.churn_etiqueta` AS e
  ON e.corte = p.corte AND e.unidad_id = p.unidad_id
GROUP BY p.corte
ORDER BY p.corte;
