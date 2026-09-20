{{ config(
    partition_by={'field': 'fecha', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['modo_id', 'zona_id']
) }}
-- Gold · fct_abordaje. Grano (ADR-004): una validación de una tarjeta de un usuario en un modo, en una estación o
-- parada, en un instante. Una fila por fila de silver_abordajes (prueba assert_abordajes_gold_igual_silver), con la
-- llave nativa sustituida por usuario_sk / usuario_unificado_sk de silver_usuarios (HMAC-SHA256, ADR-007/008).
-- es_hora_pico, es_dia_habil y franja se desnormalizan desde dim_tiempo para Tableau. Linaje: fuente_sk (dim_fuente)
-- más archivo, objeto_gcs, ingest_date, linea_num y kafka_offset copiados de Silver (restricción dura 4).
-- Particionada por fecha y agrupada por modo_id, zona_id (patrón de consulta del tablero: demanda por modo/zona/hora).
with abordajes as (
    select
        a.*,
        cast(format_date('%Y%m%d', a.fecha) as int64) * 100 + a.hora as tiempo_sk
    from {{ ref('silver_abordajes') }} as a
),
usuarios as (
    select modo_id, llave_nativa, usuario_sk, usuario_unificado_sk
    from {{ ref('silver_usuarios') }}
),
tiempo as (
    select tiempo_sk, franja, es_hora_pico, es_dia_habil
    from {{ ref('dim_tiempo') }}
)
select
    a.abordaje_id as abordaje_sk,
    a.tiempo_sk,
    a.fecha,
    a.hora,
    a.modo_id,
    a.estacion_sk,
    a.zona_id,
    u.usuario_sk,
    u.usuario_unificado_sk,
    to_hex(sha256(concat(a.fuente, '|', a.archivo, '|', coalesce(a.objeto_gcs, ''), '|', cast(a.ingest_date as string)))) as fuente_sk,
    a.fecha_hora_local as fecha_hora,
    a.monto_q,
    1 as abordajes,
    a.tipo_validacion,
    a.es_transbordo_interno,
    t.franja,
    t.es_hora_pico,
    t.es_dia_habil,
    -- linaje hasta el archivo crudo
    a.fuente,
    a.archivo,
    a.objeto_gcs,
    a.ingest_date,
    a.linea_num,
    a.kafka_offset
from abordajes as a
left join usuarios as u on u.modo_id = a.modo_id and u.llave_nativa = a.llave_nativa
left join tiempo as t on t.tiempo_sk = a.tiempo_sk
