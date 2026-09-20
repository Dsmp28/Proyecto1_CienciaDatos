-- Gold · dim_estacion. Grano: una estación o parada de cualquier modo. Copia conformada de silver_estaciones
-- (catálogos de los 4 operadores ya validados y con zona conformada). estacion_sk es un hash determinista de
-- modo|código público de infraestructura (no es dato personal). archivo_origen y fuente_sk dan el linaje al catálogo crudo.
select
    e.estacion_sk,
    e.modo_id,
    e.codigo_nativo,
    e.nombre,
    e.linea_ruta_eje,
    e.zona_id,
    e.lat,
    e.lon,
    e.km,
    e.archivo as archivo_origen,
    to_hex(sha256(concat(e.fuente, '|', e.archivo, '|', coalesce(e.objeto_gcs, ''), '|', cast(e.ingest_date as string)))) as fuente_sk
from {{ ref('silver_estaciones') }} as e
