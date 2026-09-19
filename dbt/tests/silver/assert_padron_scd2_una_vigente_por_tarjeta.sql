-- SCD2 del padrón: exactamente una fila es_vigente por tarjeta.
-- Devuelve las tarjetas con 0 o más de 1 vigente: si devuelve filas, la prueba falla.
select tarjeta, countif(es_vigente) as n_vigentes
from {{ ref('silver_padron_scd2') }}
group by tarjeta
having countif(es_vigente) != 1
