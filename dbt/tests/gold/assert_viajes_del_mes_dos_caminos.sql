-- Prueba de fuego de gobernanza (definiciones_oficiales.md §1): "viajes del mes" de junio 2026 calculados por dos
-- caminos independientes deben coincidir.
--   Camino A: fct_abordaje × dim_tiempo (un abordaje = un viaje), filtrando anio_mes = '2026-06'.
--   Camino B: fct_uso_usuario_dia (snapshot construido directamente desde Silver), SUM(abordajes) en junio 2026.
-- Devuelve una fila si difieren: si devuelve filas, la prueba falla.
with camino_a as (
    select sum(a.abordajes) as viajes
    from {{ ref('fct_abordaje') }} as a
    join {{ ref('dim_tiempo') }} as t on t.tiempo_sk = a.tiempo_sk
    where t.anio_mes = '2026-06'
),
camino_b as (
    select sum(abordajes) as viajes
    from {{ ref('fct_uso_usuario_dia') }}
    where fecha between date '2026-06-01' and date '2026-06-30'
)
select a.viajes as viajes_camino_a, b.viajes as viajes_camino_b, a.viajes - b.viajes as diferencia
from camino_a as a
cross join camino_b as b
where a.viajes != b.viajes or a.viajes is null or b.viajes is null
