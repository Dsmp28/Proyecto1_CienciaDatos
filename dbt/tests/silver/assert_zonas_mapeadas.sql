-- Regla R05: todo valor de zona/sector/district de los 4 catálogos de staging y toda zona_residencia del padrón
-- deben existir en el seed zonas_mapeo. Las filas afectadas además van a cuarentena (val_estaciones,
-- val_cdc_padron_usuarios); esta prueba pone la corrida en rojo, como exige el enunciado.
-- Devuelve los valores sin mapear: si devuelve filas, la prueba falla.
with valores as (
    select 'tm_estaciones' as origen, zona_origen as valor from {{ ref('stg_tm_estaciones') }}
    union all
    select 'tu_paradas', sector_origen from {{ ref('stg_tu_paradas') }}
    union all
    select 'mr_estaciones', zona_origen from {{ ref('stg_mr_estaciones') }}
    union all
    select 'am_estaciones', district_origen from {{ ref('stg_am_estaciones') }}
    union all
    select 'cdc_padron_usuarios', zona_residencia from {{ ref('stg_cdc_padron_usuarios') }}
    where zona_residencia is not null
)
select
    v.origen,
    v.valor,
    count(*) as n_filas
from valores as v
left join {{ ref('zonas_mapeo') }} as m on m.valor_origen = v.valor
where m.valor_origen is null
group by v.origen, v.valor
