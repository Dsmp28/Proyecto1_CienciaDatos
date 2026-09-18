-- Tablas externas de Bronze (una por fuente) sobre gs://{bucket}/bronze/<fuente>/ (ADR-002).
-- Plantilla: ingest/bronze_external_tables.py sustituye {project} y {bucket} y ejecuta cada sentencia.
-- Idempotente: CREATE OR REPLACE EXTERNAL TABLE. Particionado Hive por ingest_date (y tópico/partición en streaming).
--
-- Batch y CDC: una sola columna `raw STRING` con la línea tal como llegó. Se lee como CSV con
-- delimitador tabulador (no aparece en los datos) y quote='' (sin entrecomillado, verificado en la
-- doc oficial: "If your data does not contain quoted sections, set the property value to an empty
-- string"). skip_leading_rows se aplica por archivo: 1 en CSV (encabezado) y 0 en JSONL (no lo tiene).
-- Streaming: JSONL escrito por ingest/kafka_consumer_gcs.py con esquema explícito.

-- tm_estaciones (batch, csv) · archivo tm_estaciones.csv
CREATE OR REPLACE EXTERNAL TABLE `{project}.bronze.tm_estaciones` (
  raw STRING OPTIONS (description = 'Línea original del archivo, sin transformar')
)
WITH PARTITION COLUMNS (
  ingest_date DATE
)
OPTIONS (
  format = 'CSV',
  field_delimiter = '\t',
  quote = '',
  skip_leading_rows = 1,
  uris = ['gs://{bucket}/bronze/tm_estaciones/*'],
  hive_partition_uri_prefix = 'gs://{bucket}/bronze/tm_estaciones/',
  require_hive_partition_filter = false,
  description = 'Catálogo de estaciones de Transmetro (batch, CSV)'
);

-- tu_paradas (batch, csv) · archivo tu_paradas.csv
CREATE OR REPLACE EXTERNAL TABLE `{project}.bronze.tu_paradas` (
  raw STRING OPTIONS (description = 'Línea original del archivo, sin transformar')
)
WITH PARTITION COLUMNS (
  ingest_date DATE
)
OPTIONS (
  format = 'CSV',
  field_delimiter = '\t',
  quote = '',
  skip_leading_rows = 1,
  uris = ['gs://{bucket}/bronze/tu_paradas/*'],
  hive_partition_uri_prefix = 'gs://{bucket}/bronze/tu_paradas/',
  require_hive_partition_filter = false,
  description = 'Catálogo de paradas de Transurbano (batch, CSV)'
);

-- mr_estaciones (batch, csv) · archivo mr_estaciones.csv
CREATE OR REPLACE EXTERNAL TABLE `{project}.bronze.mr_estaciones` (
  raw STRING OPTIONS (description = 'Línea original del archivo, sin transformar')
)
WITH PARTITION COLUMNS (
  ingest_date DATE
)
OPTIONS (
  format = 'CSV',
  field_delimiter = '\t',
  quote = '',
  skip_leading_rows = 1,
  uris = ['gs://{bucket}/bronze/mr_estaciones/*'],
  hive_partition_uri_prefix = 'gs://{bucket}/bronze/mr_estaciones/',
  require_hive_partition_filter = false,
  description = 'Catálogo de estaciones de MetroRiel (batch, CSV)'
);

-- am_estaciones (batch, csv) · archivo am_estaciones.csv
CREATE OR REPLACE EXTERNAL TABLE `{project}.bronze.am_estaciones` (
  raw STRING OPTIONS (description = 'Línea original del archivo, sin transformar')
)
WITH PARTITION COLUMNS (
  ingest_date DATE
)
OPTIONS (
  format = 'CSV',
  field_delimiter = '\t',
  quote = '',
  skip_leading_rows = 1,
  uris = ['gs://{bucket}/bronze/am_estaciones/*'],
  hive_partition_uri_prefix = 'gs://{bucket}/bronze/am_estaciones/',
  require_hive_partition_filter = false,
  description = 'Catálogo de estaciones de Aerómetro (batch, CSV)'
);

-- metroriel_viajes (batch, jsonl) · archivo metroriel_viajes.jsonl
CREATE OR REPLACE EXTERNAL TABLE `{project}.bronze.metroriel_viajes` (
  raw STRING OPTIONS (description = 'Línea original del archivo, sin transformar')
)
WITH PARTITION COLUMNS (
  ingest_date DATE
)
OPTIONS (
  format = 'CSV',
  field_delimiter = '\t',
  quote = '',
  skip_leading_rows = 0,
  uris = ['gs://{bucket}/bronze/metroriel_viajes/*'],
  hive_partition_uri_prefix = 'gs://{bucket}/bronze/metroriel_viajes/',
  require_hive_partition_filter = false,
  description = 'Viajes cerrados de MetroRiel (batch, JSONL: cada fila raw es un documento JSON; Staging hace PARSE_JSON(raw))'
);

-- transurbano_transacciones (batch, csv) · archivo transurbano_transacciones.csv
CREATE OR REPLACE EXTERNAL TABLE `{project}.bronze.transurbano_transacciones` (
  raw STRING OPTIONS (description = 'Línea original del archivo, sin transformar')
)
WITH PARTITION COLUMNS (
  ingest_date DATE
)
OPTIONS (
  format = 'CSV',
  field_delimiter = '\t',
  quote = '',
  skip_leading_rows = 1,
  uris = ['gs://{bucket}/bronze/transurbano_transacciones/*'],
  hive_partition_uri_prefix = 'gs://{bucket}/bronze/transurbano_transacciones/',
  require_hive_partition_filter = false,
  description = 'Transacciones de Transurbano (batch, CSV)'
);

-- transmetro_validaciones (streaming, tópico transmetro.validaciones) · archivo de origen transmetro_validaciones.csv
CREATE OR REPLACE EXTERNAL TABLE `{project}.bronze.transmetro_validaciones` (
  offset INT64 OPTIONS (description = 'Offset del mensaje en la partición de Kafka'),
  kafka_ts STRING OPTIONS (description = 'Marca de tiempo del mensaje en Kafka (ISO UTC)'),
  clave STRING OPTIONS (description = 'Clave del mensaje'),
  archivo STRING OPTIONS (description = 'Archivo crudo del que salió la línea'),
  linea_num INT64 OPTIONS (description = 'Número de línea en el archivo de origen'),
  sha256_archivo STRING OPTIONS (description = 'sha256 del archivo de origen'),
  raw STRING OPTIONS (description = 'Línea CSV original, sin transformar'),
  ingest_ts STRING OPTIONS (description = 'Marca de tiempo de escritura en Bronze (ISO UTC)')
)
WITH PARTITION COLUMNS (
  ingest_date DATE,
  topico STRING,
  particion INT64
)
OPTIONS (
  format = 'NEWLINE_DELIMITED_JSON',
  uris = ['gs://{bucket}/bronze/transmetro_validaciones/*'],
  hive_partition_uri_prefix = 'gs://{bucket}/bronze/transmetro_validaciones/',
  require_hive_partition_filter = false,
  description = 'Validaciones de Transmetro recibidas por Kafka (streaming, JSONL con metadatos de entrega)'
);

-- aerometro_boardings (streaming, tópico aerometro.boardings) · archivo de origen aerometro_boardings.csv
CREATE OR REPLACE EXTERNAL TABLE `{project}.bronze.aerometro_boardings` (
  offset INT64 OPTIONS (description = 'Offset del mensaje en la partición de Kafka'),
  kafka_ts STRING OPTIONS (description = 'Marca de tiempo del mensaje en Kafka (ISO UTC)'),
  clave STRING OPTIONS (description = 'Clave del mensaje'),
  archivo STRING OPTIONS (description = 'Archivo crudo del que salió la línea'),
  linea_num INT64 OPTIONS (description = 'Número de línea en el archivo de origen'),
  sha256_archivo STRING OPTIONS (description = 'sha256 del archivo de origen'),
  raw STRING OPTIONS (description = 'Línea CSV original, sin transformar'),
  ingest_ts STRING OPTIONS (description = 'Marca de tiempo de escritura en Bronze (ISO UTC)')
)
WITH PARTITION COLUMNS (
  ingest_date DATE,
  topico STRING,
  particion INT64
)
OPTIONS (
  format = 'NEWLINE_DELIMITED_JSON',
  uris = ['gs://{bucket}/bronze/aerometro_boardings/*'],
  hive_partition_uri_prefix = 'gs://{bucket}/bronze/aerometro_boardings/',
  require_hive_partition_filter = false,
  description = 'Abordajes de Aerómetro recibidos por Kafka (streaming, JSONL con metadatos de entrega)'
);

-- cdc_padron_usuarios (cdc, csv) · archivo cdc_padron_usuarios.csv
CREATE OR REPLACE EXTERNAL TABLE `{project}.bronze.cdc_padron_usuarios` (
  raw STRING OPTIONS (description = 'Línea original del archivo, sin transformar')
)
WITH PARTITION COLUMNS (
  ingest_date DATE
)
OPTIONS (
  format = 'CSV',
  field_delimiter = '\t',
  quote = '',
  skip_leading_rows = 1,
  uris = ['gs://{bucket}/bronze/cdc_padron_usuarios/*'],
  hive_partition_uri_prefix = 'gs://{bucket}/bronze/cdc_padron_usuarios/',
  require_hive_partition_filter = false,
  description = 'Log de cambios (CDC) del padrón de usuarios de la agencia (CSV)'
);
