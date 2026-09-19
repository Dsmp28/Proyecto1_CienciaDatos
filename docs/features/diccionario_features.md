# Diccionario de `features.usuario_features`

Grano: una fila por persona (`usuario_unificado_sk`, ADR-008). Fecha de corte: `fecha_corte` = 2026-07-16 por defecto
(`var('fecha_corte')` → `var('fecha_referencia')`). "corte" en las ventanas es exclusivo: se usan abordajes con
`fecha < corte`. "historial" = todo lo observado antes del corte (2026-06-01 a 2026-07-15 en este lote). Un viaje es un
abordaje válido de `silver.silver_abordajes` (definición oficial 1). Misma información en la tabla
`features.diccionario_features` (prueba `assert_diccionario_cubre_columnas`).

| # | Columna | Tipo | Significado | Ventana | Fuente Silver | Fórmula |
|---|---|---|---|---|---|---|
| 1 | `usuario_unificado_sk` | STRING | Identidad unificada de la persona (HMAC-SHA256 con sal secreta de `BASE\|usuario_base_id`). Llave de la tabla. | n/a | `silver_usuarios` | `ANY_VALUE(usuario_unificado_sk)` por `usuario_base_id` |
| 2 | `fecha_corte` | DATE | Fecha de corte declarada; todas las features usan solo abordajes con `fecha < fecha_corte`. | n/a | `var('fecha_corte')` → `var('fecha_referencia')` | `DATE('2026-07-16')` |
| 3 | `viajes_7d` | INT64 | Viajes en los 7 días anteriores al corte. | [corte-7, corte) | `silver_abordajes` | `COUNTIF(fecha >= corte-7)` |
| 4 | `viajes_30d` | INT64 | Viajes en los 30 días anteriores al corte. | [corte-30, corte) | `silver_abordajes` | `COUNTIF(fecha >= corte-30)` |
| 5 | `viajes_90d` | INT64 | Viajes en los 90 días anteriores al corte. Los datos cubren 45 días: ventana truncada, coincide con `viajes_total`. | [corte-90, corte) truncada a 2026-06-01 | `silver_abordajes` | `COUNTIF(fecha >= corte-90)` |
| 6 | `viajes_total` | INT64 | Viajes en todo el historial observado antes del corte. | [2026-06-01, corte) | `silver_abordajes` | `COUNT(*)` |
| 7 | `viajes_30d_previos` | INT64 | Viajes en los días 31 a 60 antes del corte. Truncada: solo 15 días con datos. | [corte-60, corte-30) | `silver_abordajes` | `COUNTIF(corte-60 <= fecha < corte-30)` |
| 8 | `tendencia_30_vs_anterior` | INT64 | Cambio de actividad (positivo = usa más el sistema). Sesgada al alza por la ventana previa truncada. | [corte-60, corte) | `silver_abordajes` | `viajes_30d - viajes_30d_previos` |
| 9 | `dias_desde_ultimo_viaje` | INT64 | Recencia: días entre el último viaje y el corte. Siempre ≥ 1 (sin fuga). | historial | `silver_abordajes` | `DATE_DIFF(corte, MAX(fecha), DAY)` |
| 10 | `dias_desde_primer_viaje` | INT64 | Antigüedad observable: días entre el primer viaje observado y el corte (máximo 45). | historial | `silver_abordajes` | `DATE_DIFF(corte, MIN(fecha), DAY)` |
| 11 | `dias_activos` | INT64 | Días distintos con al menos un viaje. | historial | `silver_abordajes` | `COUNT(DISTINCT fecha)` |
| 12 | `modo_mas_usado` | STRING | Modo con más viajes (TM, TU, MR, AM); desempate alfabético. | historial | `silver_abordajes` | `ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC, modo_id) = 1` |
| 13 | `n_modos_distintos` | INT64 | Modos distintos usados (1 a 4). | historial | `silver_abordajes` | `COUNT(DISTINCT modo_id)` |
| 14 | `es_multimodal` | BOOL | TRUE si usa más de un modo. | historial | `silver_abordajes` | `n_modos_distintos > 1` |
| 15 | `viajes_por_modo_tm` | INT64 | Viajes en Transmetro. | historial | `silver_abordajes` | `COUNTIF(modo_id = 'TM')` |
| 16 | `viajes_por_modo_tu` | INT64 | Viajes en Transurbano (solo cobros exitosos). | historial | `silver_abordajes` | `COUNTIF(modo_id = 'TU')` |
| 17 | `viajes_por_modo_mr` | INT64 | Viajes en MetroRiel (entradas de viajes cerrados). | historial | `silver_abordajes` | `COUNTIF(modo_id = 'MR')` |
| 18 | `viajes_por_modo_am` | INT64 | Viajes en Aerómetro. | historial | `silver_abordajes` | `COUNTIF(modo_id = 'AM')` |
| 19 | `prop_hora_pico` | FLOAT64 | Proporción de viajes en hora pico oficial (05–08 y 16–19). Entre 0 y 1. | historial | `silver_abordajes` + seed `franjas_horarias` | `COUNTIF(es_hora_pico) / COUNT(*)` |
| 20 | `prop_dia_habil` | FLOAT64 | Proporción de viajes en día hábil (lunes a viernes no feriado). Entre 0 y 1. | historial | `silver_abordajes` + seed `feriados_gt` | `COUNTIF(DAYOFWEEK entre 2 y 6 AND no feriado) / COUNT(*)` |
| 21 | `prop_transbordo_interno` | FLOAT64 | Proporción de viajes que son transbordo interno de Transmetro. Entre 0 y 1. | historial | `silver_abordajes` | `COUNTIF(es_transbordo_interno) / COUNT(*)` |
| 22 | `hora_promedio` | FLOAT64 | Hora del día promedio de los viajes (0 a 23). | historial | `silver_abordajes` | `AVG(hora)` |
| 23 | `franja_mas_frecuente` | STRING | Franja con más viajes (madrugada, pico_manana, valle, pico_tarde, noche); desempate alfabético. | historial | `silver_abordajes` + seed `franjas_horarias` | `ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC, franja) = 1` |
| 24 | `zona_origen_mas_frecuente` | STRING | Zona conformada (`zona_id`) con más abordajes; desempate alfabético. | historial | `silver_abordajes` | `ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC, zona_id) = 1` |
| 25 | `n_zonas_distintas` | INT64 | Zonas conformadas distintas donde abordó. | historial | `silver_abordajes` | `COUNT(DISTINCT zona_id)` |
| 26 | `n_estaciones_distintas` | INT64 | Estaciones o paradas distintas donde abordó. | historial | `silver_abordajes` | `COUNT(DISTINCT estacion_sk)` |
| 27 | `gasto_acumulado_q` | NUMERIC | Suma de tarifas pagadas en quetzales (0 es válido: adulto mayor, transbordo gratuito). | historial | `silver_abordajes` | `SUM(monto_q)` |
| 28 | `gasto_promedio_viaje_q` | NUMERIC | Tarifa promedio por viaje en quetzales. | historial | `silver_abordajes` | `AVG(monto_q)` |
| 29 | `viajes_metroriel_completos` | INT64 | Viajes cerrados de MetroRiel con entrada y salida antes del corte (0 si no usa MetroRiel). | historial | `silver_metroriel_viajes` (+ `silver_usuarios` para la persona) | `COUNT(*)` con `fecha < corte AND DATE(fecha_hora_salida_local) < corte` |
| 30 | `duracion_promedio_metroriel_min` | FLOAT64 | Duración promedio de sus viajes de MetroRiel en minutos (NULL si no usa MetroRiel). | historial | `silver_metroriel_viajes` | `AVG(duracion_s) / 60` |
| 31 | `perfil_padron` | STRING | Perfil del padrón vigente a la fecha de corte (NULL si no está en el padrón). | as of corte | `silver_padron_scd2` | última versión por `seq` con `vigente_desde < corte` |
| 32 | `zona_residencia_id` | STRING | Zona de residencia conformada del padrón vigente a la fecha de corte (NULL si no está). | as of corte | `silver_padron_scd2` | última versión por `seq` con `vigente_desde < corte` |
| 33 | `estado_padron` | STRING | ACTIVA o INACTIVA según la versión del padrón vigente al corte; SIN_PADRON si la persona no aparece. | as of corte | `silver_padron_scd2` | `COALESCE(estado, 'SIN_PADRON')` |
| 34 | `es_usuario_activo_30d` | BOOL | Definición oficial 2: ≥ 1 viaje en los 30 días anteriores al corte y no dado de baja (INACTIVA) en el padrón a esa fecha. | [corte-30, corte) | `silver_abordajes` + `silver_padron_scd2` | `viajes_30d >= 1 AND estado_padron != 'INACTIVA'` |

## Columna objetivo (no incluida)
`abandono_30d = viajes en [corte, corte+30) = 0`, calculada aparte desde `silver_abordajes` con datos posteriores al
corte. Este lote termina el 2026-07-15, así que con el corte por defecto no existe; para entrenar se retrocede el corte
(`--vars '{"fecha_corte": "2026-06-16"}'`). Ver `docs/features/README.md`.
