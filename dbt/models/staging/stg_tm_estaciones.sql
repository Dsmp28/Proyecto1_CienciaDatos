-- Staging · catálogo de estaciones de Transmetro (batch, CSV).
-- Una fila por línea de Bronze: no filtra ni deduplica. Tipado con SAFE_CAST; el valor crudo se conserva en <col>_raw.
with bronze as (
    select raw, ingest_date, _FILE_NAME as objeto_gcs
    from {{ source('bronze', 'tm_estaciones') }}
),
campos as (
    select
        raw,
        ingest_date,
        objeto_gcs,
        split(raw, ',') as c
    from bronze
)
select
    nullif(trim(c[safe_offset(0)]), '') as estacion_id,
    nullif(trim(c[safe_offset(1)]), '') as nombre,
    nullif(trim(c[safe_offset(2)]), '') as linea,
    nullif(trim(c[safe_offset(3)]), '') as zona_origen,
    safe_cast(nullif(trim(c[safe_offset(4)]), '') as float64) as lat,
    safe_cast(nullif(trim(c[safe_offset(5)]), '') as float64) as lon,
    nullif(trim(c[safe_offset(4)]), '') as lat_raw,
    nullif(trim(c[safe_offset(5)]), '') as lon_raw,
    -- linaje
    'tm_estaciones' as fuente,
    regexp_extract(objeto_gcs, r'[^/]+$') as archivo,
    objeto_gcs,
    ingest_date,
    to_hex(sha256(raw)) as registro_hash,
    row_number() over (partition by objeto_gcs, raw order by raw) as n_repeticion,
    raw
from campos
