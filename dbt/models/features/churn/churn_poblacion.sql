-- Features · Proyecto 2 (ADR-015). Embudo de población por corte t: toda persona con >= 1 abordaje válido en
-- [t-28, t). en_poblacion = n_abordajes_28d >= 2 y ninguna baja (DELETE) del CDC con vigente_desde < t en NINGUNA
-- tarjeta de padrón de la persona (lectura literal del enunciado). estado_padron_ultimo_a_t = estado (ACTIVA/INACTIVA)
-- del último evento de padrón antes de t (orden seq desc, tarjeta; 'SIN_PADRON' si no hay), para cuantificar la
-- lectura alternativa "baja vigente a t". Padrón -> persona: (modo_id = formato_tarjeta, llave_nativa = tarjeta)
-- contra silver_usuarios. Solo eventos con vigente_desde < t: sin vigente_hasta ni es_vigente (estado final).
{{ config(materialized='table', cluster_by=['corte']) }}

with cortes as (
    {{ cortes_cte() }}
),
ventana as (
    select corte, fecha_corte, unidad_id, count(*) as n_abordajes_28d
    from {{ ref('churn_eventos') }}
    where tramo = 'ventana' and dias_antes_corte between 1 and {{ var('ventana_max_dias') }}
    group by corte, fecha_corte, unidad_id
),
usuarios as (
    select modo_id, llave_nativa, usuario_unificado_sk as unidad_id
    from {{ ref('silver_usuarios') }}
    where usuario_unificado_sk is not null
),
padron_previo as (
    select c.corte, c.fecha_corte, u.unidad_id, p.op, p.estado, p.seq, p.tarjeta
    from {{ ref('silver_padron_scd2') }} as p
    inner join usuarios as u on u.modo_id = p.modo_id and u.llave_nativa = p.tarjeta
    inner join cortes as c on p.vigente_desde < datetime(c.fecha_corte)
),
padron_agregado as (
    select
        corte, fecha_corte, unidad_id,
        countif(op = 'DELETE') as n_delete_previos,
        array_agg(estado order by seq desc, tarjeta limit 1)[offset(0)] as estado_padron_ultimo_a_t
    from padron_previo
    group by corte, fecha_corte, unidad_id
)
select
    v.corte,
    v.fecha_corte,
    v.unidad_id,
    v.n_abordajes_28d,
    coalesce(p.n_delete_previos, 0) as n_delete_previos,
    coalesce(p.n_delete_previos, 0) > 0 as tiene_delete_previo,
    coalesce(p.estado_padron_ultimo_a_t, 'SIN_PADRON') as estado_padron_ultimo_a_t,
    v.n_abordajes_28d >= 2 and coalesce(p.n_delete_previos, 0) = 0 as en_poblacion
from ventana as v
left join padron_agregado as p
    on p.corte = v.corte and p.unidad_id = v.unidad_id
