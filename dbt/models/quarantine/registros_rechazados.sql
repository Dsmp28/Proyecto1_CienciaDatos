-- Cuarentena · TODOS los registros rechazados por las reglas R01–R11 (restricción dura 2: ningún registro se
-- descarta). UNION de las filas con regla_id NOT NULL de los modelos val_* (operación, CDC y catálogos), con el
-- registro original (raw), fuente, archivo, posición (linea_num en streaming; kafka_offset), regla, motivo, llave
-- nativa para auditoría, ingest_date, run_id y ts_cuarentena. Se reconstruye completa en cada corrida.
-- ts_cuarentena: var('run_ts') si Airflow la pasa; si no, TIMESTAMP(fecha_referencia). Nunca CURRENT_TIMESTAMP
-- (idempotencia, ADR-006).
{% set run_ts = var('run_ts', none) %}
{% if run_ts %}
    {% set ts_cuarentena_sql = "timestamp('" ~ run_ts ~ "')" %}
{% else %}
    {% set ts_cuarentena_sql = "timestamp(date('" ~ var('fecha_referencia') ~ "'))" %}
{% endif %}
with rechazados as (
    select
        fuente, archivo, objeto_gcs, linea_num, kafka_offset, raw as registro_original,
        regla_id, motivo, tarjeta as llave_usuario, ingest_date
    from {{ ref('val_transmetro_validaciones') }}
    where regla_id is not null
    union all
    select
        fuente, archivo, objeto_gcs, cast(null as int64), cast(null as int64), raw,
        regla_id, motivo, num_tarjeta, ingest_date
    from {{ ref('val_transurbano_transacciones') }}
    where regla_id is not null
    union all
    select
        fuente, archivo, objeto_gcs, cast(null as int64), cast(null as int64), raw,
        regla_id, motivo, card, ingest_date
    from {{ ref('val_metroriel_viajes') }}
    where regla_id is not null
    union all
    select
        fuente, archivo, objeto_gcs, linea_num, kafka_offset, raw,
        regla_id, motivo, user_hash, ingest_date
    from {{ ref('val_aerometro_boardings') }}
    where regla_id is not null
    union all
    select
        fuente, archivo, objeto_gcs, cast(null as int64), cast(null as int64), raw,
        regla_id, motivo, tarjeta, ingest_date
    from {{ ref('val_cdc_padron_usuarios') }}
    where regla_id is not null
    union all
    select
        fuente, archivo, objeto_gcs, cast(null as int64), cast(null as int64), raw,
        regla_id, motivo, cast(null as string), ingest_date
    from {{ ref('val_estaciones') }}
    where regla_id is not null
)
select
    fuente,
    archivo,
    objeto_gcs,
    linea_num,
    kafka_offset,
    registro_original,
    regla_id,
    motivo,
    llave_usuario,
    ingest_date,
    '{{ var("run_id") }}' as run_id,
    {{ ts_cuarentena_sql }} as ts_cuarentena
from rechazados
