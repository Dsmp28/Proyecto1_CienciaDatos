{#- Proyecto 2 (ADR-015): prueba de recorte. Con var('recorte_datos_hasta') (DATE) staging ignora todo evento cuya
    fecha local sea posterior, como si los archivos crudos terminaran ahí. Con la var nula (por defecto) todas las
    macros emiten cadena vacía y el SQL generado es idéntico al original. -#}

{#- Condición adicional ("and (...)") para un where existente. Filas con fecha no parseable (nulo) se conservan:
    Silver las rechaza con su regla de fecha, igual que sin recorte. -#}
{% macro filtro_recorte(expr_datetime_local) -%}
{%- if var('recorte_datos_hasta') is not none -%}
and ({{ expr_datetime_local }} is null or date({{ expr_datetime_local }}) <= date('{{ var("recorte_datos_hasta") }}'))
{%- endif -%}
{%- endmacro %}

{#- Igual que filtro_recorte pero abre el where (para modelos que no tienen uno). -#}
{% macro donde_recorte(expr_datetime_local) -%}
{%- if var('recorte_datos_hasta') is not none %}
where true {{ filtro_recorte(expr_datetime_local) }}
{%- endif -%}
{%- endmacro %}

{#- MetroRiel: devuelve `expr` tal cual o, con recorte, nulo cuando la salida cae después del recorte
    (`cond_salida_posterior` es una expresión booleana). Equivale a un archivo truncado antes de la salida. -#}
{% macro recortar_salida(expr, cond_salida_posterior, valor_recortado='null') -%}
{%- if var('recorte_datos_hasta') is not none -%}
if({{ cond_salida_posterior }}, {{ valor_recortado }}, {{ expr }})
{%- else -%}
{{ expr }}
{%- endif -%}
{%- endmacro %}
