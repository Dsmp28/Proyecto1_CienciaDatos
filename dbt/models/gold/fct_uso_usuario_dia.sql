{{ config(
    partition_by={'field': 'fecha', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['modo_id', 'usuario_unificado_sk']
) }}
-- Gold · fct_uso_usuario_dia. Snapshot periódico: una fila por tarjeta seudonimizada (usuario_sk) × fecha × modo.
-- Se construye directamente desde silver_abordajes + silver_usuarios + dim_tiempo (no desde fct_abordaje) para que
-- la "prueba de fuego" de gobernanza (viajes del mes por dos caminos, assert_viajes_del_mes_dos_caminos) compare dos
-- derivaciones independientes de Silver. Base de la pregunta de transbordo (agg_transbordo: usuarios con más de un modo).
-- zona_id_mas_frecuente: la zona con más abordajes de la tarjeta ese día (empate → menor zona_id, determinista).
with abordajes as (
    select
        u.usuario_sk,
        u.usuario_unificado_sk,
        a.fecha,
        a.modo_id,
        a.hora,
        a.zona_id,
        a.estacion_sk,
        a.monto_q,
        t.es_hora_pico,
        t.es_dia_habil
    from {{ ref('silver_abordajes') }} as a
    join {{ ref('silver_usuarios') }} as u
        on u.modo_id = a.modo_id and u.llave_nativa = a.llave_nativa
    left join {{ ref('dim_tiempo') }} as t
        on t.tiempo_sk = cast(format_date('%Y%m%d', a.fecha) as int64) * 100 + a.hora
),
zona_frecuente as (
    select usuario_sk, fecha, modo_id, zona_id as zona_id_mas_frecuente
    from (
        select usuario_sk, fecha, modo_id, zona_id, count(*) as n
        from abordajes
        group by usuario_sk, fecha, modo_id, zona_id
    )
    qualify row_number() over (partition by usuario_sk, fecha, modo_id order by n desc, zona_id) = 1
)
select
    a.usuario_sk,
    a.usuario_unificado_sk,
    a.fecha,
    cast(format_date('%Y%m%d', a.fecha) as int64) * 100 as tiempo_sk_dia,
    a.modo_id,
    count(*) as abordajes,
    sum(a.monto_q) as monto_q,
    countif(a.es_hora_pico) as abordajes_hora_pico,
    count(distinct a.estacion_sk) as estaciones_distintas,
    z.zona_id_mas_frecuente,
    min(a.hora) as primera_hora,
    max(a.hora) as ultima_hora,
    any_value(a.es_dia_habil) as es_dia_habil
from abordajes as a
join zona_frecuente as z
    on z.usuario_sk = a.usuario_sk and z.fecha = a.fecha and z.modo_id = a.modo_id
group by a.usuario_sk, a.usuario_unificado_sk, a.fecha, a.modo_id, z.zona_id_mas_frecuente
