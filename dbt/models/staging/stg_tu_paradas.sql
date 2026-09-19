-- Staging · catálogo de paradas de Transurbano (batch, CSV). Sector en mayúsculas tal como llega (Z4, MIXCO).
-- Una fila por línea de Bronze: no filtra ni deduplica.
with bronze as (
    select raw, ingest_date, _FILE_NAME as objeto_gcs
    from {{ source('bronze', 'tu_paradas') }}
),
campos as (
    select raw, ingest_date, objeto_gcs, split(raw, ',') as c
    from bronze
)
select
    nullif(trim(c[safe_offset(0)]), '') as cod_parada,
    nullif(trim(c[safe_offset(1)]), '') as descripcion,
    nullif(trim(c[safe_offset(2)]), '') as ruta,
    nullif(trim(c[safe_offset(3)]), '') as sector_origen,
    -- linaje
    'tu_paradas' as fuente,
    regexp_extract(objeto_gcs, r'[^/]+$') as archivo,
    objeto_gcs,
    ingest_date,
    to_hex(sha256(raw)) as registro_hash,
    row_number() over (partition by objeto_gcs, raw order by raw) as n_repeticion,
    raw
from campos
