-- Staging · catálogo mínimo de usuarios de Transmetro (rúbrica 1.2 / restricción dura 8): solo la llave nativa
-- distinta observada en los registros de operación (tarjeta de transmetro_validaciones). Sin atributos inventados;
-- n_registros es un conteo operativo (filas de operación con esa llave), no un atributo del usuario.
select
    tarjeta as llave,
    'TM' as operador,
    count(*) as n_registros
from {{ ref('stg_transmetro_validaciones') }}
where tarjeta is not null
group by tarjeta
