-- Features · diccionario de datos de usuario_features materializado en el warehouse (una fila por columna),
-- para que la definición de cada feature viva junto a la tabla y no solo en docs/features/diccionario_features.md.
-- Prueba singular assert_diccionario_cubre_columnas: toda columna de usuario_features está aquí y viceversa.
{{ config(materialized='table') }}

{% set fecha_corte = var('fecha_corte', var('fecha_referencia')) %}

{% set filas = [
  ('usuario_unificado_sk', 'STRING', 'Identidad unificada de la persona (HMAC-SHA256 con sal secreta de BASE|usuario_base_id, ADR-008). Llave de la tabla.', 'n/a', 'silver_usuarios', 'ANY_VALUE(usuario_unificado_sk) por usuario_base_id'),
  ('fecha_corte', 'DATE', 'Fecha de corte declarada; todas las features usan solo abordajes con fecha < fecha_corte.', 'n/a', 'var(fecha_corte) -> var(fecha_referencia)', "DATE('" ~ fecha_corte ~ "')"),
  ('viajes_7d', 'INT64', 'Viajes (abordajes válidos, definición oficial 1) en los 7 días anteriores al corte.', '[corte-7, corte)', 'silver_abordajes', 'COUNTIF(fecha >= corte-7)'),
  ('viajes_30d', 'INT64', 'Viajes en los 30 días anteriores al corte.', '[corte-30, corte)', 'silver_abordajes', 'COUNTIF(fecha >= corte-30)'),
  ('viajes_90d', 'INT64', 'Viajes en los 90 días anteriores al corte. Los datos cubren 45 días, por lo que la ventana queda truncada y coincide con viajes_total.', '[corte-90, corte) truncada a 2026-06-01', 'silver_abordajes', 'COUNTIF(fecha >= corte-90)'),
  ('viajes_total', 'INT64', 'Viajes en todo el historial observado antes del corte.', '[2026-06-01, corte)', 'silver_abordajes', 'COUNT(*)'),
  ('viajes_30d_previos', 'INT64', 'Viajes en los 30 días anteriores a la ventana de 30 días (días 31 a 60 antes del corte). Truncada: solo 15 días con datos.', '[corte-60, corte-30)', 'silver_abordajes', 'COUNTIF(corte-60 <= fecha < corte-30)'),
  ('tendencia_30_vs_anterior', 'INT64', 'Cambio de actividad: viajes_30d menos viajes_30d_previos (positivo = usa más el sistema). Sesgada al alza por la ventana previa truncada.', '[corte-60, corte)', 'silver_abordajes', 'viajes_30d - viajes_30d_previos'),
  ('dias_desde_ultimo_viaje', 'INT64', 'Días entre el último viaje y el corte (recencia). Siempre >= 1 por construcción (sin fuga).', 'historial', 'silver_abordajes', 'DATE_DIFF(corte, MAX(fecha), DAY)'),
  ('dias_desde_primer_viaje', 'INT64', 'Días entre el primer viaje observado y el corte (antigüedad observable, máximo 45).', 'historial', 'silver_abordajes', 'DATE_DIFF(corte, MIN(fecha), DAY)'),
  ('dias_activos', 'INT64', 'Días distintos con al menos un viaje.', 'historial', 'silver_abordajes', 'COUNT(DISTINCT fecha)'),
  ('modo_mas_usado', 'STRING', 'Modo con más viajes de la persona (TM, TU, MR, AM); desempate alfabético.', 'historial', 'silver_abordajes', 'ROW_NUMBER() por COUNT(*) DESC, modo_id'),
  ('n_modos_distintos', 'INT64', 'Cantidad de modos distintos usados (1 a 4).', 'historial', 'silver_abordajes', 'COUNT(DISTINCT modo_id)'),
  ('es_multimodal', 'BOOL', 'TRUE si usa más de un modo.', 'historial', 'silver_abordajes', 'n_modos_distintos > 1'),
  ('viajes_por_modo_tm', 'INT64', 'Viajes en Transmetro.', 'historial', 'silver_abordajes', "COUNTIF(modo_id = 'TM')"),
  ('viajes_por_modo_tu', 'INT64', 'Viajes en Transurbano (solo cobros exitosos).', 'historial', 'silver_abordajes', "COUNTIF(modo_id = 'TU')"),
  ('viajes_por_modo_mr', 'INT64', 'Viajes en MetroRiel (entradas de viajes cerrados).', 'historial', 'silver_abordajes', "COUNTIF(modo_id = 'MR')"),
  ('viajes_por_modo_am', 'INT64', 'Viajes en Aerómetro.', 'historial', 'silver_abordajes', "COUNTIF(modo_id = 'AM')"),
  ('prop_hora_pico', 'FLOAT64', 'Proporción de viajes en hora pico oficial (05-08 y 16-19, seed franjas_horarias). Entre 0 y 1.', 'historial', 'silver_abordajes + franjas_horarias', 'COUNTIF(es_hora_pico) / COUNT(*)'),
  ('prop_dia_habil', 'FLOAT64', 'Proporción de viajes en día hábil (lunes a viernes no feriado, seed feriados_gt). Entre 0 y 1.', 'historial', 'silver_abordajes + feriados_gt', 'COUNTIF(dow entre 2 y 6 y no feriado) / COUNT(*)'),
  ('prop_transbordo_interno', 'FLOAT64', 'Proporción de viajes que son transbordo interno de Transmetro. Entre 0 y 1.', 'historial', 'silver_abordajes', 'COUNTIF(es_transbordo_interno) / COUNT(*)'),
  ('hora_promedio', 'FLOAT64', 'Hora del día promedio de los viajes (0 a 23).', 'historial', 'silver_abordajes', 'AVG(hora)'),
  ('franja_mas_frecuente', 'STRING', 'Franja horaria con más viajes (madrugada, pico_manana, valle, pico_tarde, noche); desempate alfabético.', 'historial', 'silver_abordajes + franjas_horarias', 'ROW_NUMBER() por COUNT(*) DESC, franja'),
  ('zona_origen_mas_frecuente', 'STRING', 'Zona conformada (zona_id) con más abordajes; desempate alfabético.', 'historial', 'silver_abordajes', 'ROW_NUMBER() por COUNT(*) DESC, zona_id'),
  ('n_zonas_distintas', 'INT64', 'Zonas conformadas distintas donde abordó.', 'historial', 'silver_abordajes', 'COUNT(DISTINCT zona_id)'),
  ('n_estaciones_distintas', 'INT64', 'Estaciones o paradas distintas donde abordó.', 'historial', 'silver_abordajes', 'COUNT(DISTINCT estacion_sk)'),
  ('gasto_acumulado_q', 'NUMERIC', 'Suma de tarifas pagadas en quetzales (0 es válido: adulto mayor, transbordo gratuito).', 'historial', 'silver_abordajes', 'SUM(monto_q)'),
  ('gasto_promedio_viaje_q', 'NUMERIC', 'Tarifa promedio por viaje en quetzales.', 'historial', 'silver_abordajes', 'AVG(monto_q)'),
  ('viajes_metroriel_completos', 'INT64', 'Viajes cerrados de MetroRiel con entrada y salida antes del corte (0 si no usa MetroRiel).', 'historial', 'silver_metroriel_viajes', 'COUNT(*) con fecha < corte y DATE(salida) < corte'),
  ('duracion_promedio_metroriel_min', 'FLOAT64', 'Duración promedio de sus viajes de MetroRiel en minutos (NULL si no usa MetroRiel).', 'historial', 'silver_metroriel_viajes', 'AVG(duracion_s) / 60'),
  ('perfil_padron', 'STRING', 'Perfil del padrón vigente a la fecha de corte (NULL si no está en el padrón).', 'as of corte', 'silver_padron_scd2', 'última versión por seq con vigente_desde < corte'),
  ('zona_residencia_id', 'STRING', 'Zona de residencia conformada del padrón vigente a la fecha de corte (NULL si no está en el padrón).', 'as of corte', 'silver_padron_scd2', 'última versión por seq con vigente_desde < corte'),
  ('estado_padron', 'STRING', 'ACTIVA o INACTIVA según la versión del padrón vigente a la fecha de corte; SIN_PADRON si la persona no aparece.', 'as of corte', 'silver_padron_scd2', "COALESCE(estado, 'SIN_PADRON')"),
  ('es_usuario_activo_30d', 'BOOL', 'Definición oficial 2: >= 1 viaje en los 30 días anteriores al corte y no dado de baja (INACTIVA) en el padrón a esa fecha.', '[corte-30, corte)', 'silver_abordajes + silver_padron_scd2', "viajes_30d >= 1 AND estado_padron != 'INACTIVA'"),
] %}

{% for f in filas %}
select
    {{ loop.index }} as orden,
    '{{ f[0] }}' as columna,
    '{{ f[1] }}' as tipo,
    '{{ f[2] | replace("'", "\\'") }}' as descripcion,
    '{{ f[3] }}' as ventana,
    '{{ f[4] }}' as fuente_silver,
    '{{ f[5] | replace("'", "\\'") }}' as formula
{% if not loop.last %}union all{% endif %}
{% endfor %}
