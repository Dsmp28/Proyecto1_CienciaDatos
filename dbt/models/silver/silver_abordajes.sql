-- Silver · tabla atómica unificada al grano "un abordaje" (ADR-004, matriz del bus): UNION de
-- Transmetro (todas las válidas), Transurbano (solo es_cobro_exitoso: 7 y 9 no cuentan como viaje),
-- MetroRiel (la ENTRADA de cada viaje cerrado válido) y Aerómetro (todas las válidas).
-- abordaje_id = modo|id nativo (TU sin id: modo|registro_hash|n_repeticion). usuario_base_id viene de silver_usuarios
-- (mismo criterio de vínculo que dim_usuario). NO seudonimiza: Silver conserva la llave nativa; Gold usa usuario_sk.
with union_modos as (
    select
        concat('TM|', cast(validacion_id as string)) as abordaje_id,
        modo_id, llave_nativa, estacion_sk, codigo_estacion_nativo, zona_id,
        fecha_hora_local, fecha, hora, monto_q,
        tipo as tipo_validacion,
        es_transbordo_interno,
        fuente, archivo, objeto_gcs, ingest_date, linea_num, kafka_offset, registro_hash
    from {{ ref('silver_transmetro_validaciones') }}
    union all
    select
        concat('TU|', transaccion_id),
        modo_id, llave_nativa, estacion_sk, codigo_estacion_nativo, zona_id,
        fecha_hora_local, fecha, hora, monto_q,
        estado_desc,
        false,
        fuente, archivo, objeto_gcs, ingest_date, cast(null as int64), cast(null as int64), registro_hash
    from {{ ref('silver_transurbano_transacciones') }}
    where es_cobro_exitoso
    union all
    select
        concat('MR|', cast(trip_id as string)),
        modo_id, llave_nativa, estacion_sk_origen, codigo_estacion_nativo, zona_id_origen,
        fecha_hora_local, fecha, hora, monto_q,
        'ENTRADA',
        false,
        fuente, archivo, objeto_gcs, ingest_date, cast(null as int64), cast(null as int64), registro_hash
    from {{ ref('silver_metroriel_viajes') }}
    union all
    select
        concat('AM|', cast(boarding_id as string)),
        modo_id, llave_nativa, estacion_sk, codigo_estacion_nativo, zona_id,
        fecha_hora_local, fecha, hora, monto_q,
        'BOARDING',
        false,
        fuente, archivo, objeto_gcs, ingest_date, linea_num, kafka_offset, registro_hash
    from {{ ref('silver_aerometro_boardings') }}
),
usuarios as (
    select modo_id, llave_nativa, usuario_base_id from {{ ref('silver_usuarios') }}
)
select
    a.abordaje_id,
    a.modo_id,
    a.llave_nativa,
    u.usuario_base_id,
    a.estacion_sk,
    a.codigo_estacion_nativo,
    a.zona_id,
    a.fecha_hora_local,
    a.fecha,
    a.hora,
    a.monto_q,
    a.tipo_validacion,
    a.es_transbordo_interno,
    -- linaje
    a.fuente,
    a.archivo,
    a.objeto_gcs,
    a.ingest_date,
    a.linea_num,
    a.kafka_offset,
    a.registro_hash
from union_modos as a
left join usuarios as u on u.modo_id = a.modo_id and u.llave_nativa = a.llave_nativa
