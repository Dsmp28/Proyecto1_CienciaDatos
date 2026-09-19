-- Cuarentena · conteo de rechazos por (fuente, regla_id, motivo) con el total de filas de staging de la fuente
-- y el porcentaje (3 decimales). Además una fila regla_id = 'TOTAL' por fuente (todas las fuentes, aunque tengan
-- 0 rechazos) para la conciliación staging = silver + cuarentena de docs/METRICAS.md.
with etiquetas as (
    select fuente, regla_id, motivo from {{ ref('val_transmetro_validaciones') }}
    union all
    select fuente, regla_id, motivo from {{ ref('val_transurbano_transacciones') }}
    union all
    select fuente, regla_id, motivo from {{ ref('val_metroriel_viajes') }}
    union all
    select fuente, regla_id, motivo from {{ ref('val_aerometro_boardings') }}
    union all
    select fuente, regla_id, motivo from {{ ref('val_cdc_padron_usuarios') }}
    union all
    select fuente, regla_id, motivo from {{ ref('val_estaciones') }}
),
totales as (
    select fuente, count(*) as n_total_fuente, countif(regla_id is not null) as n_rechazados_total
    from etiquetas
    group by fuente
),
por_regla as (
    select fuente, regla_id, motivo, count(*) as n_rechazados
    from etiquetas
    where regla_id is not null
    group by fuente, regla_id, motivo
),
unido as (
    select r.fuente, r.regla_id, r.motivo, r.n_rechazados, t.n_total_fuente
    from por_regla as r
    join totales as t using (fuente)
    union all
    select fuente, 'TOTAL', 'Total en cuarentena', n_rechazados_total, n_total_fuente
    from totales
)
select
    fuente,
    regla_id,
    motivo,
    n_rechazados,
    n_total_fuente,
    round(safe_divide(n_rechazados, n_total_fuente) * 100, 3) as pct
from unido
order by fuente, regla_id
