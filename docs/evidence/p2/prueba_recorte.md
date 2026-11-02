# Prueba de recorte

Corte A (2026-07-01). `features.churn_features` (datos completos) vs `features_recorte.churn_features` (datos recortados a < t). Floats con tolerancia 1e-06; nulos iguales.

- Filas en completa: 51955; en recorte: 51955; comparadas (mismas unidades): 51955
- Unidades solo en completa: 0; solo en recorte: 0
- `EXCEPT DISTINCT` completa - recorte: 0 filas; recorte - completa: 0 filas
- Diferencias totales (celdas + unidades): 0

## Filas distintas por feature

| Feature | Filas distintas |
|---|---|
| fecha_corte | 0 |
| n_abordajes_28d | 0 |
| n_abordajes_14d | 0 |
| n_abordajes_7d | 0 |
| dias_activos_28d | 0 |
| dias_activos_7d | 0 |
| dias_desde_ultimo | 0 |
| dias_desde_primero_28d | 0 |
| semanas_activas_4 | 0 |
| ratio_ult14_prev14 | 0 |
| cv_semanal | 0 |
| n_modos_28d | 0 |
| share_tm | 0 |
| share_tu | 0 |
| share_mr | 0 |
| share_am | 0 |
| pct_hora_pico | 0 |
| pct_fin_semana | 0 |
| pct_feriado | 0 |
| gasto_q_28d | 0 |
| gasto_medio_q | 0 |
| n_estaciones_28d | 0 |
| n_zonas_28d | 0 |
| pct_transbordo_interno | 0 |
| n_tarjetas_activas_28d | 0 |
| hora_media | 0 |
| hora_sd | 0 |
| modo_principal | 0 |
| zona_principal | 0 |
| viajes_mr_completos_28d | 0 |
| duracion_media_mr_min | 0 |
| perfil_padron_a_t | 0 |
| tiene_padron_a_t | 0 |
| n_eventos_padron_28d | 0 |

**Resultado: SIN DIFERENCIAS**

## Features que fallaron antes de corregir

| Feature | Causa | Corrección |
|---|---|---|
| perfil_padron_final | Usaba silver_usuarios.perfil, el perfil del padrón después de TODO el log CDC; un cambio de perfil posterior al corte se filtraba a la feature. | Se usa el perfil del último evento del padrón con vigente_desde < t (perfil_padron_a_t, desde silver_padron_scd2). |
| estado_padron_final | Usaba silver_usuarios.estado_padron, el estado final del padrón: reflejaba altas, bajas e inactivaciones posteriores al corte. | Se retira de las features; el estado a t (estado_padron_ultimo_a_t) se calcula solo con eventos con vigente_desde < t y se usa únicamente para la población. |
| es_vigente_padron | es_vigente es verdadero cuando no existe un evento siguiente de la tarjeta; depende de eventos posteriores a t. | Se elimina la feature; se usan solo conteos de eventos con vigente_desde < t (n_eventos_padron_previos, n_eventos_padron_28d, tiene_padron_a_t) sin vigente_hasta ni es_vigente. |
| n_registros_operacion | Contaba las filas del catálogo del operador en todo el periodo (silver_usuarios.n_registros_operacion), incluidas las posteriores al corte. | Se elimina; la actividad se mide con conteos de abordajes de churn_eventos en el tramo ventana (fecha < t, máximo 28 días). |
| duracion_media_mr_min | No era fuga: AVG(duracion_s) en FLOAT suma en distinto orden en cada corrida y 4 personas caían justo en el empate del 6.º decimal (p. ej. 31.001562 vs 31.001563). | Media con suma entera exacta: SAFE_DIVIDE(SUM(duracion_s), COUNT(duracion_s) * 60). |
| hora_media | No era fuga: mismo efecto de AVG(hora) en FLOAT (2 filas en el 6.º decimal). | SAFE_DIVIDE(SUM(hora), COUNT(hora)); hora_sd con sumas enteras exactas (sqrt(E[x²] − E[x]²)) por la misma razón. |
