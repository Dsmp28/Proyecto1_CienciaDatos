-- Conciliación Bronze = Staging (rúbrica: staging no filtra ni deduplica).
-- Para cada una de las 9 fuentes compara COUNT(*) de la tabla externa de Bronze con COUNT(*) del modelo
-- stg_<fuente>. Devuelve las fuentes con diferencia distinta de 0: si devuelve filas, la prueba falla.
{% set fuentes = [
    'tm_estaciones', 'tu_paradas', 'mr_estaciones', 'am_estaciones',
    'metroriel_viajes', 'transurbano_transacciones',
    'transmetro_validaciones', 'aerometro_boardings',
    'cdc_padron_usuarios',
] %}
with conteos as (
    {% for f in fuentes %}
    select
        '{{ f }}' as fuente,
        (select count(*) from {{ source('bronze', f) }}) as filas_bronze,
        (select count(*) from {{ ref('stg_' ~ f) }}) as filas_staging
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)
select
    fuente,
    filas_bronze,
    filas_staging,
    filas_staging - filas_bronze as diferencia
from conteos
where filas_staging != filas_bronze
