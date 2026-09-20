-- Restricción dura 7 / seguridad.md §2: ninguna tabla del dataset gold expone una llave nativa de usuario ni el
-- identificador base. Consulta el INFORMATION_SCHEMA del dataset gold del proyecto objetivo tras construir los modelos
-- (depends_on fuerza el orden en dbt build). Si devuelve filas, la prueba falla.
-- depends_on: {{ ref('dim_usuario') }}, {{ ref('dim_padron_historia') }}, {{ ref('fct_abordaje') }},
-- depends_on: {{ ref('fct_viaje_metroriel') }}, {{ ref('fct_uso_usuario_dia') }}, {{ ref('fct_cambio_padron') }},
-- depends_on: {{ ref('agg_transbordo') }}, {{ ref('agg_demanda_modo_zona_hora') }}, {{ ref('agg_metroriel_zonas') }}
select table_name, column_name
from `{{ target.project }}.gold.INFORMATION_SCHEMA.COLUMNS`
where lower(column_name) in ('llave_nativa', 'tarjeta', 'num_tarjeta', 'card', 'user_hash', 'usuario_base_id')
