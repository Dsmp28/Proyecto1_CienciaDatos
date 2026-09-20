{{ config(cluster_by=['modo_id']) }}
-- Gold · dim_usuario. Grano: una tarjeta seudonimizada por modo (ADR-008). Viene de silver_usuarios SIN la llave nativa
-- ni usuario_base_id (seguridad.md §2: Gold solo lleva usuario_sk = HMAC-SHA256 con sal secreta y usuario_unificado_sk).
-- n_modos_usados y es_multimodal se calculan sobre silver_abordajes por usuario_unificado_sk (persona), de modo que las
-- tarjetas de la misma persona en distintos modos comparten el valor. Atributos del padrón: solo los conformados.
with uso as (
    select
        u.usuario_unificado_sk,
        count(distinct a.modo_id) as n_modos_usados,
        count(*) as n_abordajes_persona
    from {{ ref('silver_abordajes') }} as a
    join {{ ref('silver_usuarios') }} as u
        on u.modo_id = a.modo_id and u.llave_nativa = a.llave_nativa
    where u.usuario_unificado_sk is not null
    group by u.usuario_unificado_sk
),
uso_tarjeta as (
    select modo_id, llave_nativa, count(*) as n_abordajes_tarjeta
    from {{ ref('silver_abordajes') }}
    group by modo_id, llave_nativa
)
select
    u.usuario_sk,
    u.usuario_unificado_sk,
    u.modo_id,
    u.metodo_vinculo,
    u.usuario_unificado_sk is not null as tiene_vinculo,
    u.en_padron,
    u.perfil,
    u.zona_residencia_id,
    u.estado_padron,
    coalesce(ut.n_abordajes_tarjeta, 0) as n_abordajes_tarjeta,
    coalesce(p.n_abordajes_persona, ut.n_abordajes_tarjeta, 0) as n_abordajes_persona,
    coalesce(p.n_modos_usados, if(ut.n_abordajes_tarjeta > 0, 1, 0), 0) as n_modos_usados,
    coalesce(p.n_modos_usados, 0) > 1 as es_multimodal
from {{ ref('silver_usuarios') }} as u
left join uso as p on p.usuario_unificado_sk = u.usuario_unificado_sk
left join uso_tarjeta as ut on ut.modo_id = u.modo_id and ut.llave_nativa = u.llave_nativa
