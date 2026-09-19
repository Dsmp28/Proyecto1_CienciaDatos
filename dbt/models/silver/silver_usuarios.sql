-- Silver · una fila por (modo_id, llave_nativa) para toda llave observada en operación (catálogos mínimos
-- stg_catalogo_usuarios_*) o en el padrón (stg_padron_cdc_aplicado, modo por formato_tarjeta). Base de dim_usuario.
-- Identidad (ADR-007/008): usuario_sk = HMAC-SHA256(sal, modo|llave); usuario_base_id por formato (TM: TC-<i>,
-- TU: <i> a 10 dígitos, MR: MR<i>) o por inversión del MD5 sin sal de Aerómetro (silver_am_hash_map);
-- usuario_unificado_sk = HMAC-SHA256(sal, 'BASE|' || usuario_base_id). El padrón se une por usuario_base_id
-- (ADR-009: registro central de personas), por lo que perfil/zona llegan a cualquier modo de la misma persona.
with operacion as (
    select llave, operador as modo_id, n_registros from {{ ref('stg_catalogo_usuarios_tm') }}
    union all
    select llave, operador, n_registros from {{ ref('stg_catalogo_usuarios_tu') }}
    union all
    select llave, operador, n_registros from {{ ref('stg_catalogo_usuarios_mr') }}
    union all
    select llave, operador, n_registros from {{ ref('stg_catalogo_usuarios_am') }}
),
padron as (
    select
        tarjeta, formato_tarjeta as modo_id, usuario_base_id, estado_actual, perfil, zona_residencia, ultima_seq
    from {{ ref('stg_padron_cdc_aplicado') }}
    where formato_tarjeta in ('TM', 'TU', 'MR')
),
-- una persona por usuario_base_id (en el padrón cada persona aparece con una sola tarjeta; por seguridad se
-- toma la tarjeta con la operación más reciente si hubiera más de una)
padron_por_persona as (
    select usuario_base_id, estado_actual, perfil, zona_residencia
    from padron
    qualify row_number() over (partition by usuario_base_id order by ultima_seq desc, tarjeta) = 1
),
llaves as (
    select modo_id, llave as llave_nativa from operacion
    union distinct
    select modo_id, tarjeta from padron
),
vinculo as (
    select
        l.modo_id,
        l.llave_nativa,
        case
            when l.modo_id = 'TM' and regexp_contains(l.llave_nativa, r'^TC-\d{8}$')
                then safe_cast(regexp_extract(l.llave_nativa, r'^TC-(\d{8})$') as int64)
            when l.modo_id = 'TU' and regexp_contains(l.llave_nativa, r'^\d{10}$')
                then safe_cast(l.llave_nativa as int64)
            when l.modo_id = 'MR' and regexp_contains(l.llave_nativa, r'^MR\d{7}$')
                then safe_cast(regexp_extract(l.llave_nativa, r'^MR(\d{7})$') as int64)
            when l.modo_id = 'AM' then h.usuario_base_id
        end as usuario_base_id,
        case
            when l.modo_id in ('TM', 'TU', 'MR')
                and regexp_contains(l.llave_nativa, r'^(TC-\d{8}|\d{10}|MR\d{7})$') then 'formato'
            when l.modo_id = 'AM' and h.usuario_base_id is not null then 'inversion_md5'
        end as metodo_vinculo
    from llaves as l
    left join {{ ref('silver_am_hash_map') }} as h
        on l.modo_id = 'AM' and h.user_hash = l.llave_nativa
),
mapeo as (
    select valor_origen, zona_id from {{ ref('zonas_mapeo') }}
)
select
    {{ hmac_sha256("concat(v.modo_id, '|', v.llave_nativa)") }} as usuario_sk,
    v.modo_id,
    v.llave_nativa,
    v.usuario_base_id,
    v.metodo_vinculo,
    case
        when v.usuario_base_id is not null
        then {{ hmac_sha256("concat('BASE|', cast(v.usuario_base_id as string))") }}
    end as usuario_unificado_sk,
    p.usuario_base_id is not null as en_padron,
    p.perfil,
    p.zona_residencia,
    m.zona_id as zona_residencia_id,
    coalesce(p.estado_actual, 'SIN_PADRON') as estado_padron,
    coalesce(o.n_registros, 0) as n_registros_operacion
from vinculo as v
left join operacion as o on o.modo_id = v.modo_id and o.llave = v.llave_nativa
left join padron_por_persona as p on p.usuario_base_id = v.usuario_base_id
left join mapeo as m on m.valor_origen = p.zona_residencia
