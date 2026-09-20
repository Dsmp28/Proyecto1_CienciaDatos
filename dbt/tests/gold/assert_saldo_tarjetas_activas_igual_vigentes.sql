-- Invariante de la medida semi aditiva tarjetas_activas_despues (fct_cambio_padron): el saldo tras la última operación
-- del log debe ser igual al número de tarjetas cuya versión vigente en dim_padron_historia tiene estado ACTIVA.
-- Devuelve una fila si difieren: si devuelve filas, la prueba falla.
with saldo as (
    select tarjetas_activas_despues as saldo_final
    from {{ ref('fct_cambio_padron') }}
    qualify row_number() over (order by seq desc) = 1
),
vigentes as (
    select countif(estado = 'ACTIVA') as activas_vigentes
    from {{ ref('dim_padron_historia') }}
    where es_vigente
)
select s.saldo_final, v.activas_vigentes, s.saldo_final - v.activas_vigentes as diferencia
from saldo as s
cross join vigentes as v
where s.saldo_final != v.activas_vigentes
