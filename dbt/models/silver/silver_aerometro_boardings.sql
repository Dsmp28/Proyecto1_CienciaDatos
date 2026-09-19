-- Silver · boardings válidos de Aerómetro (regla_id NULL en val_aerometro_boardings), tipados y unificados:
-- fecha_hora_local DATETIME = DATETIME(timestamp_utc, tz_local) (conversión hecha en staging, ADR-010),
-- monto_q = fare. Conserva timestamp_utc original y la llave nativa user_hash.
with validas as (
    select * from {{ ref('val_aerometro_boardings') }}
    where regla_id is null
),
estaciones as (
    select estacion_sk, codigo_nativo, zona_id
    from {{ ref('silver_estaciones') }}
    where modo_id = 'AM'
)
select
    v.boarding_id,
    'AM' as modo_id,
    v.user_hash as llave_nativa,
    v.station_code as codigo_estacion_nativo,
    e.estacion_sk,
    e.zona_id,
    v.axis,
    v.timestamp_utc,
    v.fecha_hora_local,
    date(v.fecha_hora_local) as fecha,
    extract(hour from v.fecha_hora_local) as hora,
    v.cabin_number,
    v.fare as monto_q,
    -- linaje
    v.fuente,
    v.archivo,
    v.objeto_gcs,
    v.ingest_date,
    v.registro_hash,
    v.linea_num,
    v.kafka_offset,
    v.kafka_topico,
    v.kafka_particion,
    v.sha256_archivo,
    v.ingest_ts
from validas as v
left join estaciones as e on e.codigo_nativo = v.station_code
