-- Features · Proyecto 2 (ADR-015). Abordajes válidos (silver_abordajes) de cada persona (unidad_id = usuario_unificado_sk)
-- para cada corte t, en [t - ventana_max_dias, t + horizonte_dias). tramo = 'ventana' (fecha < t, insumo de features) o
-- 'horizonte' (fecha >= t, solo para la etiqueta). dias_antes_corte = DATE_DIFF(t, fecha, DAY): 1..28 en la ventana.
-- Tabla de trabajo: conserva modo/llave nativa para contar tarjetas; la salida final (churn_dataset) no las expone.
-- Solo Silver y variables (nunca Gold ni CURRENT_DATE). Abordajes sin persona resuelta (unidad_id nulo) no entran.
{{ config(materialized='table', cluster_by=['corte']) }}

with cortes as (
    {{ cortes_cte() }}
),
usuarios as (
    select modo_id, llave_nativa, usuario_unificado_sk as unidad_id
    from {{ ref('silver_usuarios') }}
    where usuario_unificado_sk is not null
)
select
    c.corte,
    c.fecha_corte,
    u.unidad_id,
    a.abordaje_id,
    a.modo_id,
    a.llave_nativa,
    a.fecha,
    a.hora,
    a.fecha_hora_local,
    a.monto_q,
    a.zona_id,
    a.estacion_sk,
    coalesce(a.es_transbordo_interno, false) as es_transbordo_interno,
    date_diff(c.fecha_corte, a.fecha, day) as dias_antes_corte,
    if(a.fecha < c.fecha_corte, 'ventana', 'horizonte') as tramo
from {{ ref('silver_abordajes') }} as a
inner join usuarios as u on u.modo_id = a.modo_id and u.llave_nativa = a.llave_nativa
inner join cortes as c
    on a.fecha >= date_sub(c.fecha_corte, interval {{ var('ventana_max_dias') }} day)
   and a.fecha < date_add(c.fecha_corte, interval {{ var('horizonte_dias') }} day)
