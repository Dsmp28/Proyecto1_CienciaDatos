-- La etiqueta es NULL si y solo si el horizonte no está completamente observado (t + horizonte_dias > fecha_referencia).
-- Devuelve las filas que violan la regla en cualquier sentido: si devuelve filas, la prueba falla.
select unidad_id, fecha_corte, etiqueta
from {{ ref('churn_dataset') }}
where (etiqueta is null)
    != (date_add(fecha_corte, interval {{ var('horizonte_dias') }} day) > date('{{ var("fecha_referencia") }}'))
