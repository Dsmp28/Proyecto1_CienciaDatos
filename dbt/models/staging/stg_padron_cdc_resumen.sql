-- Staging · resumen del CDC del padrón (rúbrica 1.2): UNA fila con operaciones, altas, cambios, bajas,
-- anomalías del log y tarjetas activas antes y después de aplicar los DELETE (ADR-009).
-- Identidades que deben cuadrar (se verifican en docs/evidence/cdc_resumen.md):
--   ops_total = inserts + updates + deletes
--   inserts   = altas_aplicadas + altas_repetidas + inserts_sin_tarjeta
--   updates   = cambios_aplicados + updates_sin_tarjeta
--   tarjetas_distintas = altas_aplicadas + altas_implicitas = activas_despues_de_borrados + bajas_aplicadas
--   activas_antes_de_borrados = tarjetas_distintas - tarjetas_solo_delete
--   activas_despues_de_borrados = activas_antes_de_borrados - (bajas_aplicadas - tarjetas_solo_delete)
with ops as (
    select * from {{ ref('stg_cdc_padron_usuarios') }}
),
aplicado as (
    select * from {{ ref('stg_padron_cdc_aplicado') }}
),
por_op as (
    select
        count(*) as ops_total,
        countif(op = 'INSERT') as inserts,
        countif(op = 'UPDATE') as updates,
        countif(op = 'DELETE') as deletes,
        countif(tarjeta is null or tarjeta = 'SIN-TARJETA') as filas_sin_tarjeta,
        countif(op = 'INSERT' and (tarjeta is null or tarjeta = 'SIN-TARJETA')) as inserts_sin_tarjeta,
        countif(op = 'UPDATE' and (tarjeta is null or tarjeta = 'SIN-TARJETA')) as updates_sin_tarjeta,
        countif(op = 'DELETE' and (tarjeta is null or tarjeta = 'SIN-TARJETA')) as deletes_sin_tarjeta,
        any_value(fuente) as fuente,
        min(archivo) as archivo,
        max(ingest_date) as ingest_date
    from ops
),
por_tarjeta as (
    select
        count(*) as tarjetas_distintas,
        countif(primera_op = 'INSERT') as altas_aplicadas,
        countif(alta_implicita) as altas_implicitas,
        sum(n_insert_sobre_existente) as altas_repetidas,
        countif(alta_repetida) as tarjetas_con_insert_repetido,
        sum(n_update) as cambios_aplicados,
        countif(estado_actual = 'INACTIVA') as bajas_aplicadas,
        countif(baja_sin_alta_previa) as bajas_sin_alta_previa,
        sum(n_delete_sin_alta_previa) as deletes_sin_alta_previa,
        countif(n_insert + n_update > 0) as activas_antes_de_borrados,
        countif(n_insert + n_update = 0) as tarjetas_solo_delete,
        countif(estado_actual = 'ACTIVA') as activas_despues_de_borrados
    from aplicado
)
select
    o.ops_total,
    o.inserts,
    o.updates,
    o.deletes,
    o.filas_sin_tarjeta,
    o.inserts_sin_tarjeta,
    o.updates_sin_tarjeta,
    o.deletes_sin_tarjeta,
    t.tarjetas_distintas,
    t.altas_aplicadas,
    t.altas_implicitas,
    t.altas_repetidas,
    t.tarjetas_con_insert_repetido,
    t.cambios_aplicados,
    t.bajas_aplicadas,
    t.bajas_sin_alta_previa,
    t.deletes_sin_alta_previa,
    t.tarjetas_solo_delete,
    t.activas_antes_de_borrados,
    t.activas_despues_de_borrados,
    o.fuente,
    o.archivo,
    o.ingest_date
from por_op as o
cross join por_tarjeta as t
