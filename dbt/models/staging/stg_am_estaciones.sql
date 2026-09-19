-- Staging · catálogo de estaciones de Aerómetro (batch, CSV en inglés). Se conservan los nombres de origen.
-- Una fila por línea de Bronze: no filtra ni deduplica.
with bronze as (
    select raw, ingest_date, _FILE_NAME as objeto_gcs
    from {{ source('bronze', 'am_estaciones') }}
),
campos as (
    select raw, ingest_date, objeto_gcs, split(raw, ',') as c
    from bronze
)
select
    nullif(trim(c[safe_offset(0)]), '') as station_code,
    nullif(trim(c[safe_offset(1)]), '') as station_name,
    nullif(trim(c[safe_offset(2)]), '') as axis,
    nullif(trim(c[safe_offset(3)]), '') as district_origen,
    -- linaje
    'am_estaciones' as fuente,
    regexp_extract(objeto_gcs, r'[^/]+$') as archivo,
    objeto_gcs,
    ingest_date,
    to_hex(sha256(raw)) as registro_hash,
    row_number() over (partition by objeto_gcs, raw order by raw) as n_repeticion,
    raw
from campos
