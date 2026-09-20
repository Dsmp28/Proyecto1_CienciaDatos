# Reglas de calidad y cuarentena

> Documentadas **antes** de escribir el código de Silver (exigencia 3.1). Cada regla tiene un identificador
> estable que aparece en `quarantine.registros_rechazados.regla_id` y en el conteo por regla de `docs/METRICAS.md`.
> Principio (restricción dura 2): **ningún registro se descarta**; todo rechazo va a cuarentena con el registro
> original, la fuente, el archivo, el motivo, la regla y la marca de tiempo. Prueba de conciliación por fuente:
> `filas en staging = filas en silver + filas en cuarentena`.

## Qué es un registro inválido
Un registro de operación es inválido si no puede representar un abordaje verificable: no se sabe quién (llave nula),
dónde (estación/parada nula o desconocida), cuándo (fecha inválida o posterior a la fecha de referencia), o si es una
repetición exacta de otro registro ya aceptado. Los registros inválidos **no se corrigen ni se imputan**: se aíslan.

## Reglas por fuente

| Regla | Fuente(s) | Condición de rechazo | Motivo registrado | Origen del problema (generador) | Esperado (≈) |
|---|---|---|---|---|---|
| R01 · duplicado de torniquete | Transmetro | Misma `validacion_id` que otra fila ya aceptada (fila completa repetida). Se conserva la primera aparición por `linea_num`; el resto va a cuarentena | `R01 duplicado de torniquete` | ~0,3 % de lecturas duplicadas | 1 115 |
| R02 · parada nula | Transurbano | `cod_parada` vacío | `R02 codigo de parada nulo` | ~0,5 % sin código de parada | 4 189 |
| R03 · fecha del futuro | Todas las de operación | Fecha local del evento ≥ `fecha_referencia` (2026-07-16). Nunca `CURRENT_DATE` | `R03 fecha posterior a la fecha de referencia` | Transurbano: ~0,1 % con +400 días | 817 |
| R04 · viaje sin salida | MetroRiel | `exit` nulo (no se validó la salida) | `R04 viaje sin salida` | ~1,2 % de viajes sin salida | 3 589 |
| R05 · zona sin mapear | Catálogos y padrón | Valor de zona/sector/district ausente en el seed `zonas_mapeo` | `R05 zona sin mapear` | No inyectado; protege contra cambios futuros. Además, prueba de dbt que **falla** la corrida | 0 |
| R06 · estación desconocida | Todas las de operación | Código de estación/parada no presente en su catálogo | `R06 estacion o parada no catalogada` | No inyectado | 0 |
| R07 · llave nula | Todas + CDC | Llave de usuario vacía o marcador `SIN-TARJETA` | `R07 llave de usuario nula` | Padrón: `SIN-TARJETA` | 2 206 |
| R08 · fecha inválida | Todas | Fecha/hora no parseable con el formato declarado del operador | `R08 fecha no parseable` | No inyectado | 0 |
| R09 · monto inválido | Transmetro, Transurbano, MetroRiel, Aerómetro | Monto nulo o negativo (0 es válido: adulto mayor en Transmetro) | `R09 monto invalido` | No inyectado | 0 |
| R10 · duplicado de entrega | Transmetro, Aerómetro (streaming) | Misma `(archivo, sha256_archivo, linea_num)` entregada más de una vez por Kafka (republicación forzada o reentrega) | `R10 duplicado de entrega` | Solo si se republica el mismo archivo | 0 |
| R11 · operación CDC inaplicable | CDC | `op` fuera de {INSERT, UPDATE, DELETE} o `seq` nulo | `R11 operacion cdc invalida` | No inyectado | 0 |

Orden de evaluación: R07 → R08 → R03 → R06/R02 → R09 → R04 → R01/R10. Un registro se etiqueta con la **primera** regla
que incumple (una fila, un motivo), para que la suma por regla coincida con el total en cuarentena.

## Lo que NO es un registro inválido (se conserva en Silver)
- Transurbano `cod_estado` 7 (`SALDO_INSUF`) y 9 (`TARJETA_INVALIDA`): son cobros rechazados por el sistema, es decir,
  hechos reales de la operación. Van a `silver.transurbano_transacciones` con su estado y **no cuentan como viaje**
  (definición oficial). Se reportan aparte: 41 649 en staging (≈ 5 % de las transacciones), de los cuales 41 390 quedan en Silver
  (33 112 `SALDO_INSUF` + 8 278 `TARJETA_INVALIDA`) y 259 fueron a cuarentena antes por R02/R03.
- Transmetro `tipo = TRANSBORDO`: es un abordaje válido con tarifa de transbordo.
- Tarifa 0.00 (adulto mayor): válida.
- Padrón: INSERT repetido, UPDATE sin INSERT previo y DELETE sin INSERT previo se **aplican** según ADR-009 y se cuentan
  como anomalías del log, no como rechazos.

## Cuarentena
Tabla `quarantine.registros_rechazados` (reconstruida completa en cada corrida, idempotente):

| Columna | Contenido |
|---|---|
| `fuente` | fuente lógica (transmetro_validaciones, …) |
| `archivo` | archivo crudo de origen |
| `linea_num` / `offset` | posición en el archivo / en Kafka |
| `registro_original` | la línea tal como llegó (`raw`) |
| `regla_id`, `motivo` | R01…R11 y su descripción |
| `llave_usuario` | llave nativa, si existe (para auditoría) |
| `ingest_date`, `run_id`, `ts_cuarentena` | linaje y marca de tiempo |

## Reporte obligatorio (`docs/METRICAS.md`, categoría Calidad)
Registros en cuarentena por regla y por fuente, porcentaje del total de la fuente, duplicados detectados (R01 + R10),
y la conciliación por fuente (staging = silver + cuarentena).
