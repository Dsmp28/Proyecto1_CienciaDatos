{#- Usa el +schema tal cual (staging, silver, gold...) sin el prefijo del dataset del perfil.
    Proyecto 2 (ADR-015): con el target `recorte` cada esquema recibe el sufijo `_recorte` (staging_recorte,
    silver_recorte, ...): así la prueba de recorte reconstruye las capas con los datos truncados en datasets
    aparte sin tocar las tablas oficiales. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set base = target.schema if custom_schema_name is none else custom_schema_name | trim -%}
    {%- if target.name == 'recorte' -%}
        {{ base ~ '_recorte' }}
    {%- else -%}
        {{ base }}
    {%- endif -%}
{%- endmacro %}
