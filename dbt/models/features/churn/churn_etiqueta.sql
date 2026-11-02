-- Features · Proyecto 2 (ADR-015). Etiqueta de churn solo para la población (en_poblacion) de cada corte t:
-- 1 = ningún abordaje válido en ningún operador en [t, t + horizonte_dias); 0 = al menos uno; NULL = el horizonte no
-- está completamente observado (t + horizonte_dias > fecha_referencia; corte C). n_abordajes_horizonte solo se usa
-- aquí: NO pasa a churn_dataset (sería fuga). Nunca CURRENT_DATE: la fecha de referencia es var('fecha_referencia').
{{ config(materialized='table', cluster_by=['corte']) }}

with poblacion as (
    select corte, fecha_corte, unidad_id
    from {{ ref('churn_poblacion') }}
    where en_poblacion
),
horizonte as (
    select corte, unidad_id, count(*) as n_abordajes_horizonte
    from {{ ref('churn_eventos') }}
    where tramo = 'horizonte'
    group by corte, unidad_id
)
select
    p.corte,
    p.fecha_corte,
    p.unidad_id,
    coalesce(h.n_abordajes_horizonte, 0) as n_abordajes_horizonte,
    case
        when date_add(p.fecha_corte, interval {{ var('horizonte_dias') }} day) > date('{{ var("fecha_referencia") }}') then null
        when coalesce(h.n_abordajes_horizonte, 0) = 0 then 1
        else 0
    end as etiqueta
from poblacion as p
left join horizonte as h on h.corte = p.corte and h.unidad_id = p.unidad_id
