-- Silver · padrón como SCD Tipo 2 construido desde el log completo de CDC con funciones de ventana (ADR-009).
-- Grano: una fila por operación con llave (filas válidas de val_cdc_padron_usuarios; SIN-TARJETA va a cuarentena).
-- La vigencia se ordena por seq (la verdad del log): vigente_desde = commit_ts, vigente_hasta = commit_ts de la
-- siguiente operación de la misma tarjeta; es_vigente cuando no hay siguiente. Los atributos perfil y zona_residencia
-- son el último valor no nulo hasta esa operación (los DELETE llegan sin cuerpo y conservan los previos).
-- commit_ts_fuera_de_orden marca los casos en que el generador asignó a la siguiente op una hora anterior
-- dentro del mismo día (vigente_hasta < vigente_desde); no altera la vigencia por seq.
with ops as (
    select
        tarjeta, usuario_base_id, formato_tarjeta, seq, op, commit_ts, perfil, zona_residencia,
        fuente, archivo, objeto_gcs, ingest_date, registro_hash
    from {{ ref('val_cdc_padron_usuarios') }}
    where regla_id is null
),
ventana as (
    select
        *,
        row_number() over (partition by tarjeta order by seq) as version,
        lead(commit_ts) over (partition by tarjeta order by seq) as vigente_hasta,
        countif(op = 'INSERT') over (
            partition by tarjeta order by seq rows between unbounded preceding and 1 preceding
        ) as n_insert_previos,
        last_value(perfil ignore nulls) over (
            partition by tarjeta order by seq rows between unbounded preceding and current row
        ) as perfil_vigente,
        last_value(zona_residencia ignore nulls) over (
            partition by tarjeta order by seq rows between unbounded preceding and current row
        ) as zona_vigente
    from ops
),
mapeo as (
    select valor_origen, zona_id from {{ ref('zonas_mapeo') }}
)
select
    v.tarjeta,
    v.usuario_base_id,
    v.formato_tarjeta as modo_id,
    v.seq,
    v.op,
    v.commit_ts as vigente_desde,
    v.vigente_hasta,
    v.vigente_hasta is null as es_vigente,
    v.version,
    if(v.op = 'DELETE', 'INACTIVA', 'ACTIVA') as estado,
    v.perfil_vigente as perfil,
    v.zona_vigente as zona_residencia,
    m.zona_id as zona_residencia_id,
    v.version = 1 and v.op != 'INSERT' as alta_implicita,
    v.op = 'INSERT' and v.version > 1 as alta_repetida,
    v.op = 'DELETE' and v.n_insert_previos = 0 as baja_sin_alta_previa,
    coalesce(v.vigente_hasta < v.commit_ts, false) as commit_ts_fuera_de_orden,
    -- linaje
    v.fuente,
    v.archivo,
    v.objeto_gcs,
    v.ingest_date,
    v.registro_hash
from ventana as v
left join mapeo as m on m.valor_origen = v.zona_vigente
