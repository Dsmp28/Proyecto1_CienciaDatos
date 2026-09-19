-- Staging · catálogo mínimo de usuarios de MetroRiel (rúbrica 1.2 / restricción dura 8): solo la llave nativa
-- distinta observada en los registros de operación (card de metroriel_viajes). Sin atributos inventados;
-- n_registros es un conteo operativo (filas de operación con esa llave), no un atributo del usuario.
select
    card as llave,
    'MR' as operador,
    count(*) as n_registros
from {{ ref('stg_metroriel_viajes') }}
where card is not null
group by card
