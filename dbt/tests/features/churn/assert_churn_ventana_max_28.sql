-- Ningún evento de la ventana queda fuera de [t - ventana_max_dias, t): dias_antes_corte entre 1 y ventana_max_dias.
-- Los del horizonte están a t o después (dias_antes_corte <= 0). Si devuelve filas, la prueba falla.
select corte, unidad_id, abordaje_id, tramo, dias_antes_corte
from {{ ref('churn_eventos') }}
where (tramo = 'ventana' and dias_antes_corte not between 1 and {{ var('ventana_max_dias') }})
   or (tramo = 'horizonte' and (dias_antes_corte > 0 or dias_antes_corte <= -{{ var('horizonte_dias') }}))
