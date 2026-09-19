-- Staging · catálogo mínimo de usuarios de Transurbano (rúbrica 1.2 / restricción dura 8): solo la llave nativa
-- distinta observada en los registros de operación (num_tarjeta de transurbano_transacciones). Sin atributos inventados;
-- n_registros es un conteo operativo (filas de operación con esa llave), no un atributo del usuario.
select
    num_tarjeta as llave,
    'TU' as operador,
    count(*) as n_registros
from {{ ref('stg_transurbano_transacciones') }}
where num_tarjeta is not null
group by num_tarjeta
