# Métricas medidas

Todas las cifras de este documento son **medidas** (no estimadas) y provienen de `ops.ingest_manifest`,
`ops.run_metrics`, `quarantine.registros_rechazados` y las consultas de `analysis/`. Cada tabla indica la
corrida (`run_id`) y la fecha de medición. Categorías exigidas por el enunciado: Volumen, Calidad, CDC,
Rendimiento, Idempotencia y Cobertura.

## Volumen
### Filas de origen frente a filas en Bronze (1.1)
*Pendiente: se completa al cerrar F1 desde `docs/evidence/conteos_bronze.md`.*

### Filas por capa (Bronze → Staging → Silver → Gold)
*Pendiente (F3–F5).*

## Calidad
### Registros en cuarentena por regla y fuente
*Pendiente (F3). Reglas en `docs/governance/reglas_calidad.md`.*

## CDC
### Altas, cambios y bajas aplicadas; tarjetas activas antes y después de los DELETE
*Pendiente (F2).*

## Rendimiento
### Duración por etapa, tamaño en almacenamiento por capa, tiempo de las consultas del tablero
*Pendiente (F5, F6).*

## Idempotencia
### Conteos de la primera y la segunda corrida
*Pendiente (F5): `make demo-idempotencia`, evidencia en `docs/evidence/`.*

## Cobertura
### Zonas con y sin servicio; usuarios que usan más de un modo
*Pendiente (F4, F6).*
