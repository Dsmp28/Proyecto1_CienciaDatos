-- Silver · validaciones válidas de Transmetro (regla_id NULL en val_transmetro_validaciones), tipadas y unificadas:
-- fecha_hora_local DATETIME (ya local en origen), fecha, hora, monto_q NUMERIC (= tarifa), estacion_sk y zona_id
-- desde silver_estaciones. Conserva la llave nativa (tarjeta): la seudonimización ocurre en Gold vía silver_usuarios.
with validas as (
    select * from {{ ref('val_transmetro_validaciones') }}
    where regla_id is null
),
estaciones as (
    select estacion_sk, codigo_nativo, zona_id
    from {{ ref('silver_estaciones') }}
    where modo_id = 'TM'
)
select
    v.validacion_id,
    'TM' as modo_id,
    v.tarjeta as llave_nativa,
    v.estacion_id as codigo_estacion_nativo,
    e.estacion_sk,
    e.zona_id,
    v.linea,
    v.fecha_hora as fecha_hora_local,
    date(v.fecha_hora) as fecha,
    extract(hour from v.fecha_hora) as hora,
    v.tarifa as monto_q,
    v.tipo,
    v.tipo = 'TRANSBORDO' as es_transbordo_interno,
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
left join estaciones as e on e.codigo_nativo = v.estacion_id
