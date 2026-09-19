-- Validación · Aerómetro. TODAS las filas de stg_aerometro_boardings con `regla_id` (NULL = válida) y `motivo`.
-- Orden: R07 → R08 → R03 (sobre la fecha local, ya convertida desde UTC en staging) → R06 → R09 → R10.
with base as (
    select * from {{ ref('stg_aerometro_boardings') }}
),
catalogo as (
    select distinct station_code from {{ ref('stg_am_estaciones') }}
),
etiquetado as (
    select
        b.*,
        case
            when b.user_hash is null then 'R07'
            when b.timestamp_utc is null then 'R08'
            when date(b.fecha_hora_local) >= date('{{ var("fecha_referencia") }}') then 'R03'
            when c.station_code is null then 'R06'
            when b.fare is null or b.fare < 0 then 'R09'
            when row_number() over (
                partition by b.archivo, b.sha256_archivo, b.linea_num order by b.kafka_offset
            ) > 1 then 'R10'
        end as regla_id
    from base as b
    left join catalogo as c on c.station_code = b.station_code
)
select
    *,
    case regla_id
        when 'R07' then 'R07 llave de usuario nula'
        when 'R08' then 'R08 fecha no parseable'
        when 'R03' then 'R03 fecha posterior a la fecha de referencia'
        when 'R06' then 'R06 estacion o parada no catalogada'
        when 'R09' then 'R09 monto invalido'
        when 'R10' then 'R10 duplicado de entrega'
    end as motivo
from etiquetado
