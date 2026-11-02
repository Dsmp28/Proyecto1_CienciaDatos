# Diccionario de features de churn (`features.churn_dataset`)

Generado desde `features.churn_diccionario` (modelo `dbt/models/features/churn/churn_diccionario.sql`); la prueba
`assert_churn_diccionario_cubre_columnas` garantiza que cubre exactamente las columnas de `churn_dataset`. Toda ventana
mide como máximo 28 días (`ventana_max_dias`); "estado en t" significa el último valor conocido antes del corte, sin ventana.

| # | Columna | Tipo | Qué mide | Ventana | Tabla Silver | Fórmula |
|---:|---|---|---|---|---|---|
| 1 | `unidad_id` | STRING | Persona (usuario_unificado_sk = HMAC-SHA256 con sal secreta de BASE|usuario_base_id, ADR-008). Unidad de análisis; no es una tarjeta. | n/a | silver_usuarios | usuario_unificado_sk |
| 2 | `fecha_corte` | DATE | Corte t (00:00 local). Las features usan solo eventos con fecha < t; la etiqueta usa [t, t+horizonte). | n/a | var(fechas_corte) | DATE de var('fechas_corte') |
| 3 | `corte` | STRING | Letra del corte: A, B o C según la posición en var(fechas_corte). | n/a | var(fechas_corte) | CHR(65 + posición) |
| 4 | `n_abordajes_28d` | INT64 | Abordajes válidos de la persona (todos los modos) en la ventana de 28 días. Siempre >= 2 en el dataset. | 28 d | silver_abordajes | COUNT(*) |
| 5 | `n_abordajes_14d` | INT64 | Abordajes válidos en los 14 días anteriores a t. | 14 d | silver_abordajes | COUNTIF(dias_antes_corte <= 14) |
| 6 | `n_abordajes_7d` | INT64 | Abordajes válidos en los 7 días anteriores a t. | 7 d | silver_abordajes | COUNTIF(dias_antes_corte <= 7) |
| 7 | `dias_activos_28d` | INT64 | Días distintos con al menos un abordaje. | 28 d | silver_abordajes | COUNT(DISTINCT fecha) |
| 8 | `dias_activos_7d` | INT64 | Días distintos con al menos un abordaje en los últimos 7 días (0 si no viajó). | 7 d | silver_abordajes | COUNT(DISTINCT fecha) con dias_antes_corte <= 7 |
| 9 | `dias_desde_ultimo` | INT64 | Días entre el último abordaje y t (recencia). Entre 1 y 28 por construcción. | 28 d | silver_abordajes | MIN(dias_antes_corte) |
| 10 | `dias_desde_primero_28d` | INT64 | Días entre el primer abordaje de la ventana y t. | 28 d | silver_abordajes | MAX(dias_antes_corte) |
| 11 | `semanas_activas_4` | INT64 | Semanas (bloques de 7 días hacia atrás desde t) con al menos un abordaje, de 4 posibles. | 28 d | silver_abordajes | COUNT(DISTINCT DIV(dias_antes_corte - 1, 7)) |
| 12 | `ratio_ult14_prev14` | FLOAT64 | Abordajes de los últimos 14 días entre los de los 14 previos; NULL si no hubo abordajes en los 14 previos. | 28 d (14 + 14) | silver_abordajes | SAFE_DIVIDE(n_abordajes_14d, n_abordajes_28d - n_abordajes_14d) |
| 13 | `cv_semanal` | FLOAT64 | Coeficiente de variación de los abordajes por semana (4 semanas, incluidas las de cero). | 28 d | silver_abordajes | STDDEV_POP(n_sem0..3) / AVG(n_sem0..3) |
| 14 | `n_modos_28d` | INT64 | Modos distintos usados (1 a 4). | 28 d | silver_abordajes | COUNT(DISTINCT modo_id) |
| 15 | `share_tm` | FLOAT64 | Proporción de abordajes en Transmetro (0 a 1). | 28 d | silver_abordajes | COUNTIF(modo_id = 'TM') / COUNT(*) |
| 16 | `share_tu` | FLOAT64 | Proporción de abordajes en Transurbano (0 a 1). | 28 d | silver_abordajes | COUNTIF(modo_id = 'TU') / COUNT(*) |
| 17 | `share_mr` | FLOAT64 | Proporción de abordajes en MetroRiel (0 a 1). | 28 d | silver_abordajes | COUNTIF(modo_id = 'MR') / COUNT(*) |
| 18 | `share_am` | FLOAT64 | Proporción de abordajes en Aerómetro (0 a 1). | 28 d | silver_abordajes | COUNTIF(modo_id = 'AM') / COUNT(*) |
| 19 | `pct_hora_pico` | FLOAT64 | Proporción de abordajes en hora pico oficial (seed franjas_horarias), 0 a 1. | 28 d | silver_abordajes + franjas_horarias | COUNTIF(es_hora_pico) / COUNT(*) |
| 20 | `pct_fin_semana` | FLOAT64 | Proporción de abordajes en sábado o domingo, 0 a 1. | 28 d | silver_abordajes | COUNTIF(DAYOFWEEK in (1, 7)) / COUNT(*) |
| 21 | `pct_feriado` | FLOAT64 | Proporción de abordajes en día feriado (seed feriados_gt), 0 a 1. | 28 d | silver_abordajes + feriados_gt | COUNTIF(fecha in feriados) / COUNT(*) |
| 22 | `gasto_q_28d` | FLOAT64 | Suma de tarifas pagadas en quetzales (0 es válido). | 28 d | silver_abordajes | SUM(monto_q) |
| 23 | `gasto_medio_q` | FLOAT64 | Tarifa media por abordaje en quetzales. | 28 d | silver_abordajes | AVG(monto_q) |
| 24 | `n_estaciones_28d` | INT64 | Estaciones o paradas distintas donde abordó. | 28 d | silver_abordajes | COUNT(DISTINCT estacion_sk) |
| 25 | `n_zonas_28d` | INT64 | Zonas conformadas distintas donde abordó. | 28 d | silver_abordajes | COUNT(DISTINCT zona_id) |
| 26 | `pct_transbordo_interno` | FLOAT64 | Proporción de abordajes que son transbordo interno de Transmetro, 0 a 1. | 28 d | silver_abordajes | COUNTIF(es_transbordo_interno) / COUNT(*) |
| 27 | `n_tarjetas_activas_28d` | INT64 | Tarjetas (modo + llave) distintas con abordajes en la ventana: la unidad es la persona, no la tarjeta. | 28 d | silver_abordajes | COUNT(DISTINCT tarjeta_sk) (seudónimo HMAC por modo y llave, de silver_usuarios.usuario_sk) |
| 28 | `hora_media` | FLOAT64 | Hora del día media de los abordajes (0 a 23). | 28 d | silver_abordajes | AVG(hora) |
| 29 | `hora_sd` | FLOAT64 | Desviación estándar poblacional de la hora de abordaje. | 28 d | silver_abordajes | STDDEV_POP(hora) |
| 30 | `modo_principal` | STRING | Modo con más abordajes (moda); desempate alfabético. | 28 d | silver_abordajes | ROW_NUMBER() por COUNT(*) DESC, modo_id |
| 31 | `zona_principal` | STRING | Zona conformada con más abordajes (moda); desempate alfabético; NULL si ninguna tiene zona. | 28 d | silver_abordajes | ROW_NUMBER() por COUNT(*) DESC, zona_id |
| 32 | `viajes_mr_completos_28d` | INT64 | Viajes de MetroRiel con entrada en la ventana y salida anterior a t (0 si no usa MetroRiel). | 28 d | silver_metroriel_viajes | COUNT(*) con fecha_hora_salida_local < t |
| 33 | `duracion_media_mr_min` | FLOAT64 | Duración media en minutos de esos viajes de MetroRiel; NULL si no hay. | 28 d | silver_metroriel_viajes | AVG(duracion_s) / 60 |
| 34 | `perfil_padron_a_t` | STRING | Perfil del último evento de padrón con vigente_desde < t (NULL si no hay o no trae perfil). | estado en t | silver_padron_scd2 | perfil del evento con seq máximo y vigente_desde < t |
| 35 | `tiene_padron_a_t` | BOOL | TRUE si la persona tiene algún evento de padrón con vigente_desde < t. | estado en t | silver_padron_scd2 | COUNT(*) > 0 con vigente_desde < t |
| 36 | `n_eventos_padron_28d` | INT64 | Eventos de padrón (altas, cambios) con vigente_desde en [t-28, t). | 28 d | silver_padron_scd2 | COUNTIF(vigente_desde >= t - 28 días) |
| 37 | `etiqueta` | INT64 | Churn: 1 si no hay ningún abordaje válido en ningún operador en [t, t+horizonte); 0 si hay; NULL si t+horizonte > fecha_referencia (corte C). | etiqueta: [t, t+30) | silver_abordajes | IF(COUNT(abordajes en [t, t+horizonte)) = 0, 1, 0) |
| 38 | `fecha_referencia` | DATE | Linaje: var(fecha_referencia) de la corrida que construyó la fila. | n/a | var(fecha_referencia) | DATE('2026-08-30') |
| 39 | `run_id` | STRING | Linaje: identificador de la corrida (var run_id). | n/a | var(run_id) | 'desde-cero-20261101T212525' |
