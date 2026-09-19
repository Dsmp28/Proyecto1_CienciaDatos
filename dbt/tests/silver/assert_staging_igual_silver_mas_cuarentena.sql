-- Conciliación Staging = Silver + Cuarentena por fuente (restricción dura 2: ningún registro se descarta).
-- Operación: stg_<fuente> = silver_<fuente> + registros_rechazados(fuente).
-- CDC: stg_cdc_padron_usuarios = silver_padron_scd2 + registros_rechazados(cdc_padron_usuarios).
-- Catálogos: los 4 stg de estaciones = silver_estaciones + registros_rechazados(4 fuentes de catálogo).
-- Devuelve las fuentes con diferencia distinta de 0: si devuelve filas, la prueba falla.
with cuarentena as (
    select fuente, count(*) as n
    from {{ ref('registros_rechazados') }}
    group by fuente
),
conteos as (
    select
        'transmetro_validaciones' as fuente,
        (select count(*) from {{ ref('stg_transmetro_validaciones') }}) as filas_staging,
        (select count(*) from {{ ref('silver_transmetro_validaciones') }}) as filas_silver,
        (select coalesce(sum(n), 0) from cuarentena where fuente = 'transmetro_validaciones') as filas_cuarentena
    union all
    select
        'transurbano_transacciones',
        (select count(*) from {{ ref('stg_transurbano_transacciones') }}),
        (select count(*) from {{ ref('silver_transurbano_transacciones') }}),
        (select coalesce(sum(n), 0) from cuarentena where fuente = 'transurbano_transacciones')
    union all
    select
        'metroriel_viajes',
        (select count(*) from {{ ref('stg_metroriel_viajes') }}),
        (select count(*) from {{ ref('silver_metroriel_viajes') }}),
        (select coalesce(sum(n), 0) from cuarentena where fuente = 'metroriel_viajes')
    union all
    select
        'aerometro_boardings',
        (select count(*) from {{ ref('stg_aerometro_boardings') }}),
        (select count(*) from {{ ref('silver_aerometro_boardings') }}),
        (select coalesce(sum(n), 0) from cuarentena where fuente = 'aerometro_boardings')
    union all
    select
        'cdc_padron_usuarios',
        (select count(*) from {{ ref('stg_cdc_padron_usuarios') }}),
        (select count(*) from {{ ref('silver_padron_scd2') }}),
        (select coalesce(sum(n), 0) from cuarentena where fuente = 'cdc_padron_usuarios')
    union all
    select
        'catalogos_estaciones',
        (select count(*) from {{ ref('stg_tm_estaciones') }})
            + (select count(*) from {{ ref('stg_tu_paradas') }})
            + (select count(*) from {{ ref('stg_mr_estaciones') }})
            + (select count(*) from {{ ref('stg_am_estaciones') }}),
        (select count(*) from {{ ref('silver_estaciones') }}),
        (select coalesce(sum(n), 0) from cuarentena
         where fuente in ('tm_estaciones', 'tu_paradas', 'mr_estaciones', 'am_estaciones'))
)
select
    fuente,
    filas_staging,
    filas_silver,
    filas_cuarentena,
    filas_staging - (filas_silver + filas_cuarentena) as diferencia
from conteos
where filas_staging - (filas_silver + filas_cuarentena) != 0
