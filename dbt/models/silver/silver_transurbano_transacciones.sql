-- Silver · transacciones válidas de Transurbano (regla_id NULL en val_transurbano_transacciones), tipadas y
-- unificadas: fecha_hora_local DATETIME (fecha dd/mm/yyyy + hora unidas en staging), monto_q = monto_centavos / 100.
-- Conserva cod_estado, estado_desc y es_cobro_exitoso: los cobros fallidos (7, 9) son hechos reales y NO cuentan
-- como viaje; silver_abordajes toma solo es_cobro_exitoso. Sin id nativo: (registro_hash, n_repeticion) es la llave.
with validas as (
    select * from {{ ref('val_transurbano_transacciones') }}
    where regla_id is null
),
paradas as (
    select estacion_sk, codigo_nativo, zona_id
    from {{ ref('silver_estaciones') }}
    where modo_id = 'TU'
)
select
    concat(v.registro_hash, '|', cast(v.n_repeticion as string)) as transaccion_id,
    'TU' as modo_id,
    v.num_tarjeta as llave_nativa,
    v.cod_parada as codigo_estacion_nativo,
    p.estacion_sk,
    p.zona_id,
    v.ruta,
    v.fecha_hora as fecha_hora_local,
    date(v.fecha_hora) as fecha,
    extract(hour from v.fecha_hora) as hora,
    v.monto_centavos,
    cast(v.monto_centavos as numeric) / 100 as monto_q,
    v.cod_estado,
    v.estado_desc,
    v.es_cobro_exitoso,
    -- linaje
    v.fuente,
    v.archivo,
    v.objeto_gcs,
    v.ingest_date,
    v.registro_hash,
    v.n_repeticion
from validas as v
left join paradas as p on p.codigo_nativo = v.cod_parada
