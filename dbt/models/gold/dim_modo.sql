-- Gold · dim_modo. Grano: un operador / modo de transporte. Cuatro filas fijas definidas por la Agencia
-- (Arquitectura de datos, definiciones_oficiales.md §3). No es un seed: es un catálogo estático del modelo.
-- via_ingesta documenta cómo llega la operación de cada modo a Bronze (streaming por Kafka o batch por archivo).
select modo_id, nombre, tipo, via_ingesta, fuente_operacion, orden
from unnest([
    struct('TM' as modo_id, 'Transmetro' as nombre, 'BRT' as tipo, 'streaming' as via_ingesta,
           'transmetro_validaciones' as fuente_operacion, 1 as orden),
    struct('TU', 'Transurbano', 'bus', 'batch', 'transurbano_transacciones', 2),
    struct('MR', 'MetroRiel', 'tren ligero', 'batch', 'metroriel_viajes', 3),
    struct('AM', 'Aerómetro', 'teleférico', 'streaming', 'aerometro_boardings', 4)
])
