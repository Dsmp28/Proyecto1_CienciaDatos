-- Gold · fct_cobertura_zona_modo. Hecho sin medidas (factless): una fila por (zona, modo) con al menos una estación o
-- parada en silver_estaciones. La existencia de la fila es el hecho ("el modo M sirve a la zona Z"); n_estaciones es un
-- conteo de apoyo. Cobertura del tablero: dim_zona LEFT JOIN este hecho; zona sin fila = zona sin servicio.
-- fuente_sk apunta al catálogo crudo del operador (un archivo por modo).
select
    zona_id,
    modo_id,
    count(*) as n_estaciones,
    count(distinct linea_ruta_eje) as n_lineas_rutas,
    min(to_hex(sha256(concat(fuente, '|', archivo, '|', coalesce(objeto_gcs, ''), '|', cast(ingest_date as string))))) as fuente_sk,
    true as tiene_servicio
from {{ ref('silver_estaciones') }}
group by zona_id, modo_id
