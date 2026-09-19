-- Regla R03 en la salida: ningún abordaje de silver_abordajes tiene fecha >= var('fecha_referencia').
-- Devuelve las filas del futuro: si devuelve filas, la prueba falla.
select abordaje_id, modo_id, fecha, fecha_hora_local
from {{ ref('silver_abordajes') }}
where fecha >= date('{{ var("fecha_referencia") }}')
