-- Silver · catálogo conformado de estaciones y paradas de los 4 modos (dim_estacion en Gold).
-- Filas válidas de val_estaciones (regla_id NULL). estacion_sk = SHA256(modo_id | codigo_nativo): hash determinista
-- de un código público de infraestructura (no es dato personal). zona_id conformada por el seed zonas_mapeo
-- (NOT NULL garantizado: lo no mapeado va a cuarentena por R05).
select
    to_hex(sha256(concat(modo_id, '|', codigo_nativo))) as estacion_sk,
    modo_id,
    codigo_nativo,
    nombre,
    linea_ruta_eje,
    zona_origen,
    zona_id,
    lat,
    lon,
    km,
    -- linaje
    fuente,
    archivo,
    objeto_gcs,
    ingest_date,
    registro_hash
from {{ ref('val_estaciones') }}
where regla_id is null
