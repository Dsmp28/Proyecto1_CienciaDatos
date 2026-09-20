-- Gold · dim_zona. Grano: una zona conformada. Universo completo del seed zonas (26 filas: 22 zonas de la ciudad
-- y 4 municipios), incluidas las que no tienen ningún dato, para que "zona sin servicio" sea una fila y no una
-- ausencia. n_estaciones_total y modos_con_servicio se calculan desde silver_estaciones (catálogos conformados).
with estaciones as (
    select
        zona_id,
        count(*) as n_estaciones_total,
        count(distinct modo_id) as n_modos_con_servicio,
        string_agg(distinct modo_id, ',' order by modo_id) as modos_con_servicio
    from {{ ref('silver_estaciones') }}
    group by zona_id
)
select
    z.zona_id,
    z.zona_nombre,
    z.tipo,
    z.municipio,
    z.presente_en_datos,
    z.orden,
    coalesce(e.n_estaciones_total, 0) as n_estaciones_total,
    coalesce(e.n_modos_con_servicio, 0) as n_modos_con_servicio,
    e.modos_con_servicio,
    e.zona_id is not null as tiene_servicio
from {{ ref('zonas') }} as z
left join estaciones as e on e.zona_id = z.zona_id
