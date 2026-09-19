-- ADR-008: toda llave (user_hash) de stg_catalogo_usuarios_am existe en silver_am_hash_map (relationships).
-- Si alguna no se invierte, usuario_base_id quedaría nulo para Aerómetro. Devuelve las llaves sin
-- correspondencia: si devuelve filas, la prueba falla.
select u.llave, u.n_registros
from {{ ref('stg_catalogo_usuarios_am') }} as u
left join {{ ref('silver_am_hash_map') }} as h on h.user_hash = u.llave
where h.user_hash is null
