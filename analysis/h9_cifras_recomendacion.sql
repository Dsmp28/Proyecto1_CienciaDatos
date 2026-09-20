-- H9 · Cifras citadas en docs/RECOMENDACION.md que no salen de otra hoja: uso exclusivo de Aerómetro, usuarios que
-- comparten Aerómetro y Transurbano, y personas con demanda multimodal en la Zona 12 (segunda candidata a transbordo).
-- Fuente: gold.agg_transbordo (una fila por persona, modos ordenados 'AM,MR,TM,TU') y gold.fct_abordaje.
SELECT
  (SELECT COUNT(*) FROM `cienciadatos-509301.gold.agg_transbordo` WHERE modos = 'AM')                          AS personas_solo_aerometro,
  (SELECT COUNT(*) FROM `cienciadatos-509301.gold.agg_transbordo` WHERE modos = 'AM,TU')                       AS personas_am_tu_dos_modos,
  (SELECT COUNT(*) FROM `cienciadatos-509301.gold.agg_transbordo`
    WHERE n_modos = 3 AND modos LIKE '%AM%' AND modos LIKE '%TU%')                                             AS personas_am_tu_tres_modos,
  (SELECT COUNT(DISTINCT a.usuario_unificado_sk)
     FROM `cienciadatos-509301.gold.fct_abordaje` a
     JOIN `cienciadatos-509301.gold.agg_transbordo` t USING (usuario_unificado_sk)
    WHERE a.zona_id = 'GT-Z12' AND t.es_multimodal)                                                            AS personas_multimodales_zona12,
  -- personas que usan al menos dos modos DENTRO de la Zona 12 (misma definición que h8 para la Zona 17)
  (SELECT COUNT(*) FROM (
     SELECT usuario_unificado_sk FROM `cienciadatos-509301.gold.fct_abordaje`
      WHERE zona_id = 'GT-Z12' GROUP BY 1 HAVING COUNT(DISTINCT modo_id) >= 2))                                AS personas_dos_modos_en_zona12;

-- Resultado (ejecutado el 2026-09-21 con bq query --use_legacy_sql=false --location=us-central1 --nouse_cache, 1,63 s):
--   personas_solo_aerometro = 964 · personas_am_tu_dos_modos = 1 546 · personas_am_tu_tres_modos = 4 866
--   personas_multimodales_zona12 = 38 540 (multimodales en la red con al menos un abordaje en la Zona 12)
--   personas_dos_modos_en_zona12 = 23 004 (usan >= 2 modos dentro de la Zona 12; misma definición que h8 para la Zona 17)
