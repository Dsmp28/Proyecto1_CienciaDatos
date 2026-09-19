-- Toda columna de usuario_features está en diccionario_features y toda entrada del diccionario existe en la tabla.
-- Devuelve las diferencias en ambos sentidos: si devuelve filas, la prueba falla.
{% set uf = ref("usuario_features") %}
with columnas_tabla as (
    select column_name as columna
    from `{{ uf.database }}`.`{{ uf.schema }}`.INFORMATION_SCHEMA.COLUMNS
    where table_name = '{{ uf.identifier }}'
),
columnas_diccionario as (
    select columna from {{ ref('diccionario_features') }}
)
select 'falta en diccionario' as diferencia, columna
from columnas_tabla
where columna not in (select columna from columnas_diccionario)
union all
select 'sobra en diccionario', columna
from columnas_diccionario
where columna not in (select columna from columnas_tabla)
