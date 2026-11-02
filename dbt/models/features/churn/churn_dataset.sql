-- Features · Proyecto 2 (ADR-015). Dataset de churn listo para entrenar: una fila por (unidad_id, fecha_corte), con
-- unidad_id = usuario_unificado_sk (persona seudonimizada), las features de churn_features (ventanas <= 28 días, solo
-- datos con fecha < corte) y la etiqueta (1 = sin abordajes en [t, t+30); 0 = con; NULL = horizonte no observado, corte C).
-- Población: churn_poblacion.en_poblacion (>= 2 abordajes en [t-28, t) y sin DELETE previo). Linaje: fecha_referencia y
-- run_id de la corrida. Sin llaves nativas ni n_abordajes_horizonte (fuga). Diccionario en features.churn_diccionario.
{{ config(materialized='table', cluster_by=['corte']) }}

select
    f.*,
    e.etiqueta,
    date('{{ var("fecha_referencia") }}') as fecha_referencia,
    '{{ var("run_id") }}' as run_id
from {{ ref('churn_features') }} as f
inner join {{ ref('churn_poblacion') }} as p
    on p.corte = f.corte and p.unidad_id = f.unidad_id and p.en_poblacion
inner join {{ ref('churn_etiqueta') }} as e
    on e.corte = f.corte and e.unidad_id = f.unidad_id
