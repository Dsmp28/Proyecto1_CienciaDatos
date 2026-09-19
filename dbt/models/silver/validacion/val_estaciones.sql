-- Validación · catálogos de estaciones/paradas de los 4 modos unidos con columnas comunes. TODAS las filas de
-- stg_tm_estaciones, stg_tu_paradas, stg_mr_estaciones y stg_am_estaciones con `regla_id` (NULL = válida) y `motivo`.
-- Única regla aplicable: R05 (valor de zona/sector/district nulo o ausente en el seed zonas_mapeo). R06 no aplica
-- a un catálogo. Además la prueba singular assert_zonas_mapeadas pone la corrida en rojo si R05 ocurre.
with union_catalogos as (
    select
        'TM' as modo_id, estacion_id as codigo_nativo, nombre, linea as linea_ruta_eje, zona_origen,
        lat, lon, cast(null as float64) as km,
        fuente, archivo, objeto_gcs, ingest_date, registro_hash, n_repeticion, raw
    from {{ ref('stg_tm_estaciones') }}
    union all
    select
        'TU', cod_parada, descripcion, ruta, sector_origen,
        cast(null as float64), cast(null as float64), cast(null as float64),
        fuente, archivo, objeto_gcs, ingest_date, registro_hash, n_repeticion, raw
    from {{ ref('stg_tu_paradas') }}
    union all
    select
        'MR', cast(id_estacion as string), nombre_estacion, cast(null as string), zona_origen,
        cast(null as float64), cast(null as float64), km,
        fuente, archivo, objeto_gcs, ingest_date, registro_hash, n_repeticion, raw
    from {{ ref('stg_mr_estaciones') }}
    union all
    select
        'AM', station_code, station_name, axis, district_origen,
        cast(null as float64), cast(null as float64), cast(null as float64),
        fuente, archivo, objeto_gcs, ingest_date, registro_hash, n_repeticion, raw
    from {{ ref('stg_am_estaciones') }}
),
mapeo as (
    select valor_origen, zona_id from {{ ref('zonas_mapeo') }}
),
etiquetado as (
    select
        u.*,
        m.zona_id,
        case when m.zona_id is null then 'R05' end as regla_id
    from union_catalogos as u
    left join mapeo as m on m.valor_origen = u.zona_origen
)
select
    *,
    case regla_id when 'R05' then 'R05 zona sin mapear' end as motivo
from etiquetado
