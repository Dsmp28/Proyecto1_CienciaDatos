-- Validación · MetroRiel. TODAS las filas de stg_metroriel_viajes con `regla_id` (NULL = válida) y `motivo`.
-- Orden: R07 → R08 → R03 → R06 (entrada, o salida si existe) → R09 → R04 (viaje sin salida).
with base as (
    select * from {{ ref('stg_metroriel_viajes') }}
),
catalogo as (
    select distinct id_estacion from {{ ref('stg_mr_estaciones') }}
),
etiquetado as (
    select
        b.*,
        case
            when b.card is null then 'R07'
            when b.entry_ts is null then 'R08'
            when date(b.entry_ts) >= date('{{ var("fecha_referencia") }}') then 'R03'
            when ce.id_estacion is null then 'R06'
            when b.tiene_salida and cs.id_estacion is null then 'R06'
            when b.fare_gtq is null or b.fare_gtq < 0 then 'R09'
            when not b.tiene_salida then 'R04'
        end as regla_id
    from base as b
    left join catalogo as ce on ce.id_estacion = b.entry_station
    left join catalogo as cs on cs.id_estacion = b.exit_station
)
select
    *,
    case regla_id
        when 'R07' then 'R07 llave de usuario nula'
        when 'R08' then 'R08 fecha no parseable'
        when 'R03' then 'R03 fecha posterior a la fecha de referencia'
        when 'R06' then 'R06 estacion o parada no catalogada'
        when 'R09' then 'R09 monto invalido'
        when 'R04' then 'R04 viaje sin salida'
    end as motivo
from etiquetado
