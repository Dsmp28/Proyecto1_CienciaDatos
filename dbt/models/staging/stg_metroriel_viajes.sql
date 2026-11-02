-- Staging · viajes de MetroRiel (batch, JSON Lines: entrada y salida en la misma fila; exit puede ser null).
-- Una fila por línea de Bronze: no filtra ni deduplica. SAFE.PARSE_JSON: una línea mal formada deja NULL en
-- las columnas tipadas y conserva raw. tiene_salida usa JSON_TYPE para distinguir objeto de null JSON.
-- Recorte (ADR-015): con var('recorte_datos_hasta') se filtra por la fecha de ENTRADA; si la salida cae después del recorte
-- exit_station/exit_ts/duration_s quedan nulos y tiene_salida=false (archivo truncado: val_metroriel_viajes lo manda a R04).
-- Con la var nula no hace nada. Las columnas *_raw y raw conservan el registro original.
{%- set entrada_local = "safe.parse_datetime('%Y-%m-%dT%H:%M:%S', json_value(j, '$.entry.ts'))" %}
{%- set salida_local = "safe.parse_datetime('%Y-%m-%dT%H:%M:%S', json_value(j, '$.exit.ts'))" %}
{%- set salida_tarde = "date(" ~ salida_local ~ ") > date('" ~ var('recorte_datos_hasta') ~ "')" %}
with bronze as (
    select raw, ingest_date, _FILE_NAME as objeto_gcs
    from {{ source('bronze', 'metroriel_viajes') }}
),
doc as (
    select raw, ingest_date, objeto_gcs, safe.parse_json(raw) as j
    from bronze
)
select
    safe_cast(json_value(j, '$.trip_id') as int64) as trip_id,
    json_value(j, '$.card') as card,
    safe_cast(json_value(j, '$.entry.station') as int64) as entry_station,
    safe.parse_datetime('%Y-%m-%dT%H:%M:%S', json_value(j, '$.entry.ts')) as entry_ts,
    {{ recortar_salida("safe_cast(json_value(j, '$.exit.station') as int64)", salida_tarde) }} as exit_station,
    {{ recortar_salida(salida_local, salida_tarde) }} as exit_ts,
    safe_cast(json_value(j, '$.fare_gtq') as numeric) as fare_gtq,
    {{ recortar_salida("safe_cast(json_value(j, '$.duration_s') as int64)", salida_tarde) }} as duration_s,
    {{ recortar_salida("coalesce(json_type(json_query(j, '$.exit')) = 'object', false)", salida_tarde, 'false') }} as tiene_salida,
    json_value(j, '$.trip_id') as trip_id_raw,
    json_value(j, '$.entry.ts') as entry_ts_raw,
    json_value(j, '$.exit.ts') as exit_ts_raw,
    json_value(j, '$.fare_gtq') as fare_gtq_raw,
    json_value(j, '$.duration_s') as duration_s_raw,
    -- linaje
    'metroriel_viajes' as fuente,
    regexp_extract(objeto_gcs, r'[^/]+$') as archivo,
    objeto_gcs,
    ingest_date,
    to_hex(sha256(raw)) as registro_hash,
    row_number() over (partition by objeto_gcs, raw order by raw) as n_repeticion,
    raw
from doc{{ donde_recorte(entrada_local) }}
