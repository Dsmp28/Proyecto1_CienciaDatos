-- Toda persona del dataset de churn tiene fila en silver_unidad_tarjetas_corte para su corte, y las tarjetas que
-- usó en la ventana están contenidas en `tarjetas` (solo se conocen tarjetas observadas antes de t).
-- Devuelve los incumplimientos: si devuelve filas, la prueba falla.
with usadas as (
    select e.corte, e.unidad_id, count(distinct e.tarjeta_sk) as n_usadas
    from {{ ref('churn_eventos') }} as e
    inner join {{ ref('churn_dataset') }} as d on d.corte = e.corte and d.unidad_id = e.unidad_id
    where e.tramo = 'ventana'
    group by e.corte, e.unidad_id
)
select d.corte, d.unidad_id, t.n_tarjetas, u.n_usadas
from {{ ref('churn_dataset') }} as d
left join {{ ref('silver_unidad_tarjetas_corte') }} as t on t.corte = d.corte and t.unidad_id = d.unidad_id
left join usadas as u on u.corte = d.corte and u.unidad_id = d.unidad_id
where t.unidad_id is null or t.n_tarjetas < u.n_usadas
