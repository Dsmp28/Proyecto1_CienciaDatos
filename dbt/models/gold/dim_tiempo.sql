-- Gold · dim_tiempo. Grano: una hora de un día (fecha × hora 0–23). Llave tiempo_sk = AAAAMMDD*100 + hora
-- (p. ej. 2026060107 = 2026-06-01 07:00). El rango de fechas se deriva de los datos (mínimo y máximo de
-- silver_abordajes.fecha, ampliado a la última salida de MetroRiel y a la última operación del padrón para que
-- toda llave de los hechos exista): nunca CURRENT_DATE. Franja y hora pico vienen del seed franjas_horarias;
-- feriados del seed feriados_gt. Día hábil = lunes a viernes y no feriado (definiciones_oficiales.md).
-- Sin partición (≤ 2 000 filas).
with rango as (
    select
        least(
            (select min(fecha) from {{ ref('silver_abordajes') }}),
            (select min(date(vigente_desde)) from {{ ref('silver_padron_scd2') }})
        ) as fecha_min,
        greatest(
            (select max(fecha) from {{ ref('silver_abordajes') }}),
            (select max(date(fecha_hora_salida_local)) from {{ ref('silver_metroriel_viajes') }}),
            (select max(date(vigente_desde)) from {{ ref('silver_padron_scd2') }})
        ) as fecha_max
),
fechas as (
    select fecha
    from rango, unnest(generate_date_array(rango.fecha_min, rango.fecha_max, interval 1 day)) as fecha
),
horas as (
    select hora from unnest(generate_array(0, 23)) as hora
),
franjas as (
    select hora, franja, es_hora_pico from {{ ref('franjas_horarias') }}
),
feriados as (
    select fecha, nombre as nombre_feriado from {{ ref('feriados_gt') }}
),
base as (
    select
        f.fecha,
        h.hora,
        -- BigQuery: DAYOFWEEK 1 = domingo … 7 = sábado; se convierte a ISO 1 = lunes … 7 = domingo
        mod(extract(dayofweek from f.fecha) + 5, 7) + 1 as dia_semana,
        fe.fecha is not null as es_feriado,
        fe.nombre_feriado
    from fechas as f
    cross join horas as h
    left join feriados as fe on fe.fecha = f.fecha
)
select
    cast(format_date('%Y%m%d', b.fecha) as int64) * 100 + b.hora as tiempo_sk,
    b.fecha,
    b.hora,
    datetime(b.fecha, time(b.hora, 0, 0)) as fecha_hora_inicio,
    fr.franja,
    fr.es_hora_pico,
    b.dia_semana,
    case b.dia_semana
        when 1 then 'lunes' when 2 then 'martes' when 3 then 'miércoles' when 4 then 'jueves'
        when 5 then 'viernes' when 6 then 'sábado' when 7 then 'domingo'
    end as dia_semana_nombre,
    b.dia_semana >= 6 as es_fin_de_semana,
    b.es_feriado,
    b.nombre_feriado,
    b.dia_semana <= 5 and not b.es_feriado as es_dia_habil,
    extract(isoweek from b.fecha) as semana_iso,
    extract(month from b.fecha) as mes,
    format_date('%Y-%m', b.fecha) as anio_mes,
    extract(year from b.fecha) as anio
from base as b
join franjas as fr on fr.hora = b.hora
