-- Features · tabla lista para entrenar (entregable 2.3). Entidad: UNA PERSONA (usuario_unificado_sk, ADR-008),
-- una fila por persona con columnas derivadas de su historial de abordajes en los cuatro modos.
-- Restricción dura 5: solo lee Silver y seeds (nunca Gold; prueba tests/test_gold_lineage.py).
-- Fecha de corte declarada: var('fecha_corte') (por defecto var('fecha_referencia') = 2026-07-16). Toda fuente se
-- filtra con fecha < fecha_corte (exclusivo), por lo que ninguna feature usa datos del día de corte ni posteriores
-- (prueba singular assert_features_sin_fuga). Nunca CURRENT_DATE: dos corridas producen la misma tabla.
-- Ventanas: 7d = [corte-7, corte), 30d = [corte-30, corte), 90d = [corte-90, corte). Los datos observados cubren
-- 45 días (2026-06-01 a 2026-07-15), así que la ventana de 90 días queda truncada y coincide con viajes_total.
-- Sin columna objetivo: la etiqueta (p. ej. abandono = 0 viajes en los 30 días posteriores al corte) se construiría
-- con datos posteriores a fecha_corte, que este lote no contiene (ver docs/features/README.md).
{{ config(materialized='table', cluster_by=['modo_mas_usado']) }}

{% set fecha_corte = var('fecha_corte', var('fecha_referencia')) %}

with params as (
    select date('{{ fecha_corte }}') as fecha_corte
),
-- Identidad unificada: usuario_unificado_sk es el mismo para todas las tarjetas de una persona (HMAC de 'BASE|i').
identidad as (
    select usuario_base_id, any_value(usuario_unificado_sk) as usuario_unificado_sk
    from {{ ref('silver_usuarios') }}
    where usuario_base_id is not null and usuario_unificado_sk is not null
    group by usuario_base_id
),
franjas as (
    select hora, franja, es_hora_pico from {{ ref('franjas_horarias') }}
),
feriados as (
    select fecha from {{ ref('feriados_gt') }}
),
-- Historial observable: abordajes estrictamente anteriores a la fecha de corte.
abordajes as (
    select
        a.usuario_base_id,
        a.modo_id,
        a.fecha,
        a.hora,
        a.monto_q,
        a.zona_id,
        a.estacion_sk,
        a.es_transbordo_interno,
        coalesce(f.es_hora_pico, false) as es_hora_pico,
        f.franja,
        (extract(dayofweek from a.fecha) between 2 and 6 and fe.fecha is null) as es_dia_habil,
        p.fecha_corte
    from {{ ref('silver_abordajes') }} as a
    cross join params as p
    left join franjas as f on f.hora = a.hora
    left join feriados as fe on fe.fecha = a.fecha
    where a.fecha < p.fecha_corte
      and a.usuario_base_id is not null
),
agregados as (
    select
        usuario_base_id,
        any_value(fecha_corte) as fecha_corte,
        count(*) as viajes_total,
        countif(fecha >= date_sub(fecha_corte, interval 7 day)) as viajes_7d,
        countif(fecha >= date_sub(fecha_corte, interval 30 day)) as viajes_30d,
        countif(fecha >= date_sub(fecha_corte, interval 90 day)) as viajes_90d,
        countif(fecha >= date_sub(fecha_corte, interval 60 day)
            and fecha < date_sub(fecha_corte, interval 30 day)) as viajes_30d_previos,
        date_diff(any_value(fecha_corte), max(fecha), day) as dias_desde_ultimo_viaje,
        date_diff(any_value(fecha_corte), min(fecha), day) as dias_desde_primer_viaje,
        count(distinct fecha) as dias_activos,
        count(distinct modo_id) as n_modos_distintos,
        countif(modo_id = 'TM') as viajes_por_modo_tm,
        countif(modo_id = 'TU') as viajes_por_modo_tu,
        countif(modo_id = 'MR') as viajes_por_modo_mr,
        countif(modo_id = 'AM') as viajes_por_modo_am,
        safe_divide(countif(es_hora_pico), count(*)) as prop_hora_pico,
        safe_divide(countif(es_dia_habil), count(*)) as prop_dia_habil,
        safe_divide(countif(es_transbordo_interno), count(*)) as prop_transbordo_interno,
        avg(hora) as hora_promedio,
        count(distinct zona_id) as n_zonas_distintas,
        count(distinct estacion_sk) as n_estaciones_distintas,
        sum(monto_q) as gasto_acumulado_q,
        avg(monto_q) as gasto_promedio_viaje_q
    from abordajes
    group by usuario_base_id
),
-- Modas: más abordajes; desempate determinista por orden alfabético del valor.
modo_top as (
    select usuario_base_id, modo_id as modo_mas_usado
    from (select usuario_base_id, modo_id, count(*) as n from abordajes group by 1, 2)
    qualify row_number() over (partition by usuario_base_id order by n desc, modo_id) = 1
),
zona_top as (
    select usuario_base_id, zona_id as zona_origen_mas_frecuente
    from (select usuario_base_id, zona_id, count(*) as n from abordajes group by 1, 2)
    qualify row_number() over (partition by usuario_base_id order by n desc, zona_id) = 1
),
franja_top as (
    select usuario_base_id, franja as franja_mas_frecuente
    from (select usuario_base_id, franja, count(*) as n from abordajes where franja is not null group by 1, 2)
    qualify row_number() over (partition by usuario_base_id order by n desc, franja) = 1
),
-- MetroRiel: viajes cerrados cuya entrada Y salida ocurren antes del corte (la duración se conoce completa).
usuarios_mr as (
    select llave_nativa, usuario_base_id
    from {{ ref('silver_usuarios') }}
    where modo_id = 'MR' and usuario_base_id is not null
),
metroriel as (
    select
        u.usuario_base_id,
        count(*) as viajes_metroriel_completos,
        avg(v.duracion_s) / 60.0 as duracion_promedio_metroriel_min
    from {{ ref('silver_metroriel_viajes') }} as v
    cross join params as p
    join usuarios_mr as u on u.llave_nativa = v.llave_nativa
    where v.fecha < p.fecha_corte
      and date(v.fecha_hora_salida_local) < p.fecha_corte
    group by u.usuario_base_id
),
-- Padrón "as of" la fecha de corte: última versión por persona (orden de seq, la verdad del log; ADR-009) entre las
-- operaciones confirmadas antes del corte. Se ordena por seq y no por vigente_hasta porque commit_ts_fuera_de_orden
-- marca 103 operaciones cuya hora está invertida dentro del mismo día.
padron_asof as (
    select usuario_base_id, perfil, zona_residencia_id, estado
    from {{ ref('silver_padron_scd2') }} as s
    cross join params as p
    where s.vigente_desde < datetime(p.fecha_corte)
    qualify row_number() over (partition by s.usuario_base_id order by s.seq desc, s.tarjeta) = 1
)
select
    i.usuario_unificado_sk,
    g.fecha_corte,
    -- actividad
    g.viajes_7d,
    g.viajes_30d,
    g.viajes_90d,
    g.viajes_total,
    g.viajes_30d_previos,
    g.viajes_30d - g.viajes_30d_previos as tendencia_30_vs_anterior,
    g.dias_desde_ultimo_viaje,
    g.dias_desde_primer_viaje,
    g.dias_activos,
    -- modos
    m.modo_mas_usado,
    g.n_modos_distintos,
    g.n_modos_distintos > 1 as es_multimodal,
    g.viajes_por_modo_tm,
    g.viajes_por_modo_tu,
    g.viajes_por_modo_mr,
    g.viajes_por_modo_am,
    -- hábitos horarios
    g.prop_hora_pico,
    g.prop_dia_habil,
    g.prop_transbordo_interno,
    g.hora_promedio,
    fr.franja_mas_frecuente,
    -- geografía
    z.zona_origen_mas_frecuente,
    g.n_zonas_distintas,
    g.n_estaciones_distintas,
    -- gasto
    g.gasto_acumulado_q,
    g.gasto_promedio_viaje_q,
    -- MetroRiel
    coalesce(mr.viajes_metroriel_completos, 0) as viajes_metroriel_completos,
    mr.duracion_promedio_metroriel_min,
    -- padrón vigente a la fecha de corte
    pa.perfil as perfil_padron,
    pa.zona_residencia_id,
    coalesce(pa.estado, 'SIN_PADRON') as estado_padron,
    -- definición oficial 2: >= 1 viaje en los 30 días anteriores a la fecha de referencia y no dado de baja en el padrón
    g.viajes_30d >= 1 and coalesce(pa.estado, 'SIN_PADRON') != 'INACTIVA' as es_usuario_activo_30d
from agregados as g
join identidad as i on i.usuario_base_id = g.usuario_base_id
left join modo_top as m on m.usuario_base_id = g.usuario_base_id
left join zona_top as z on z.usuario_base_id = g.usuario_base_id
left join franja_top as fr on fr.usuario_base_id = g.usuario_base_id
left join metroriel as mr on mr.usuario_base_id = g.usuario_base_id
left join padron_asof as pa on pa.usuario_base_id = g.usuario_base_id
