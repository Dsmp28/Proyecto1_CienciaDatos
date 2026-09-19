-- Staging · log de CDC del padrón de usuarios (CSV: seq,commit_ts,op,tarjeta,perfil,zona_residencia,estado).
-- Una fila por operación de Bronze: no filtra ni deduplica; los DELETE llegan sin cuerpo (perfil/zona/estado NULL).
-- Implementa ADR-008: la columna tarjeta mezcla formatos de tres operadores; se clasifica en formato_tarjeta y
-- se extrae el identificador base compartido (usuario_base_id) que vincula tarjetas entre modos.
with bronze as (
    select raw, ingest_date, _FILE_NAME as objeto_gcs
    from {{ source('bronze', 'cdc_padron_usuarios') }}
),
campos as (
    select raw, ingest_date, objeto_gcs, split(raw, ',') as c
    from bronze
),
tipado as (
    select
        nullif(trim(c[safe_offset(0)]), '') as seq_raw,
        nullif(trim(c[safe_offset(1)]), '') as commit_ts_raw,
        nullif(trim(c[safe_offset(2)]), '') as op,
        nullif(trim(c[safe_offset(3)]), '') as tarjeta,
        nullif(trim(c[safe_offset(4)]), '') as perfil,
        nullif(trim(c[safe_offset(5)]), '') as zona_residencia,
        nullif(trim(c[safe_offset(6)]), '') as estado,
        raw, ingest_date, objeto_gcs
    from campos
),
clasificado as (
    select
        *,
        case
            when regexp_contains(tarjeta, r'^TC-\d{8}$') then 'TM'
            when regexp_contains(tarjeta, r'^\d{10}$') then 'TU'
            when regexp_contains(tarjeta, r'^MR\d{7}$') then 'MR'
            when tarjeta = 'SIN-TARJETA' then 'SIN'
            else 'DESCONOCIDO'
        end as formato_tarjeta
    from tipado
)
select
    safe_cast(seq_raw as int64) as seq,
    seq_raw,
    safe.parse_datetime('%Y-%m-%dT%H:%M:%S', commit_ts_raw) as commit_ts,
    commit_ts_raw,
    op,
    tarjeta,
    perfil,
    zona_residencia,
    estado,
    formato_tarjeta,
    case
        when formato_tarjeta in ('TM', 'TU', 'MR')
            then safe_cast(regexp_extract(tarjeta, r'^(?:TC-|MR)?(\d+)$') as int64)
        else null
    end as usuario_base_id,
    -- linaje
    'cdc_padron_usuarios' as fuente,
    regexp_extract(objeto_gcs, r'[^/]+$') as archivo,
    objeto_gcs,
    ingest_date,
    to_hex(sha256(raw)) as registro_hash,
    row_number() over (partition by objeto_gcs, raw order by raw) as n_repeticion,
    raw
from clasificado
