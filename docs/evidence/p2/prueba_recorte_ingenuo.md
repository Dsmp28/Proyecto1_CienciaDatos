# Prueba de recorte (borrador ingenuo)

Corte A (2026-07-01). `features.churn_features_ingenuo` (datos completos) vs `features_recorte.churn_features_ingenuo` (datos recortados a < t). Floats con tolerancia 1e-06; nulos iguales.

- Filas en completa: 51955; en recorte: 51955; comparadas (mismas unidades): 51955
- Unidades solo en completa: 0; solo en recorte: 0
- `EXCEPT DISTINCT` completa - recorte: 49058 filas; recorte - completa: 49058 filas
- Diferencias totales (celdas + unidades): 90553

## Filas distintas por feature

| Feature | Filas distintas |
|---|---|
| fecha_corte | 0 |
| perfil_padron_final | 14467 |
| estado_padron_final | 15381 |
| es_vigente_padron | 13990 |
| duracion_media_mr_min_sin_filtro | 0 |
| n_registros_operacion | 46715 |
| n_abordajes_28d | 0 |
| dias_desde_ultimo | 0 |

**Resultado: HAY DIFERENCIAS**

## Features que fallaron antes de corregir

| Feature | Causa | Corrección |
|---|---|---|
| perfil_padron_final | Usaba silver_usuarios.perfil, el perfil del padrón después de TODO el log CDC; un cambio de perfil posterior al corte se filtraba a la feature. | Se usa el perfil del último evento del padrón con vigente_desde < t (perfil_padron_a_t, desde silver_padron_scd2). |
| estado_padron_final | Usaba silver_usuarios.estado_padron, el estado final del padrón: reflejaba altas, bajas e inactivaciones posteriores al corte. | Se retira de las features; el estado a t (estado_padron_ultimo_a_t) se calcula solo con eventos con vigente_desde < t y se usa únicamente para la población. |
| es_vigente_padron | es_vigente es verdadero cuando no existe un evento siguiente de la tarjeta; depende de eventos posteriores a t. | Se elimina la feature; se usan solo conteos de eventos con vigente_desde < t (n_eventos_padron_previos, n_eventos_padron_28d, tiene_padron_a_t) sin vigente_hasta ni es_vigente. |
| n_registros_operacion | Contaba las filas del catálogo del operador en todo el periodo (silver_usuarios.n_registros_operacion), incluidas las posteriores al corte. | Se elimina; la actividad se mide con conteos de abordajes de churn_eventos en el tramo ventana (fecha < t, máximo 28 días). |
