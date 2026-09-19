-- Anti-fuga (entregable 2.3): ninguna feature usa datos con fecha >= fecha_corte y la tabla cubre exactamente a
-- las personas con historial anterior al corte. Devuelve una fila por chequeo incumplido: si devuelve filas, falla.
{% set fecha_corte = var('fecha_corte', var('fecha_referencia')) %}

with corte as (
    select date('{{ fecha_corte }}') as fecha_corte
),
-- 1) recencia: si alguna persona tuviera un viaje el día de corte o después, dias_desde_ultimo_viaje sería <= 0
recencia as (
    select 'dias_desde_ultimo_viaje < 1' as chequeo, cast(count(*) as string) as detalle
    from {{ ref('usuario_features') }}
    where dias_desde_ultimo_viaje < 1
    having count(*) > 0
),
-- 2) la fecha_corte grabada en la tabla es la declarada en la corrida
fecha_declarada as (
    select 'fecha_corte distinta a la declarada' as chequeo, cast(count(*) as string) as detalle
    from {{ ref('usuario_features') }}, corte
    where usuario_features.fecha_corte != corte.fecha_corte or usuario_features.fecha_corte is null
    having count(*) > 0
),
-- 3) el primer viaje observado también es anterior al corte (ninguna fila construida solo con datos posteriores)
antiguedad as (
    select 'dias_desde_primer_viaje < dias_desde_ultimo_viaje' as chequeo, cast(count(*) as string) as detalle
    from {{ ref('usuario_features') }}
    where dias_desde_primer_viaje < dias_desde_ultimo_viaje
    having count(*) > 0
),
-- 4) cobertura: una fila por persona con abordajes anteriores al corte, ni más ni menos
esperado as (
    select count(distinct a.usuario_base_id) as n
    from {{ ref('silver_abordajes') }} as a, corte
    where a.fecha < corte.fecha_corte and a.usuario_base_id is not null
),
observado as (
    select count(*) as n from {{ ref('usuario_features') }}
),
cobertura as (
    select
        'COUNT(*) de usuario_features != personas con abordajes antes del corte' as chequeo,
        concat('features=', cast(o.n as string), ' esperado=', cast(e.n as string)) as detalle
    from observado as o, esperado as e
    where o.n != e.n
),
-- 5) suma de viajes_total = abordajes anteriores al corte (nada se cuenta dos veces ni se pierde)
volumen as (
    select
        'SUM(viajes_total) != abordajes antes del corte' as chequeo,
        concat('features=', cast(f.n as string), ' esperado=', cast(e.n as string)) as detalle
    from (select sum(viajes_total) as n from {{ ref('usuario_features') }}) as f,
         (select count(*) as n from {{ ref('silver_abordajes') }}, corte
          where fecha < corte.fecha_corte and usuario_base_id is not null) as e
    where f.n != e.n
)
select * from recencia
union all select * from fecha_declarada
union all select * from antiguedad
union all select * from cobertura
union all select * from volumen
