-- H7 · Linaje de una cifra del tablero hasta los objetos crudos de GCS (restricción dura 4).
-- Cifra elegida: abordajes de Transmetro en la Zona 17 el 2026-06-01 (hoja H2 con filtros fecha = 2026-06-01,
-- modo = TM, zona = GT-Z17). Camino: gold.fct_abordaje (fuente_sk, kafka_offset, linea_num) → gold.dim_fuente
-- (fuente, archivo, objeto_gcs, ingest_date) → objeto jsonl en gs://…/bronze/<fuente>/ingest_date=…/ → tabla externa
-- Hive de Bronze con el mismo nombre que `fuente` (bronze.transmetro_validaciones) → archivo entregado por el operador
-- (`archivo` = transmetro_validaciones.csv, publicado a Kafka línea a línea).
-- Ejecutable tal cual en BigQuery:
--   bq query --use_legacy_sql=false --location=us-central1 < analysis/h7_linaje_de_una_cifra.sql
-- La suma de abordajes_de_la_cifra sobre todas las filas (cifra_total) es exactamente la cifra del tablero.
WITH cifra AS (
  SELECT
    fuente_sk,
    SUM(abordajes)       AS abordajes_de_la_cifra,   -- aditiva: se reparte entre objetos crudos sin pérdida
    MIN(kafka_offset)    AS kafka_offset_min,
    MAX(kafka_offset)    AS kafka_offset_max,
    MIN(linea_num)       AS linea_num_min,
    MAX(linea_num)       AS linea_num_max
  FROM `cienciadatos-509301.gold.fct_abordaje`
  WHERE fecha = DATE '2026-06-01' AND modo_id = 'TM' AND zona_id = 'GT-Z17'
  GROUP BY fuente_sk
)
SELECT
  SUM(c.abordajes_de_la_cifra) OVER () AS cifra_total,
  c.abordajes_de_la_cifra,
  f.fuente,                                -- = tabla externa de Bronze
  f.via,
  f.archivo,                               -- archivo crudo del operador
  f.objeto_gcs,                            -- objeto exacto en el lago (partición ingest_date=…)
  f.ingest_date,
  f.n_filas_silver,                        -- filas válidas que aportó ese objeto a Silver
  c.kafka_offset_min, c.kafka_offset_max,  -- rango de offsets de Kafka que contiene esos abordajes
  c.linea_num_min,    c.linea_num_max,     -- línea del archivo original publicado al tópico
  f.fuente_sk
FROM cifra AS c
JOIN `cienciadatos-509301.gold.dim_fuente` AS f USING (fuente_sk)
ORDER BY f.objeto_gcs;

-- Resultado (ejecutado el 2026-09-20 con bq query --use_legacy_sql=false --location=us-central1 --nouse_cache):
--   cifra_total = 725 abordajes (Transmetro, Zona 17, 2026-06-01), repartidos SIN pérdida en 2 objetos crudos de Bronze:
--     388 → gs://cienciadatos-509301-lake/bronze/transmetro_validaciones/ingest_date=2026-09-20/topico=transmetro.validaciones/particion=1/offsets=000000000000-000000004999.jsonl
--           (offsets de Kafka 3 … 4 985; líneas 4 … 4 986 de transmetro_validaciones.csv; el objeto aportó 4 980 filas a Silver)
--     337 → …/offsets=000000005000-000000009999.jsonl (offsets 5 013 … 9 292; líneas 5 014 … 9 293; 4 983 filas en Silver)
--   Camino: fct_abordaje.fuente_sk → dim_fuente (fuente = tabla externa bronze.transmetro_validaciones, archivo, objeto_gcs,
--   ingest_date) → objeto jsonl en GCS → línea del archivo del operador (linea_num). 388 + 337 = 725.
--   tiempo del job: 0,173 s (173 ms; 41 slot-ms; 4,2 MB procesados, gracias a la partición por fecha y el cluster por
--   modo/zona). Tiempo total con CLI (time): 1,42 s. Job: h7_linaje_de_una_cifra_1789968200 (ronda previa …_1789968114: 209 ms).
