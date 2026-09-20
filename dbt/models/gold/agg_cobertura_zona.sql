-- Gold · agg_cobertura_zona. Agregado para Tableau (pregunta 2: cobertura y zonas sin servicio). Una fila por zona de
-- dim_zona (26), con LEFT JOIN a fct_cobertura_zona_modo (oferta: estaciones por modo) y a fct_abordaje (demanda real).
-- sin_servicio = ninguna estación ni parada de ningún modo. Además distingue zonas con oferta pero sin demanda
-- (tiene_estacion_sin_demanda) para contrastar catálogo y operación.
with cobertura as (
    select
        zona_id,
        count(*) as n_modos_con_servicio,
        sum(n_estaciones) as n_estaciones,
        string_agg(modo_id, ',' order by modo_id) as modos_con_servicio
    from {{ ref('fct_cobertura_zona_modo') }}
    group by zona_id
),
demanda as (
    select
        zona_id,
        sum(abordajes) as abordajes_totales,
        sum(monto_q) as monto_q_total,
        count(distinct usuario_sk) as usuarios_distintos,
        count(distinct modo_id) as n_modos_con_demanda
    from {{ ref('fct_abordaje') }}
    group by zona_id
)
select
    z.zona_id,
    z.zona_nombre,
    z.tipo,
    z.municipio,
    z.orden,
    coalesce(c.n_modos_con_servicio, 0) as n_modos_con_servicio,
    coalesce(c.n_estaciones, 0) as n_estaciones,
    c.modos_con_servicio,
    coalesce(d.abordajes_totales, 0) as abordajes_totales,
    coalesce(d.monto_q_total, 0) as monto_q_total,
    coalesce(d.usuarios_distintos, 0) as usuarios_distintos,
    coalesce(d.n_modos_con_demanda, 0) as n_modos_con_demanda,
    c.zona_id is not null as tiene_servicio,
    c.zona_id is null as sin_servicio,
    c.zona_id is not null and d.zona_id is null as tiene_estacion_sin_demanda
from {{ ref('dim_zona') }} as z
left join cobertura as c on c.zona_id = z.zona_id
left join demanda as d on d.zona_id = z.zona_id
