-- Coherencia de ventanas: viajes_7d <= viajes_30d <= viajes_90d <= viajes_total y ninguna negativa.
-- Devuelve las personas que rompen el orden: si devuelve filas, la prueba falla.
select usuario_unificado_sk, viajes_7d, viajes_30d, viajes_90d, viajes_total
from {{ ref('usuario_features') }}
where not (0 <= viajes_7d and viajes_7d <= viajes_30d and viajes_30d <= viajes_90d and viajes_90d <= viajes_total)
   or viajes_30d_previos < 0
   or viajes_30d_previos + viajes_30d > viajes_total
