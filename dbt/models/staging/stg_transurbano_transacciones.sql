-- Staging · transacciones de Transurbano (batch, CSV: fecha dd/mm/yyyy, hora separada, monto en centavos,
-- estado como código numérico). Una fila por línea de Bronze: no filtra ni deduplica (cod_parada vacío y fechas
-- del futuro se conservan; Silver decide). Fecha/hora con SAFE.PARSE_DATETIME; crudos en fecha_raw / hora_raw.
with bronze as (
    select raw, ingest_date, _FILE_NAME as objeto_gcs
    from {{ source('bronze', 'transurbano_transacciones') }}
),
campos as (
    select raw, ingest_date, objeto_gcs, split(raw, ',') as c
    from bronze
),
tipado as (
    select
        nullif(trim(c[safe_offset(0)]), '') as fecha_raw,
        nullif(trim(c[safe_offset(1)]), '') as hora_raw,
        nullif(trim(c[safe_offset(2)]), '') as num_tarjeta,
        nullif(trim(c[safe_offset(3)]), '') as cod_parada,
        nullif(trim(c[safe_offset(4)]), '') as ruta,
        nullif(trim(c[safe_offset(5)]), '') as monto_centavos_raw,
        nullif(trim(c[safe_offset(6)]), '') as cod_estado_raw,
        raw, ingest_date, objeto_gcs
    from campos
)
select
    fecha_raw,
    hora_raw,
    safe.parse_datetime('%d/%m/%Y %H:%M:%S', concat(fecha_raw, ' ', hora_raw)) as fecha_hora,
    num_tarjeta,
    cod_parada,
    ruta,
    safe_cast(monto_centavos_raw as int64) as monto_centavos,
    safe_cast(safe_cast(monto_centavos_raw as int64) as numeric) / 100 as monto_q,
    monto_centavos_raw,
    safe_cast(cod_estado_raw as int64) as cod_estado,
    cod_estado_raw,
    case safe_cast(cod_estado_raw as int64)
        when 1 then 'OK'
        when 2 then 'OK'
        when 3 then 'OK'
        when 7 then 'SALDO_INSUF'
        when 9 then 'TARJETA_INVALIDA'
        else 'DESCONOCIDO'
    end as estado_desc,
    safe_cast(cod_estado_raw as int64) in (1, 2, 3) as es_cobro_exitoso,
    -- linaje
    'transurbano_transacciones' as fuente,
    regexp_extract(objeto_gcs, r'[^/]+$') as archivo,
    objeto_gcs,
    ingest_date,
    to_hex(sha256(raw)) as registro_hash,
    row_number() over (partition by objeto_gcs, raw order by raw) as n_repeticion,
    raw
from tipado
