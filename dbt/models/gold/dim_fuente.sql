-- Gold · dim_fuente. Grano: un objeto crudo ingerido a Bronze (fuente, archivo, objeto_gcs, ingest_date) observado en
-- Silver. Es la dimensión de linaje (restricción dura 4): todo hecho lleva fuente_sk y desde aquí se llega al archivo
-- crudo y a la ruta gs:// de Bronze. En streaming (Transmetro, Aerómetro) un mismo archivo lógico se reparte en varios
-- objetos jsonl (uno por lote de offsets de Kafka), por eso el grano incluye objeto_gcs.
-- fuente_sk = TO_HEX(SHA256(fuente|archivo|objeto_gcs|ingest_date)); la misma expresión se usa en cada hecho.
with observado as (
    select fuente, archivo, objeto_gcs, ingest_date, count(*) as n_filas
    from (
        select fuente, archivo, objeto_gcs, ingest_date from {{ ref('silver_abordajes') }}
        union all
        select fuente, archivo, objeto_gcs, ingest_date from {{ ref('silver_metroriel_viajes') }}
        union all
        select fuente, archivo, objeto_gcs, ingest_date from {{ ref('silver_estaciones') }}
        union all
        select fuente, archivo, objeto_gcs, ingest_date from {{ ref('silver_padron_scd2') }}
    )
    group by fuente, archivo, objeto_gcs, ingest_date
)
select
    to_hex(sha256(concat(fuente, '|', archivo, '|', coalesce(objeto_gcs, ''), '|', cast(ingest_date as string)))) as fuente_sk,
    fuente,
    archivo,
    objeto_gcs,
    ingest_date,
    case fuente
        when 'transmetro_validaciones' then 'streaming'
        when 'aerometro_boardings' then 'streaming'
        when 'cdc_padron_usuarios' then 'cdc'
        else 'batch'
    end as via,
    case fuente
        when 'transmetro_validaciones' then 'operacion'
        when 'transurbano_transacciones' then 'operacion'
        when 'metroriel_viajes' then 'operacion'
        when 'aerometro_boardings' then 'operacion'
        when 'cdc_padron_usuarios' then 'padron'
        else 'catalogo'
    end as tipo_contenido,
    case fuente
        when 'transmetro_validaciones' then 'TM'
        when 'tm_estaciones' then 'TM'
        when 'cdc_padron_usuarios' then 'TM'
        when 'transurbano_transacciones' then 'TU'
        when 'tu_paradas' then 'TU'
        when 'metroriel_viajes' then 'MR'
        when 'mr_estaciones' then 'MR'
        when 'aerometro_boardings' then 'AM'
        when 'am_estaciones' then 'AM'
    end as modo_id,
    n_filas as n_filas_silver
from observado
