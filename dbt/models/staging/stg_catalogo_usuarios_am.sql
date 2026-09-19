-- Staging · catálogo mínimo de usuarios de Aerómetro (rúbrica 1.2 / restricción dura 8): solo la llave nativa
-- distinta observada en los registros de operación (user_hash de aerometro_boardings). Sin atributos inventados;
-- n_registros es un conteo operativo (filas de operación con esa llave), no un atributo del usuario.
select
    user_hash as llave,
    'AM' as operador,
    count(*) as n_registros
from {{ ref('stg_aerometro_boardings') }}
where user_hash is not null
group by user_hash
