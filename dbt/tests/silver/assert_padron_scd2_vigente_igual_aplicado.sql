-- SCD2 del padrón: la fila vigente de cada tarjeta coincide con stg_padron_cdc_aplicado (estado_actual, perfil,
-- zona_residencia), es decir, ambas construcciones del padrón (aplicado por agregación y SCD2 por ventanas) dan lo
-- mismo. Devuelve las tarjetas con diferencia o sin contraparte: si devuelve filas, la prueba falla.
with vigente as (
    select tarjeta, estado, perfil, zona_residencia
    from {{ ref('silver_padron_scd2') }}
    where es_vigente
),
aplicado as (
    select tarjeta, estado_actual, perfil, zona_residencia
    from {{ ref('stg_padron_cdc_aplicado') }}
)
select
    coalesce(v.tarjeta, a.tarjeta) as tarjeta,
    v.estado as estado_scd2, a.estado_actual as estado_aplicado,
    v.perfil as perfil_scd2, a.perfil as perfil_aplicado,
    v.zona_residencia as zona_scd2, a.zona_residencia as zona_aplicado
from vigente as v
full outer join aplicado as a using (tarjeta)
where v.tarjeta is null
    or a.tarjeta is null
    or v.estado != a.estado_actual
    or coalesce(v.perfil, '') != coalesce(a.perfil, '')
    or coalesce(v.zona_residencia, '') != coalesce(a.zona_residencia, '')
