-- Recalcula la población de churn desde silver_abordajes y silver_padron_scd2 (sin pasar por churn_eventos ni
-- churn_poblacion) y compara con churn_poblacion.en_poblacion: >= 2 abordajes válidos en [t-28, t) y ningún DELETE con
-- vigente_desde < datetime(t) en ninguna tarjeta de la persona. Diferencias en ambos sentidos; si hay filas, falla.
with cortes as (
    {{ cortes_cte() }}
),
usuarios as (
    select modo_id, llave_nativa, usuario_unificado_sk as unidad_id
    from {{ ref('silver_usuarios') }}
    where usuario_unificado_sk is not null
),
ab as (
    select c.corte, u.unidad_id, count(*) as n
    from {{ ref('silver_abordajes') }} as a
    inner join usuarios as u on u.modo_id = a.modo_id and u.llave_nativa = a.llave_nativa
    inner join cortes as c
        on a.fecha_hora_local >= datetime(date_sub(c.fecha_corte, interval {{ var('ventana_max_dias') }} day))
       and a.fecha_hora_local < datetime(c.fecha_corte)
    group by c.corte, u.unidad_id
),
bajas as (
    select distinct c.corte, u.unidad_id
    from {{ ref('silver_padron_scd2') }} as p
    inner join usuarios as u on u.modo_id = p.modo_id and u.llave_nativa = p.tarjeta
    inner join cortes as c on p.vigente_desde < datetime(c.fecha_corte)
    where p.op = 'DELETE'
),
esperado as (
    select ab.corte, ab.unidad_id, ab.n, (ab.n >= 2 and bajas.unidad_id is null) as en_poblacion
    from ab
    left join bajas on bajas.corte = ab.corte and bajas.unidad_id = ab.unidad_id
),
observado as (
    select corte, unidad_id, n_abordajes_28d, en_poblacion from {{ ref('churn_poblacion') }}
)
select coalesce(e.corte, r.corte) as corte, coalesce(e.unidad_id, r.unidad_id) as unidad_id,
       e.n as n_esperado, r.n_abordajes_28d as n_real, e.en_poblacion as esperado, r.en_poblacion as observado
from esperado as e
full outer join observado as r on r.corte = e.corte and r.unidad_id = e.unidad_id
where e.unidad_id is null or r.unidad_id is null
   or e.n != r.n_abordajes_28d or e.en_poblacion != r.en_poblacion
