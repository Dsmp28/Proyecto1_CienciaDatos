-- Validación · Transurbano. TODAS las filas de stg_transurbano_transacciones con `regla_id` (NULL = válida) y `motivo`.
-- Orden: R07 → R08 → R03 → R02 → R06 → R09. Los cobros no exitosos (cod_estado 7 y 9) NO se rechazan: son hechos
-- reales de la operación (ADR-010); Silver los conserva y no cuentan como viaje.
with base as (
    select * from {{ ref('stg_transurbano_transacciones') }}
),
catalogo as (
    select distinct cod_parada from {{ ref('stg_tu_paradas') }}
),
etiquetado as (
    select
        b.*,
        case
            when b.num_tarjeta is null then 'R07'
            when b.fecha_hora is null then 'R08'
            when date(b.fecha_hora) >= date('{{ var("fecha_referencia") }}') then 'R03'
            when b.cod_parada is null then 'R02'
            when c.cod_parada is null then 'R06'
            when b.monto_centavos is null or b.monto_centavos < 0 then 'R09'
        end as regla_id
    from base as b
    left join catalogo as c on c.cod_parada = b.cod_parada
)
select
    *,
    case regla_id
        when 'R07' then 'R07 llave de usuario nula'
        when 'R08' then 'R08 fecha no parseable'
        when 'R03' then 'R03 fecha posterior a la fecha de referencia'
        when 'R02' then 'R02 codigo de parada nulo'
        when 'R06' then 'R06 estacion o parada no catalogada'
        when 'R09' then 'R09 monto invalido'
    end as motivo
from etiquetado
