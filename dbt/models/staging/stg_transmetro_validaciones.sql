-- Staging · validaciones de Transmetro (streaming Kafka -> GCS). Bronze guarda una envolvente JSON por mensaje;
-- raw es la línea CSV original: validacion_id,tarjeta,estacion_id,linea,fecha_hora,tarifa,tipo.
-- Una fila por mensaje de Bronze: no filtra ni deduplica (los ~1 115 duplicados de torniquete llegan a Silver/cuarentena).
with bronze as (
    select
        offset, kafka_ts, clave, archivo, linea_num, sha256_archivo, raw, ingest_ts,
        ingest_date, topico, particion,
        _FILE_NAME as objeto_gcs
    from {{ source('bronze', 'transmetro_validaciones') }}
),
campos as (
    select *, split(raw, ',') as c
    from bronze
)
select
    safe_cast(nullif(trim(c[safe_offset(0)]), '') as int64) as validacion_id,
    nullif(trim(c[safe_offset(1)]), '') as tarjeta,
    nullif(trim(c[safe_offset(2)]), '') as estacion_id,
    nullif(trim(c[safe_offset(3)]), '') as linea,
    safe.parse_datetime('%Y-%m-%d %H:%M:%S', nullif(trim(c[safe_offset(4)]), '')) as fecha_hora,
    safe_cast(nullif(trim(c[safe_offset(5)]), '') as numeric) as tarifa,
    nullif(trim(c[safe_offset(6)]), '') as tipo,
    nullif(trim(c[safe_offset(0)]), '') as validacion_id_raw,
    nullif(trim(c[safe_offset(4)]), '') as fecha_hora_raw,
    nullif(trim(c[safe_offset(5)]), '') as tarifa_raw,
    -- linaje
    'transmetro_validaciones' as fuente,
    archivo,
    objeto_gcs,
    ingest_date,
    to_hex(sha256(raw)) as registro_hash,
    offset as kafka_offset,
    topico as kafka_topico,
    particion as kafka_particion,
    safe_cast(kafka_ts as timestamp) as kafka_ts,
    clave as kafka_clave,
    linea_num,
    sha256_archivo,
    safe_cast(ingest_ts as timestamp) as ingest_ts,
    raw
from campos
