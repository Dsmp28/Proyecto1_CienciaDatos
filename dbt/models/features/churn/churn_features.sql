-- Features · Proyecto 2 (ADR-015). Features de churn por (unidad_id, corte) para la población en_poblacion. Solo usa el
-- tramo 'ventana' de churn_eventos: abordajes con fecha en [t-28, t) (fecha < t, dias_antes_corte 1..28). TODAS las
-- ventanas son <= 28 días (prueba tests/test_ventanas_churn.py y assert_churn_ventana_max_28). Padrón: solo eventos con
-- vigente_desde < t; no usa vigente_hasta/es_vigente ni columnas de estado FINAL de silver_usuarios. MetroRiel: duración
-- solo de viajes con fecha_hora_salida_local < t. Semanas: semana_idx = DIV(dias_antes_corte - 1, 7) (0 = la más reciente).
-- Desviaciones estándar poblacionales (STDDEV_POP). FLOAT redondeados a 6 decimales. Sin llaves nativas en la salida.
{{ config(materialized='table', cluster_by=['corte']) }}

with cortes as (
    {{ cortes_cte() }}
),
poblacion as (
    select corte, fecha_corte, unidad_id
    from {{ ref('churn_poblacion') }}
    where en_poblacion
),
franjas as (
    select hora, es_hora_pico from {{ ref('franjas_horarias') }}
),
feriados as (
    select fecha from {{ ref('feriados_gt') }}
),
ev as (
    select
        e.corte, e.fecha_corte, e.unidad_id, e.modo_id, e.tarjeta_sk, e.fecha, e.hora, e.monto_q, e.zona_id,
        e.estacion_sk, e.es_transbordo_interno, e.dias_antes_corte,
        div(e.dias_antes_corte - 1, 7) as semana_idx,
        coalesce(f.es_hora_pico, false) as es_hora_pico,
        extract(dayofweek from e.fecha) in (1, 7) as es_fin_semana,
        fe.fecha is not null as es_feriado
    from {{ ref('churn_eventos') }} as e
    inner join poblacion as p on p.corte = e.corte and p.unidad_id = e.unidad_id
    left join franjas as f on f.hora = e.hora
    left join feriados as fe on fe.fecha = e.fecha
    where e.tramo = 'ventana'
      and e.dias_antes_corte between 1 and {{ var('ventana_max_dias') }}
),
agregados as (
    select
        corte, fecha_corte, unidad_id,
        count(*) as n_abordajes_28d,
        countif(dias_antes_corte <= 14) as n_abordajes_14d,
        countif(dias_antes_corte <= 7) as n_abordajes_7d,
        count(distinct fecha) as dias_activos_28d,
        count(distinct if(dias_antes_corte <= 7, fecha, null)) as dias_activos_7d,
        min(dias_antes_corte) as dias_desde_ultimo,
        max(dias_antes_corte) as dias_desde_primero_28d,
        count(distinct semana_idx) as semanas_activas_4,
        safe_divide(countif(dias_antes_corte <= 14), countif(dias_antes_corte > 14)) as ratio_ult14_prev14,
        countif(semana_idx = 0) as n_sem0,
        countif(semana_idx = 1) as n_sem1,
        countif(semana_idx = 2) as n_sem2,
        countif(semana_idx = 3) as n_sem3,
        count(distinct modo_id) as n_modos_28d,
        safe_divide(countif(modo_id = 'TM'), count(*)) as share_tm,
        safe_divide(countif(modo_id = 'TU'), count(*)) as share_tu,
        safe_divide(countif(modo_id = 'MR'), count(*)) as share_mr,
        safe_divide(countif(modo_id = 'AM'), count(*)) as share_am,
        safe_divide(countif(es_hora_pico), count(*)) as pct_hora_pico,
        safe_divide(countif(es_fin_semana), count(*)) as pct_fin_semana,
        safe_divide(countif(es_feriado), count(*)) as pct_feriado,
        cast(coalesce(sum(monto_q), 0) as float64) as gasto_q_28d,
        cast(avg(monto_q) as float64) as gasto_medio_q,
        count(distinct estacion_sk) as n_estaciones_28d,
        count(distinct zona_id) as n_zonas_28d,
        safe_divide(countif(es_transbordo_interno), count(*)) as pct_transbordo_interno,
        count(distinct tarjeta_sk) as n_tarjetas_activas_28d,
        -- medias y desviaciones con sumas enteras exactas: AVG/STDDEV en float dependen del orden de suma y cambian
        -- el 6.º decimal entre corridas (lo detectó la prueba de recorte)
        safe_divide(sum(hora), count(hora)) as hora_media,
        sqrt(greatest(safe_divide(sum(hora * hora), count(hora)) - pow(safe_divide(sum(hora), count(hora)), 2), 0)) as hora_sd
    from ev
    group by corte, fecha_corte, unidad_id
),
modo_moda as (
    select corte, unidad_id, modo_id as modo_principal
    from (select corte, unidad_id, modo_id, count(*) as n from ev group by corte, unidad_id, modo_id)
    qualify row_number() over (partition by corte, unidad_id order by n desc, modo_id) = 1
),
zona_moda as (
    select corte, unidad_id, zona_id as zona_principal
    from (select corte, unidad_id, zona_id, count(*) as n from ev where zona_id is not null group by corte, unidad_id, zona_id)
    qualify row_number() over (partition by corte, unidad_id order by n desc, zona_id) = 1
),
usuarios as (
    select modo_id, llave_nativa, usuario_unificado_sk as unidad_id
    from {{ ref('silver_usuarios') }}
    where usuario_unificado_sk is not null
),
-- MetroRiel: viajes completos al corte (entrada en [t-28, t) y salida < t). Una salida posterior a t no se conoce en t.
mr as (
    select
        c.corte, u.unidad_id,
        count(*) as viajes_mr_completos_28d,
        -- suma entera exacta / (n*60): evita que el orden de suma de AVG en float cambie el 6.º decimal entre corridas
        safe_divide(sum(v.duracion_s), count(v.duracion_s) * 60) as duracion_media_mr_min
    from {{ ref('silver_metroriel_viajes') }} as v
    inner join usuarios as u on u.modo_id = v.modo_id and u.llave_nativa = v.llave_nativa
    inner join cortes as c
        on v.fecha >= date_sub(c.fecha_corte, interval {{ var('ventana_max_dias') }} day)
       and v.fecha < c.fecha_corte
       and v.fecha_hora_salida_local < datetime(c.fecha_corte)
    inner join poblacion as p on p.corte = c.corte and p.unidad_id = u.unidad_id
    group by c.corte, u.unidad_id
),
-- Padrón a t: eventos con vigente_desde < t (log CDC), persona por (modo_id, tarjeta) contra silver_usuarios.
padron as (
    select
        c.corte, u.unidad_id,
        count(*) as n_eventos_padron_previos,
        countif(p.vigente_desde >= datetime(date_sub(c.fecha_corte, interval {{ var('ventana_max_dias') }} day))) as n_eventos_padron_28d,
        array_agg(p.perfil order by p.seq desc, p.tarjeta limit 1)[offset(0)] as perfil_padron_a_t
    from {{ ref('silver_padron_scd2') }} as p
    inner join usuarios as u on u.modo_id = p.modo_id and u.llave_nativa = p.tarjeta
    inner join cortes as c on p.vigente_desde < datetime(c.fecha_corte)
    inner join poblacion as po on po.corte = c.corte and po.unidad_id = u.unidad_id
    group by c.corte, u.unidad_id
)
select
    a.unidad_id,
    a.fecha_corte,
    a.corte,
    a.n_abordajes_28d,
    a.n_abordajes_14d,
    a.n_abordajes_7d,
    a.dias_activos_28d,
    a.dias_activos_7d,
    a.dias_desde_ultimo,
    a.dias_desde_primero_28d,
    a.semanas_activas_4,
    round(a.ratio_ult14_prev14, 6) as ratio_ult14_prev14,
    round(safe_divide(
        (select stddev_pop(x) from unnest([a.n_sem0, a.n_sem1, a.n_sem2, a.n_sem3]) as x),
        (a.n_sem0 + a.n_sem1 + a.n_sem2 + a.n_sem3) / 4
    ), 6) as cv_semanal,
    a.n_modos_28d,
    round(a.share_tm, 6) as share_tm,
    round(a.share_tu, 6) as share_tu,
    round(a.share_mr, 6) as share_mr,
    round(a.share_am, 6) as share_am,
    round(a.pct_hora_pico, 6) as pct_hora_pico,
    round(a.pct_fin_semana, 6) as pct_fin_semana,
    round(a.pct_feriado, 6) as pct_feriado,
    round(a.gasto_q_28d, 6) as gasto_q_28d,
    round(a.gasto_medio_q, 6) as gasto_medio_q,
    a.n_estaciones_28d,
    a.n_zonas_28d,
    round(a.pct_transbordo_interno, 6) as pct_transbordo_interno,
    a.n_tarjetas_activas_28d,
    round(a.hora_media, 6) as hora_media,
    round(a.hora_sd, 6) as hora_sd,
    mm.modo_principal,
    zm.zona_principal,
    coalesce(mr.viajes_mr_completos_28d, 0) as viajes_mr_completos_28d,
    round(mr.duracion_media_mr_min, 6) as duracion_media_mr_min,
    pd.perfil_padron_a_t,
    coalesce(pd.n_eventos_padron_previos, 0) > 0 as tiene_padron_a_t,
    coalesce(pd.n_eventos_padron_28d, 0) as n_eventos_padron_28d
from agregados as a
left join modo_moda as mm on mm.corte = a.corte and mm.unidad_id = a.unidad_id
left join zona_moda as zm on zm.corte = a.corte and zm.unidad_id = a.unidad_id
left join mr on mr.corte = a.corte and mr.unidad_id = a.unidad_id
left join padron as pd on pd.corte = a.corte and pd.unidad_id = a.unidad_id
