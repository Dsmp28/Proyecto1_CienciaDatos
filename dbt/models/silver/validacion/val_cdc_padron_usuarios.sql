-- Validación · log de CDC del padrón. TODAS las filas de stg_cdc_padron_usuarios con `regla_id` (NULL = válida) y `motivo`.
-- Orden: R11 (op fuera de INSERT/UPDATE/DELETE o seq nulo) → R07 (tarjeta nula o SIN-TARJETA) → R08 (commit_ts
-- no parseable) → R05 (zona_residencia presente pero ausente en el seed zonas_mapeo).
-- INSERT repetido, UPDATE sin INSERT y DELETE sin INSERT NO se rechazan: se aplican (ADR-009).
with base as (
    select * from {{ ref('stg_cdc_padron_usuarios') }}
),
mapeo as (
    select distinct valor_origen from {{ ref('zonas_mapeo') }}
),
etiquetado as (
    select
        b.*,
        case
            when b.op is null or b.op not in ('INSERT', 'UPDATE', 'DELETE') or b.seq is null then 'R11'
            when b.tarjeta is null or b.tarjeta = 'SIN-TARJETA' then 'R07'
            when b.commit_ts is null then 'R08'
            when b.zona_residencia is not null and m.valor_origen is null then 'R05'
        end as regla_id
    from base as b
    left join mapeo as m on m.valor_origen = b.zona_residencia
)
select
    *,
    case regla_id
        when 'R11' then 'R11 operacion cdc invalida'
        when 'R07' then 'R07 llave de usuario nula'
        when 'R08' then 'R08 fecha no parseable'
        when 'R05' then 'R05 zona sin mapear'
    end as motivo
from etiquetado
