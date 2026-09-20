{{ config(
    partition_by={'field': 'fecha', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['modo_id', 'zona_id']
) }}
-- Gold · agg_demanda_modo_zona_hora. Agregado para Tableau (pregunta 1: demanda por modo, zona y hora) sobre
-- fct_abordaje × dim_tiempo. Grano: fecha × hora × modo × zona. abordajes y monto_q son aditivas; usuarios_distintos es
-- NO aditiva (COUNT DISTINCT de usuario_sk dentro de la celda: no se suma entre horas, zonas ni modos; para otro nivel
-- se recalcula desde fct_abordaje).
select
    a.tiempo_sk,
    a.fecha,
    a.hora,
    t.franja,
    t.es_hora_pico,
    t.es_dia_habil,
    t.dia_semana,
    t.dia_semana_nombre,
    a.modo_id,
    a.zona_id,
    sum(a.abordajes) as abordajes,
    sum(a.monto_q) as monto_q,
    count(distinct a.usuario_sk) as usuarios_distintos,
    count(distinct a.estacion_sk) as estaciones_con_demanda
from {{ ref('fct_abordaje') }} as a
join {{ ref('dim_tiempo') }} as t on t.tiempo_sk = a.tiempo_sk
group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
