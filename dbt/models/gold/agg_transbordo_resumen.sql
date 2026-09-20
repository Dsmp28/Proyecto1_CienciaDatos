-- Gold · agg_transbordo_resumen. Resumen de agg_transbordo por número de modos usados: usuarios (personas), porcentaje
-- sobre el total de personas con vínculo, abordajes y combinación de modos más frecuente. Cifra de portada de la
-- pregunta de transbordo del tablero.
with base as (
    select n_modos, count(*) as usuarios, sum(abordajes) as abordajes
    from {{ ref('agg_transbordo') }}
    group by n_modos
),
combinacion as (
    select n_modos, modos, count(*) as usuarios_combinacion
    from {{ ref('agg_transbordo') }}
    group by n_modos, modos
    qualify row_number() over (partition by n_modos order by count(*) desc, modos) = 1
)
select
    b.n_modos,
    b.n_modos > 1 as es_multimodal,
    b.usuarios,
    round(100 * b.usuarios / sum(b.usuarios) over (), 2) as pct_usuarios,
    b.abordajes,
    round(b.abordajes / b.usuarios, 2) as abordajes_por_usuario,
    c.modos as combinacion_mas_frecuente,
    c.usuarios_combinacion
from base as b
join combinacion as c on c.n_modos = b.n_modos
