-- Validación · Transmetro (reglas de docs/governance/reglas_calidad.md). TODAS las filas de stg_transmetro_validaciones
-- con `regla_id` (NULL = válida) y `motivo`. Una fila, una regla: la primera que incumple en el orden
-- R07 → R08 → R03 → R06 → R09 → R10 → R01. Silver toma las filas con regla_id NULL; cuarentena las demás.
-- R01 (duplicado de torniquete) se evalúa solo entre filas que superaron las reglas anteriores: se conserva
-- la primera aparición de cada validacion_id por (linea_num, kafka_offset).
with base as (
    select * from {{ ref('stg_transmetro_validaciones') }}
),
catalogo as (
    select distinct estacion_id from {{ ref('stg_tm_estaciones') }}
),
previas as (
    select
        b.*,
        case
            when b.tarjeta is null then 'R07'
            when b.fecha_hora is null then 'R08'
            when date(b.fecha_hora) >= date('{{ var("fecha_referencia") }}') then 'R03'
            when c.estacion_id is null then 'R06'
            when b.tarifa is null or b.tarifa < 0 then 'R09'
            when row_number() over (
                partition by b.archivo, b.sha256_archivo, b.linea_num order by b.kafka_offset
            ) > 1 then 'R10'
        end as regla_previa
    from base as b
    left join catalogo as c on c.estacion_id = b.estacion_id
),
torniquete as (
    select
        *,
        case
            when regla_previa is null and validacion_id is not null
                and row_number() over (
                    partition by validacion_id, regla_previa is null order by linea_num, kafka_offset
                ) > 1
            then 'R01'
        end as regla_torniquete
    from previas
),
etiquetado as (
    select
        * except (regla_previa, regla_torniquete),
        coalesce(regla_previa, regla_torniquete) as regla_id
    from torniquete
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
        when 'R01' then 'R01 duplicado de torniquete'
    end as motivo
from etiquetado
