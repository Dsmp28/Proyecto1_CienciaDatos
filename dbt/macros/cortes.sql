{#- Proyecto 2 (ADR-015): CTE de fechas de corte del dataset de churn. Itera var('fechas_corte'); la letra del corte es
    chr(65 + i): A, B, C. Uso: with cortes as ({{ cortes_cte() }}). Sin CURRENT_DATE: las fechas son parámetros. -#}
{% macro cortes_cte() -%}
{%- for f in var('fechas_corte') -%}
select date('{{ f }}') as fecha_corte, '{{ 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[loop.index0] }}' as corte
{% if not loop.last %}union all
{% endif -%}
{%- endfor -%}
{%- endmacro %}
