{{ config(cluster_by=['n_modos']) }}
-- Gold · agg_transbordo. Agregado para Tableau (pregunta 3: usuarios que usan más de un sistema). Una fila por persona
-- seudonimizada (usuario_unificado_sk, ADR-008) desde fct_uso_usuario_dia, como indica la matriz del bus.
-- modos = lista ordenada de modos usados ('AM,MR,TM,TU'); es_multimodal = n_modos > 1. Solo tarjetas con vínculo
-- (usuario_unificado_sk no nulo; en estos datos el 100 %).
select
    usuario_unificado_sk,
    count(distinct modo_id) as n_modos,
    string_agg(distinct modo_id, ',' order by modo_id) as modos,
    sum(abordajes) as abordajes,
    sum(monto_q) as monto_q,
    count(distinct fecha) as dias_activos,
    count(distinct if(modo_id = 'TM', fecha, null)) as dias_tm,
    count(distinct if(modo_id = 'TU', fecha, null)) as dias_tu,
    count(distinct if(modo_id = 'MR', fecha, null)) as dias_mr,
    count(distinct if(modo_id = 'AM', fecha, null)) as dias_am,
    count(distinct modo_id) > 1 as es_multimodal
from {{ ref('fct_uso_usuario_dia') }}
where usuario_unificado_sk is not null
group by usuario_unificado_sk
