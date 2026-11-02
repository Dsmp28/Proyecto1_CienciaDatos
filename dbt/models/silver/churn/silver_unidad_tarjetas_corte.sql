-- Silver · Proyecto 2 (ADR-015). Tarjetas de cada persona (unidad_id = usuario_unificado_sk) conocidas en cada corte t.
-- Grano: una fila por (unidad_id, fecha_corte). Una tarjeta cuenta para el corte solo si fue OBSERVADA antes de t:
-- tuvo un abordaje válido con fecha_hora_local < t, o un evento de padrón con vigente_desde < t. Así la lista de
-- tarjetas no mira el futuro. Padrón -> persona: (modo_id = formato_tarjeta, llave_nativa = tarjeta) contra silver_usuarios.
-- `tarjetas` = STRING_AGG(llave_nativa, ';' ORDER BY modo_id, llave_nativa). Conserva llaves nativas (Silver las conserva;
-- ninguna tabla de churn_* las expone). Cortes desde var('fechas_corte'); nunca CURRENT_DATE.
with cortes as (
    {{ cortes_cte() }}
),
usuarios as (
    select modo_id, llave_nativa, usuario_unificado_sk as unidad_id
    from {{ ref('silver_usuarios') }}
    where usuario_unificado_sk is not null
),
observaciones as (
    select u.unidad_id, a.modo_id, a.llave_nativa, a.fecha_hora_local as momento
    from {{ ref('silver_abordajes') }} as a
    inner join usuarios as u on u.modo_id = a.modo_id and u.llave_nativa = a.llave_nativa
    union all
    select u.unidad_id, p.modo_id, p.tarjeta, p.vigente_desde
    from {{ ref('silver_padron_scd2') }} as p
    inner join usuarios as u on u.modo_id = p.modo_id and u.llave_nativa = p.tarjeta
),
tarjetas_corte as (
    select distinct c.corte, c.fecha_corte, o.unidad_id, o.modo_id, o.llave_nativa
    from observaciones as o
    inner join cortes as c on o.momento < datetime(c.fecha_corte)
)
select
    unidad_id,
    fecha_corte,
    corte,
    string_agg(llave_nativa, ';' order by modo_id, llave_nativa) as tarjetas,
    count(*) as n_tarjetas
from tarjetas_corte
group by unidad_id, fecha_corte, corte
