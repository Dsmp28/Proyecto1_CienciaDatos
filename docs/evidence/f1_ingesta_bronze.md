# Evidencia F1 — Ingesta a Bronze por las tres vías (2026-09-20)

Conciliación origen vs Bronze: `docs/evidence/conteos_bronze.md` (9 archivos, diferencia 0, 1 730 184 filas).

## Generar o verificar (en la VM, dentro del contenedor de Airflow)
```
archivo                       |      bytes |    filas | sha256       | verificado
aerometro_boardings.csv       |   12122578 |   203554 | 898b871c6b34 | sí
am_estaciones.csv             |        687 |       14 | e3acbeed8608 | sí
cdc_padron_usuarios.csv       |    2149136 |    31050 | 68e4d9dd2588 | sí
metroriel_viajes.jsonl        |   55311001 |   299100 | 23feb4a3a55c | sí
mr_estaciones.csv             |        537 |       22 | c302ffbc6f0b | sí
tm_estaciones.csv             |       7387 |      104 | 4d53a95abb4f | sí
transmetro_validaciones.csv   |   24042454 |   363221 | 5f88356e427d | sí
transurbano_transacciones.csv |   43125718 |   832791 | 8ce5028499b7 | sí
tu_paradas.csv                |      13189 |      328 | a888a09c4518 | sí
Todos los archivos verificados.   real 1m46s
```

## Batch + CDC (`ingest/batch_to_gcs.py --via todas`)
Corrida 1 (`manual-20260920T221154-400c84`): 7 archivos `completado`, md5 del blob = md5 local, 1 objeto por archivo.
Corrida 2 (`manual-20260920T221409-7ae8c6`): 7 archivos `omitido` (sha256 ya en `ops.ingest_manifest`), 0 bytes subidos.

## Streaming (Kafka en la VM → GCS)
Corrida 1 (`f1-streaming-20260921T042051`):
```
=== PRODUCTOR ===
archivo | filas publicadas | tópico | segundos | msgs/s
transmetro_validaciones.csv | 363221 | transmetro.validaciones (part. 1) | 5.76 | 63,084
aerometro_boardings.csv     | 203554 | aerometro.boardings (part. 1)     | 2.10 | 96,971
=== CONSUMIDOR ===
fin del bucle: idle (lag 0), 77.8 s
tópico | partición | offsets | mensajes | objetos | bytes
aerometro.boardings     | 1 | 0-203553 | 203554 | 41 |  72966490
transmetro.validaciones | 1 | 0-363220 | 363221 | 73 | 135692243
total: 566775 mensajes, 114 objetos
```
Nombres deterministas por ventana de offsets, p. ej.
`bronze/transmetro_validaciones/ingest_date=2026-09-20/topico=transmetro.validaciones/particion=1/offsets=000000170000-000000174999.jsonl`.

Corrida 2 (`f1-streaming-rerun`, mismos archivos):
```
=== PRODUCTOR 2 ===
omitido  transmetro_validaciones.csv: sha256=5f88356e427d… ya publicado (manifiesto)
omitido  aerometro_boardings.csv:     sha256=898b871c6b34… ya publicado (manifiesto)
=== CONSUMIDOR 2 ===
fin del bucle: idle (lag 0), 22.7 s
total: 0 mensajes, 0 objetos
```
Objetos de datos en `gs://cienciadatos-509301-lake/bronze/**` antes y después de la segunda corrida: **121** (7 batch/cdc + 114 streaming).

## Tablas externas de Bronze (`ingest/bronze_external_tables.py --verificar`)
9 tablas creadas en el dataset `bronze` (7 con columna `raw` sobre CSV/JSONL crudo, 2 con envolvente JSON de Kafka), partición Hive `ingest_date`; conteos idénticos a los archivos de origen. Nota: BigQuery no permite crear una tabla externa Hive sobre un prefijo vacío, por eso el DDL de las tablas de streaming se ejecuta después del consumidor (el DAG lo hace en ese orden).
