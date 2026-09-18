# Métricas medidas

Todas las cifras de este documento son **medidas** (no estimadas) y provienen de `ops.ingest_manifest`,
`ops.run_metrics`, `quarantine.registros_rechazados` y las consultas de `analysis/`. Cada tabla indica la
corrida (`run_id`) y la fecha de medición. Categorías exigidas por el enunciado: Volumen, Calidad, CDC,
Rendimiento, Idempotencia y Cobertura.

## Volumen
### Filas de origen frente a filas en Bronze (1.1)
Medido el 2026-09-20 con `ingest/conteos_bronze.py` (COUNT(*) sobre las tablas externas de Bronze frente a `ops.ingest_manifest`).
Corridas: batch `manual-20260920T221154-400c84`, streaming `f1-streaming-20260921T042051`.

| archivo | vía | filas_origen | filas_bronze | diferencia | objetos en GCS |
|---|---|---:|---:|---:|---:|
| tm_estaciones.csv | batch | 104 | 104 | 0 | 1 |
| tu_paradas.csv | batch | 328 | 328 | 0 | 1 |
| mr_estaciones.csv | batch | 22 | 22 | 0 | 1 |
| am_estaciones.csv | batch | 14 | 14 | 0 | 1 |
| metroriel_viajes.jsonl | batch | 299 100 | 299 100 | 0 | 1 |
| transurbano_transacciones.csv | batch (ADR-003) | 832 791 | 832 791 | 0 | 1 |
| transmetro_validaciones.csv | streaming (Kafka) | 363 221 | 363 221 | 0 | 73 |
| aerometro_boardings.csv | streaming (Kafka) | 203 554 | 203 554 | 0 | 41 |
| cdc_padron_usuarios.csv | cdc | 31 050 | 31 050 | 0 | 1 |
| **Total** | | **1 730 184** | **1 730 184** | **0** | **121** |

Tamaño en Bronze: batch 137 MB (copia byte a byte); streaming 209 MB (72 966 490 + 135 692 243 bytes: cada línea viaja en una envolvente JSON con offset, archivo, línea y marcas de tiempo).

Rendimiento de la vía streaming en la VM (e2-standard-2, Kafka de un nodo): productor 363 221 msgs en 5,8 s (63 084 msg/s) y 203 554 en 2,1 s (96 971 msg/s); consumidor 566 775 mensajes → 114 objetos en 77,8 s. Regeneración y verificación de los 9 archivos en la VM: 1 min 46 s.

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
