-- Silver · viajes cerrados válidos de MetroRiel (regla_id NULL en val_metroriel_viajes: tienen entrada y salida).
-- Conserva entrada y salida con dimensiones role-playing (estacion_sk_origen/destino, zona_id_origen/destino) y
-- duracion_s; fecha_hora_local = entry_ts (la entrada es el abordaje, ADR-004), monto_q = fare_gtq.
with validas as (
    select * from {{ ref('val_metroriel_viajes') }}
    where regla_id is null
),
estaciones as (
    select estacion_sk, codigo_nativo, zona_id
    from {{ ref('silver_estaciones') }}
    where modo_id = 'MR'
)
select
    v.trip_id,
    'MR' as modo_id,
    v.card as llave_nativa,
    cast(v.entry_station as string) as codigo_estacion_nativo,
    cast(v.exit_station as string) as codigo_estacion_destino,
    eo.estacion_sk as estacion_sk_origen,
    ed.estacion_sk as estacion_sk_destino,
    eo.zona_id as zona_id_origen,
    ed.zona_id as zona_id_destino,
    v.entry_ts as fecha_hora_local,
    v.exit_ts as fecha_hora_salida_local,
    date(v.entry_ts) as fecha,
    extract(hour from v.entry_ts) as hora,
    v.duration_s as duracion_s,
    v.fare_gtq as monto_q,
    -- linaje
    v.fuente,
    v.archivo,
    v.objeto_gcs,
    v.ingest_date,
    v.registro_hash,
    v.n_repeticion
from validas as v
left join estaciones as eo on eo.codigo_nativo = cast(v.entry_station as string)
left join estaciones as ed on ed.codigo_nativo = cast(v.exit_station as string)
