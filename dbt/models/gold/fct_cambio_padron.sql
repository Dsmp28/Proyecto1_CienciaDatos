{{ config(cluster_by=['usuario_sk']) }}
-- Gold · fct_cambio_padron. Grano: una operación del log CDC aplicada al padrón (INSERT/UPDATE/DELETE), desde
-- silver_padron_scd2 con la tarjeta sustituida por usuario_sk (silver_usuarios). Conserva las banderas de calidad del
-- CDC (alta_implicita, alta_repetida, baja_sin_alta_previa; ADR-009).
-- Regla de tarjetas_activas_despues (medida semi aditiva: saldo, se compara entre instantes, no se suma en el tiempo):
--   estado_previo = estado de la versión anterior de la misma tarjeta (NULL si la tarjeta no existía);
--   delta_activas = +1 si la operación deja ACTIVA una tarjeta antes INACTIVA o inexistente,
--                   −1 si deja INACTIVA una tarjeta que estaba ACTIVA,
--                    0 en cualquier otro caso (INSERT repetido sobre ACTIVA, UPDATE de ACTIVA, DELETE sin alta previa);
--   tarjetas_activas_despues = SUM(delta_activas) acumulado en orden de seq (ventana sobre todo el log).
--   Invariante (assert_saldo_tarjetas_activas_igual_vigentes): el último saldo = tarjetas vigentes con estado ACTIVA.
with ops as (
    select
        p.seq,
        p.tarjeta,
        p.modo_id,
        p.version,
        p.op,
        p.vigente_desde,
        p.estado,
        lag(p.estado) over (partition by p.tarjeta order by p.seq) as estado_previo,
        p.perfil,
        p.zona_residencia_id,
        p.alta_implicita,
        p.alta_repetida,
        p.baja_sin_alta_previa,
        p.fuente, p.archivo, p.objeto_gcs, p.ingest_date
    from {{ ref('silver_padron_scd2') }} as p
),
delta as (
    select
        *,
        case
            when estado = 'ACTIVA' and (estado_previo is null or estado_previo = 'INACTIVA') then 1
            when estado = 'INACTIVA' and estado_previo = 'ACTIVA' then -1
            else 0
        end as delta_activas
    from ops
),
usuarios as (
    select modo_id, llave_nativa, usuario_sk, usuario_unificado_sk
    from {{ ref('silver_usuarios') }}
)
select
    d.seq,
    cast(format_date('%Y%m%d', date(d.vigente_desde)) as int64) * 100 + extract(hour from d.vigente_desde) as tiempo_sk,
    date(d.vigente_desde) as fecha,
    d.vigente_desde as fecha_hora,
    u.usuario_sk,
    u.usuario_unificado_sk,
    d.modo_id,
    d.version,
    d.op as operacion,
    d.estado as estado_resultante,
    d.estado_previo,
    d.perfil,
    d.zona_residencia_id,
    d.alta_implicita,
    d.alta_repetida,
    d.baja_sin_alta_previa,
    1 as operaciones,
    d.delta_activas,
    sum(d.delta_activas) over (order by d.seq rows between unbounded preceding and current row) as tarjetas_activas_despues,
    to_hex(sha256(concat(d.fuente, '|', d.archivo, '|', coalesce(d.objeto_gcs, ''), '|', cast(d.ingest_date as string)))) as fuente_sk
from delta as d
join usuarios as u on u.modo_id = d.modo_id and u.llave_nativa = d.tarjeta
