-- Staging · catálogo de estaciones de MetroRiel (batch, CSV). id_estacion y km tipados con SAFE_CAST.
-- Una fila por línea de Bronze: no filtra ni deduplica.
with bronze as (
    select raw, ingest_date, _FILE_NAME as objeto_gcs
    from {{ source('bronze', 'mr_estaciones') }}
),
campos as (
    select raw, ingest_date, objeto_gcs, split(raw, ',') as c
    from bronze
)
select
    safe_cast(nullif(trim(c[safe_offset(0)]), '') as int64) as id_estacion,
    nullif(trim(c[safe_offset(1)]), '') as nombre_estacion,
    nullif(trim(c[safe_offset(2)]), '') as zona_origen,
    safe_cast(nullif(trim(c[safe_offset(3)]), '') as float64) as km,
    nullif(trim(c[safe_offset(0)]), '') as id_estacion_raw,
    nullif(trim(c[safe_offset(3)]), '') as km_raw,
    -- linaje
    'mr_estaciones' as fuente,
    regexp_extract(objeto_gcs, r'[^/]+$') as archivo,
    objeto_gcs,
    ingest_date,
    to_hex(sha256(raw)) as registro_hash,
    row_number() over (partition by objeto_gcs, raw order by raw) as n_repeticion,
    raw
from campos
