-- Staging · padrón vigente tras aplicar el log de CDC en orden de `seq` (ADR-009).
-- Grano: una fila por tarjeta. Excluye 'SIN-TARJETA' (sin llave: va a cuarentena en Silver, regla R07;
-- se cuentan en stg_padron_cdc_resumen.filas_sin_tarjeta).
-- Reglas: la última op define el estado (DELETE -> INACTIVA, si no ACTIVA); perfil y zona_residencia son el
-- último valor NO nulo hasta la última op (los DELETE llegan sin cuerpo y conservan los atributos previos);
-- UPDATE sin INSERT previo = alta implícita; DELETE sin INSERT previo = baja sin alta previa; INSERT sobre
-- llave existente se aplica como UPDATE y se cuenta como alta repetida.
with ops as (
    select
        tarjeta, seq, op, commit_ts, perfil, zona_residencia, usuario_base_id, formato_tarjeta,
        fuente, archivo, ingest_date
    from {{ ref('stg_cdc_padron_usuarios') }}
    where tarjeta is not null and tarjeta != 'SIN-TARJETA'
),
ventana as (
    select
        *,
        row_number() over (partition by tarjeta order by seq) as rn_asc,
        row_number() over (partition by tarjeta order by seq desc) as rn_desc,
        -- INSERT anteriores a esta operación (sin contar la actual)
        countif(op = 'INSERT') over (
            partition by tarjeta order by seq rows between unbounded preceding and 1 preceding
        ) as n_insert_previos,
        -- atributos vigentes en cada punto de la secuencia (último valor no nulo)
        last_value(perfil ignore nulls) over (
            partition by tarjeta order by seq rows between unbounded preceding and current row
        ) as perfil_vigente,
        last_value(zona_residencia ignore nulls) over (
            partition by tarjeta order by seq rows between unbounded preceding and current row
        ) as zona_vigente
    from ops
)
select
    tarjeta,
    any_value(usuario_base_id) as usuario_base_id,
    any_value(formato_tarjeta) as formato_tarjeta,
    if(max(if(rn_desc = 1, op, null)) = 'DELETE', 'INACTIVA', 'ACTIVA') as estado_actual,
    max(if(rn_desc = 1, perfil_vigente, null)) as perfil,
    max(if(rn_desc = 1, zona_vigente, null)) as zona_residencia,
    max(if(rn_asc = 1, op, null)) as primera_op,
    min(seq) as primera_seq,
    max(if(rn_desc = 1, op, null)) as ultima_op,
    max(seq) as ultima_seq,
    max(if(rn_desc = 1, commit_ts, null)) as ultimo_commit_ts,
    count(*) as n_ops,
    countif(op = 'INSERT') as n_insert,
    countif(op = 'UPDATE') as n_update,
    countif(op = 'DELETE') as n_delete,
    -- INSERT que llegan cuando la llave ya existe (por INSERT o por alta implícita): se aplican como UPDATE
    countif(op = 'INSERT' and rn_asc > 1) as n_insert_sobre_existente,
    -- DELETE que llegan sin ningún INSERT antes en la secuencia
    countif(op = 'DELETE' and n_insert_previos = 0) as n_delete_sin_alta_previa,
    max(if(rn_asc = 1, op, null)) != 'INSERT' as alta_implicita,
    countif(op = 'DELETE' and n_insert_previos = 0) > 0 as baja_sin_alta_previa,
    countif(op = 'INSERT') > 1 as alta_repetida,
    -- linaje
    any_value(fuente) as fuente,
    min(archivo) as archivo,
    max(ingest_date) as ingest_date
from ventana
group by tarjeta
