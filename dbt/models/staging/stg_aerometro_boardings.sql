-- Staging · abordajes de Aerómetro (streaming Kafka -> GCS). Bronze guarda una envolvente JSON por mensaje;
-- raw es la línea CSV original en inglés: boarding_id,user_hash,station_code,axis,timestamp_utc,cabin_number,fare.
-- timestamp_utc llega en UTC ('...Z'); fecha_hora_local = DATETIME(ts, tz_local) (ADR-010).
-- Una fila por mensaje de Bronze: no filtra ni deduplica.
with bronze as (
    select
        offset, kafka_ts, clave, archivo, linea_num, sha256_archivo, raw, ingest_ts,
        ingest_date, topico, particion,
        _FILE_NAME as objeto_gcs
    from {{ source('bronze', 'aerometro_boardings') }}
),
campos as (
    select *, split(raw, ',') as c
    from bronze
),
tipado as (
    select
        *,
        safe.parse_timestamp('%Y-%m-%dT%H:%M:%SZ', nullif(trim(c[safe_offset(4)]), '')) as ts_utc
    from campos
)
select
    safe_cast(nullif(trim(c[safe_offset(0)]), '') as int64) as boarding_id,
    nullif(trim(c[safe_offset(1)]), '') as user_hash,
    nullif(trim(c[safe_offset(2)]), '') as station_code,
    nullif(trim(c[safe_offset(3)]), '') as axis,
    ts_utc as timestamp_utc,
    datetime(ts_utc, '{{ var("tz_local") }}') as fecha_hora_local,
    safe_cast(nullif(trim(c[safe_offset(5)]), '') as int64) as cabin_number,
    safe_cast(nullif(trim(c[safe_offset(6)]), '') as numeric) as fare,
    nullif(trim(c[safe_offset(0)]), '') as boarding_id_raw,
    nullif(trim(c[safe_offset(4)]), '') as timestamp_utc_raw,
    nullif(trim(c[safe_offset(5)]), '') as cabin_number_raw,
    nullif(trim(c[safe_offset(6)]), '') as fare_raw,
    -- linaje
    'aerometro_boardings' as fuente,
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
from tipado
