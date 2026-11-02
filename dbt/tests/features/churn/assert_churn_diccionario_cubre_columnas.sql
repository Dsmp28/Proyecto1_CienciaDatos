-- Toda columna de churn_dataset está en churn_diccionario y toda entrada del diccionario existe en la tabla.
-- Devuelve las diferencias en ambos sentidos: si devuelve filas, la prueba falla.
{% set d = ref("churn_dataset") %}
with columnas_tabla as (
    select column_name as columna
    from `{{ d.database }}`.`{{ d.schema }}`.INFORMATION_SCHEMA.COLUMNS
    where table_name = '{{ d.identifier }}'
),
columnas_diccionario as (
    select columna from {{ ref('churn_diccionario') }}
)
select 'falta en diccionario' as diferencia, columna
from columnas_tabla
where columna not in (select columna from columnas_diccionario)
union all
select 'sobra en diccionario', columna
from columnas_diccionario
where columna not in (select columna from columnas_tabla)
