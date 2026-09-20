-- Gold · agg_metroriel_zonas. Agregado para Tableau (pregunta 4: caso MetroRiel, zonas 12, 8, 1, 6 y 17 frente al resto).
-- Una fila por zona de dim_zona con abordajes por modo (pivot de fct_abordaje), abordajes totales, usuarios distintos
-- (no aditiva), estaciones de MetroRiel y ranking por demanda total (1 = zona con más abordajes).
-- es_zona_metroriel = las cinco zonas por las que corre la línea de MetroRiel según el enunciado.
with demanda as (
    select
        zona_id,
        countif(modo_id = 'TM') as abordajes_tm,
        countif(modo_id = 'TU') as abordajes_tu,
        countif(modo_id = 'MR') as abordajes_mr,
        countif(modo_id = 'AM') as abordajes_am,
        count(*) as abordajes_totales,
        count(distinct usuario_sk) as usuarios_distintos,
        count(distinct usuario_unificado_sk) as personas_distintas
    from {{ ref('fct_abordaje') }}
    group by zona_id
),
estaciones_mr as (
    select zona_id, n_estaciones as n_estaciones_mr
    from {{ ref('fct_cobertura_zona_modo') }}
    where modo_id = 'MR'
)
select
    z.zona_id,
    z.zona_nombre,
    z.tipo,
    z.orden,
    z.zona_id in ('GT-Z12', 'GT-Z08', 'GT-Z01', 'GT-Z06', 'GT-Z17') as es_zona_metroriel,
    coalesce(e.n_estaciones_mr, 0) as n_estaciones_mr,
    coalesce(d.abordajes_tm, 0) as abordajes_tm,
    coalesce(d.abordajes_tu, 0) as abordajes_tu,
    coalesce(d.abordajes_mr, 0) as abordajes_mr,
    coalesce(d.abordajes_am, 0) as abordajes_am,
    coalesce(d.abordajes_totales, 0) as abordajes_totales,
    coalesce(d.usuarios_distintos, 0) as usuarios_distintos,
    coalesce(d.personas_distintas, 0) as personas_distintas,
    round(100 * coalesce(d.abordajes_mr, 0) / nullif(d.abordajes_totales, 0), 2) as pct_metroriel,
    rank() over (order by coalesce(d.abordajes_totales, 0) desc, z.orden) as ranking
from {{ ref('dim_zona') }} as z
left join demanda as d on d.zona_id = z.zona_id
left join estaciones_mr as e on e.zona_id = z.zona_id
