-- Gold no pierde ni inventa abordajes: COUNT(fct_abordaje) = COUNT(silver_abordajes), en total y por modo.
-- Devuelve las filas (modo o TOTAL) con diferencia distinta de 0: si devuelve filas, la prueba falla.
with gold as (
    select modo_id, count(*) as n from {{ ref('fct_abordaje') }} group by modo_id
    union all
    select 'TOTAL', count(*) from {{ ref('fct_abordaje') }}
),
silver as (
    select modo_id, count(*) as n from {{ ref('silver_abordajes') }} group by modo_id
    union all
    select 'TOTAL', count(*) from {{ ref('silver_abordajes') }}
)
select
    coalesce(g.modo_id, s.modo_id) as modo_id,
    g.n as filas_gold,
    s.n as filas_silver,
    coalesce(g.n, 0) - coalesce(s.n, 0) as diferencia
from gold as g
full outer join silver as s on s.modo_id = g.modo_id
where coalesce(g.n, 0) != coalesce(s.n, 0)
