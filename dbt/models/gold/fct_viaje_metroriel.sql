{{ config(
    partition_by={'field': 'fecha_entrada', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['zona_id_origen', 'zona_id_destino']
) }}
-- Gold · fct_viaje_metroriel. Grano: un viaje cerrado de MetroRiel (entrada y salida), desde silver_metroriel_viajes.
-- Es el único modo que entrega origen–destino real, por eso conserva su hecho propio (ADR-004) además de aportar su
-- entrada a fct_abordaje (abordaje_sk = 'MR|trip_id' permite cruzar ambos). Dimensiones role-playing: tiempo y
-- estación/zona de entrada y de salida. Llave de usuario seudonimizada desde silver_usuarios.
with viajes as (
    select
        v.*,
        date(v.fecha_hora_salida_local) as fecha_salida,
        cast(format_date('%Y%m%d', v.fecha) as int64) * 100 + v.hora as tiempo_sk_entrada,
        cast(format_date('%Y%m%d', date(v.fecha_hora_salida_local)) as int64) * 100
            + extract(hour from v.fecha_hora_salida_local) as tiempo_sk_salida
    from {{ ref('silver_metroriel_viajes') }} as v
),
usuarios as (
    select llave_nativa, usuario_sk, usuario_unificado_sk
    from {{ ref('silver_usuarios') }}
    where modo_id = 'MR'
),
tiempo as (
    select tiempo_sk, franja, es_hora_pico, es_dia_habil
    from {{ ref('dim_tiempo') }}
)
select
    v.trip_id,
    concat('MR|', cast(v.trip_id as string)) as abordaje_sk,
    v.modo_id,
    v.tiempo_sk_entrada,
    v.tiempo_sk_salida,
    v.fecha as fecha_entrada,
    v.fecha_salida,
    v.hora as hora_entrada,
    v.estacion_sk_origen,
    v.estacion_sk_destino,
    v.zona_id_origen,
    v.zona_id_destino,
    v.zona_id_origen != v.zona_id_destino as cambia_de_zona,
    u.usuario_sk,
    u.usuario_unificado_sk,
    to_hex(sha256(concat(v.fuente, '|', v.archivo, '|', coalesce(v.objeto_gcs, ''), '|', cast(v.ingest_date as string)))) as fuente_sk,
    v.fecha_hora_local as fecha_hora_entrada,
    v.fecha_hora_salida_local as fecha_hora_salida,
    v.monto_q,
    v.duracion_s,
    round(v.duracion_s / 60, 2) as duracion_min,
    1 as viajes,
    t.franja,
    t.es_hora_pico,
    t.es_dia_habil,
    -- linaje
    v.fuente,
    v.archivo,
    v.objeto_gcs,
    v.ingest_date
from viajes as v
left join usuarios as u on u.llave_nativa = v.llave_nativa
left join tiempo as t on t.tiempo_sk = v.tiempo_sk_entrada
