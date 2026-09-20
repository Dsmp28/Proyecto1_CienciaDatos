-- =====================================================================================================================
-- DDL real de la capa Gold · dataset `cienciadatos-509301.gold` (BigQuery, us-central1)
-- Exportado el 2026-09-20 tras `dbt build --select tag:gold` con:
--   SELECT table_name, ddl FROM `cienciadatos-509301.gold.INFORMATION_SCHEMA.TABLES` ORDER BY table_name;
-- Las tablas las crea dbt (materialized = table); este archivo es evidencia, no se ejecuta a mano.
-- Las descripciones OPTIONS(description=...) provienen de dbt/models/gold/schema.yml (persist_docs).
--
-- Particionado y clustering (config() en cada modelo de dbt/models/gold/):
--   fct_abordaje              PARTITION BY fecha (DATE, día)        CLUSTER BY modo_id, zona_id
--       El tablero filtra por rango de fechas y agrupa por modo y zona: la partición poda por día y el clustering
--       ordena físicamente los bloques por modo/zona dentro de cada partición (menos bytes leídos).
--   fct_viaje_metroriel       PARTITION BY fecha_entrada             CLUSTER BY zona_id_origen, zona_id_destino
--   fct_uso_usuario_dia       PARTITION BY fecha                     CLUSTER BY modo_id, usuario_unificado_sk
--       Snapshot diario: la partición por día hace barato "viajes del mes" (camino B) y el clustering por persona
--       acelera el agregado de transbordo.
--   agg_demanda_modo_zona_hora PARTITION BY fecha                    CLUSTER BY modo_id, zona_id
--   dim_usuario               sin partición (dimensión)              CLUSTER BY modo_id
--   dim_padron_historia       sin partición                          CLUSTER BY usuario_sk (historia por tarjeta)
--   fct_cambio_padron         sin partición (28 844 filas)           CLUSTER BY usuario_sk
--   agg_transbordo            sin partición                          CLUSTER BY n_modos
--   dim_tiempo, dim_modo, dim_zona, dim_estacion, dim_fuente, fct_cobertura_zona_modo, agg_cobertura_zona,
--   agg_transbordo_resumen, agg_metroriel_zonas: tablas pequeñas (≤ 1 080 filas), sin partición ni clustering.
-- Ninguna tabla usa partition_expiration: Gold se conserva indefinidamente (seguridad.md §4, ya no identifica personas).
-- Ninguna columna de llave nativa de usuario (llave_nativa, tarjeta, card, user_hash, usuario_base_id): verificado por
-- dbt/tests/gold/assert_gold_sin_llaves_nativas.sql sobre INFORMATION_SCHEMA.COLUMNS.
-- =====================================================================================================================

-- ---------------------------------------------------------------------------------------------------------------------
-- DIMENSIÓN · dim_tiempo
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.dim_tiempo`
(
  tiempo_sk INT64 OPTIONS(description="Llave sustituta INT64 = AAAAMMDD*100 + hora (2026060107 = 2026-06-01 07:00). Calculada: CAST(FORMAT_DATE('%Y%m%d', fecha) AS INT64)*100 + hora."),
  fecha DATE OPTIONS(description="Fecha calendario (DATE), generada con GENERATE_DATE_ARRAY entre el mínimo y el máximo observados en Silver."),
  hora INT64 OPTIONS(description="Hora del día 0–23 (INT64), generada con GENERATE_ARRAY(0, 23)."),
  fecha_hora_inicio DATETIME OPTIONS(description="DATETIME de inicio de la hora (fecha + hora:00:00); comodidad para ejes temporales en Tableau."),
  franja STRING OPTIONS(description="Franja del día según el seed franjas_horarias: madrugada, pico_manana, valle, pico_tarde, noche."),
  es_hora_pico BOOL OPTIONS(description="TRUE en 05–08 y 16–19 (seed franjas_horarias, definición oficial de la Agencia)."),
  dia_semana INT64 OPTIONS(description="Día de la semana ISO: 1 = lunes … 7 = domingo. Transformación de EXTRACT(DAYOFWEEK) de BigQuery (1 = domingo): MOD(DAYOFWEEK + 5, 7) + 1."),
  dia_semana_nombre STRING OPTIONS(description="Nombre del día en español (lunes … domingo)."),
  es_fin_de_semana BOOL OPTIONS(description="TRUE si dia_semana es 6 (sábado) o 7 (domingo)."),
  es_feriado BOOL OPTIONS(description="TRUE si la fecha está en el seed feriados_gt (Guatemala 2026)."),
  nombre_feriado STRING OPTIONS(description="Nombre del feriado (seed feriados_gt); NULL si no es feriado."),
  es_dia_habil BOOL OPTIONS(description="Definición oficial: lunes a viernes y no feriado (NOT es_fin_de_semana AND NOT es_feriado)."),
  semana_iso INT64 OPTIONS(description="Semana ISO 8601 del año (EXTRACT(ISOWEEK))."),
  mes INT64 OPTIONS(description="Mes 1–12 (EXTRACT(MONTH))."),
  anio_mes STRING OPTIONS(description="Año-mes 'AAAA-MM' (FORMAT_DATE('%Y-%m')); llave de agrupación para 'viajes del mes'."),
  anio INT64 OPTIONS(description="Año (EXTRACT(YEAR)).")
)
OPTIONS(
  description="Dimensión conformada de tiempo. Grano: una hora de un día. Rango derivado de los datos: desde el mínimo de silver_abordajes.fecha (y del padrón) hasta el máximo de abordajes, salida de MetroRiel y padrón, para que toda llave de los hechos exista. Hora pico y franja: seed franjas_horarias; feriados: seed feriados_gt. Dueño: Agencia · Planificación de operación.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- DIMENSIÓN · dim_modo
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.dim_modo`
(
  modo_id STRING OPTIONS(description="Llave natural del modo: TM, TU, MR, AM. Misma codificación que Silver."),
  nombre STRING OPTIONS(description="Nombre del operador: Transmetro, Transurbano, MetroRiel, Aerómetro."),
  tipo STRING OPTIONS(description="Tecnología: BRT, bus, tren ligero, teleférico."),
  via_ingesta STRING OPTIONS(description="Cómo llega la operación a Bronze: streaming (Kafka → GCS) o batch (archivo)."),
  fuente_operacion STRING OPTIONS(description="Nombre lógico de la fuente de operación del modo en Silver/dim_fuente (transmetro_validaciones, …)."),
  orden INT64 OPTIONS(description="Orden de presentación en el tablero (1–4).")
)
OPTIONS(
  description="Dimensión de modo/operador. Cuatro filas fijas definidas en el modelo (SELECT … UNNEST de STRUCTs, no seed): TM Transmetro (BRT, streaming), TU Transurbano (bus, batch), MR MetroRiel (tren ligero, batch), AM Aerómetro (teleférico, streaming). Dueño: Agencia · Arquitectura de datos.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- DIMENSIÓN · dim_zona
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.dim_zona`
(
  zona_id STRING OPTIONS(description="Llave natural conformada del seed zonas (GT-Z01 … GT-Z25, GT-MIXCO, …)."),
  zona_nombre STRING OPTIONS(description="Nombre canónico ('Zona 10', 'Mixco') del seed zonas."),
  tipo STRING OPTIONS(description="zona_ciudad o municipio (seed zonas)."),
  municipio STRING OPTIONS(description="Municipio al que pertenece (Guatemala para las zonas de la ciudad)."),
  presente_en_datos BOOL OPTIONS(description="Marca del seed: algún operador o el padrón menciona la zona."),
  orden INT64 OPTIONS(description="Orden de presentación (número de zona; municipios 101+)."),
  n_estaciones_total INT64 OPTIONS(description="Estaciones y paradas de todos los modos en la zona: COUNT(*) de silver_estaciones por zona_id; 0 si no hay."),
  n_modos_con_servicio INT64 OPTIONS(description="COUNT(DISTINCT modo_id) de silver_estaciones en la zona; 0 = zona sin servicio."),
  modos_con_servicio STRING OPTIONS(description="Modos con al menos una estación en la zona, STRING ordenado ('AM,MR,TM,TU'); NULL si ninguno."),
  tiene_servicio BOOL OPTIONS(description="TRUE si al menos un modo tiene una estación o parada en la zona.")
)
OPTIONS(
  description="Dimensión conformada de zona. Universo completo del seed zonas (26 filas: 22 zonas de la Ciudad de Guatemala y 4 municipios), incluidas las zonas sin datos, para que 'zona sin servicio' sea una fila. Atributos de cobertura calculados desde silver_estaciones. Dueño: Agencia · Planificación territorial.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- DIMENSIÓN · dim_estacion
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.dim_estacion`
(
  estacion_sk STRING OPTIONS(description="Llave sustituta determinista TO_HEX(SHA256(modo_id|codigo_nativo)) heredada de silver_estaciones (código público de infraestructura, no dato personal)."),
  modo_id STRING OPTIONS(description="Modo dueño de la estación (FK a dim_modo)."),
  codigo_nativo STRING OPTIONS(description="Código nativo del operador (TM: estacion_id; TU: cod_parada; MR: id_estacion; AM: station_code)."),
  nombre STRING OPTIONS(description="Nombre publicado por el operador."),
  linea_ruta_eje STRING OPTIONS(description="Línea (TM), ruta (TU) o eje (AM); NULL en MetroRiel (línea única)."),
  zona_id STRING OPTIONS(description="Zona conformada (FK a dim_zona), asignada en Silver por zonas_mapeo."),
  lat FLOAT64 OPTIONS(description="Latitud (solo Transmetro)."),
  lon FLOAT64 OPTIONS(description="Longitud (solo Transmetro)."),
  km FLOAT64 OPTIONS(description="Kilómetro sobre la línea (solo MetroRiel)."),
  archivo_origen STRING OPTIONS(description="Archivo crudo del catálogo del operador (linaje)."),
  fuente_sk STRING OPTIONS(description="FK a dim_fuente del catálogo crudo.")
)
OPTIONS(
  description="Dimensión de estación o parada de cualquier modo. Copia conformada de silver_estaciones (catálogos de los 4 operadores validados y con zona conformada por zonas_mapeo). Dueño: cada operador para su código; Agencia para la conformación.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- DIMENSIÓN · dim_usuario
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.dim_usuario`
(
  usuario_sk STRING OPTIONS(description="Seudónimo estable de la tarjeta: HMAC-SHA256(sal, modo_id|llave_nativa), 64 hex (silver_usuarios). Única llave de usuario en Gold."),
  usuario_unificado_sk STRING OPTIONS(description="Seudónimo de la persona: HMAC-SHA256(sal, 'BASE|' || usuario_base_id); NULL si la tarjeta no se pudo vincular (ADR-008)."),
  modo_id STRING OPTIONS(description="Modo emisor de la tarjeta (FK a dim_modo)."),
  metodo_vinculo STRING OPTIONS(description="Cómo se vinculó la tarjeta a la persona: formato (regex TC-/10 dígitos/MR) o inversion_md5 (Aerómetro); NULL sin vínculo."),
  tiene_vinculo BOOL OPTIONS(description="TRUE si usuario_unificado_sk no es nulo."),
  en_padron BOOL OPTIONS(description="TRUE si la persona tiene fila en el padrón aplicado de Transmetro (silver_usuarios)."),
  perfil STRING OPTIONS(description="Perfil vigente del padrón (silver_usuarios); NULL si no está en el padrón."),
  zona_residencia_id STRING OPTIONS(description="Zona de residencia conformada del padrón (FK a dim_zona); NULL si no está en el padrón."),
  estado_padron STRING OPTIONS(description="ACTIVA / INACTIVA según el padrón aplicado; SIN_PADRON si la persona no aparece en él."),
  n_abordajes_tarjeta INT64 OPTIONS(description="Abordajes válidos de esta tarjeta en silver_abordajes (COUNT por modo, llave)."),
  n_abordajes_persona INT64 OPTIONS(description="Abordajes válidos de la persona en todos sus modos (COUNT por usuario_unificado_sk)."),
  n_modos_usados INT64 OPTIONS(description="COUNT(DISTINCT modo_id) de silver_abordajes por usuario_unificado_sk (persona); 0 si nunca abordó."),
  es_multimodal BOOL OPTIONS(description="TRUE si n_modos_usados > 1 (la persona usa más de un sistema).")
)
CLUSTER BY modo_id
OPTIONS(
  description="Dimensión de usuario seudonimizado. Grano: una tarjeta por modo (ADR-008). Fuente: silver_usuarios SIN llave_nativa ni usuario_base_id (seguridad.md §2). usuario_sk = HMAC-SHA256(sal secreta, modo|llave) calculado en Silver (ADR-007); usuario_unificado_sk une las tarjetas de la misma persona. n_modos_usados y es_multimodal se calculan sobre silver_abordajes por persona. Agrupada (cluster) por modo_id.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- DIMENSIÓN · dim_padron_historia
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.dim_padron_historia`
(
  usuario_sk STRING OPTIONS(description="Seudónimo de la tarjeta (FK a dim_usuario)."),
  usuario_unificado_sk STRING OPTIONS(description="Seudónimo de la persona (dim_usuario)."),
  modo_id STRING OPTIONS(description="Modo del formato de la tarjeta del padrón (TM, TU, MR)."),
  version INT64 OPTIONS(description="Número de versión por tarjeta (ROW_NUMBER por seq en Silver)."),
  seq INT64 OPTIONS(description="Secuencia del log CDC que originó la versión; única en el log."),
  operacion STRING OPTIONS(description="Operación del log: INSERT, UPDATE, DELETE."),
  vigente_desde DATETIME OPTIONS(description="commit_ts de la operación (DATETIME)."),
  vigente_hasta DATETIME OPTIONS(description="commit_ts de la siguiente versión de la misma tarjeta (orden seq); NULL en la vigente."),
  es_vigente BOOL OPTIONS(description="TRUE en la última versión de cada tarjeta (una por tarjeta)."),
  estado STRING OPTIONS(description="INACTIVA si la operación fue DELETE; ACTIVA en caso contrario."),
  perfil STRING OPTIONS(description="Perfil vigente en esa versión (último no nulo hasta la operación)."),
  zona_residencia_id STRING OPTIONS(description="Zona de residencia conformada vigente en esa versión (FK a dim_zona)."),
  alta_implicita BOOL OPTIONS(description="TRUE en la primera versión de una tarjeta cuya primera operación no fue INSERT."),
  alta_repetida BOOL OPTIONS(description="TRUE en un INSERT sobre tarjeta ya existente (aplicado como UPDATE)."),
  baja_sin_alta_previa BOOL OPTIONS(description="TRUE en un DELETE sin INSERT anterior."),
  commit_ts_fuera_de_orden BOOL OPTIONS(description="TRUE cuando vigente_hasta < vigente_desde (hora aleatoria dentro del día en el generador); la vigencia sigue seq."),
  fuente_sk STRING OPTIONS(description="FK a dim_fuente del log CDC crudo.")
)
CLUSTER BY usuario_sk
OPTIONS(
  description="Historia SCD Tipo 2 del padrón de Transmetro, seudonimizada: una fila por versión de cada tarjeta, desde silver_padron_scd2 (ADR-009) unido a silver_usuarios por (modo, tarjeta) para sustituir la llave nativa por usuario_sk. Conserva las tarjetas dadas de baja (historizar, no borrar). Agrupada por usuario_sk.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- DIMENSIÓN · dim_fuente
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.dim_fuente`
(
  fuente_sk STRING OPTIONS(description="TO_HEX(SHA256(fuente|archivo|objeto_gcs|ingest_date)); la misma expresión se calcula en cada hecho."),
  fuente STRING OPTIONS(description="Nombre lógico de la fuente (igual a la tabla externa de Bronze): transmetro_validaciones, tu_paradas, …"),
  archivo STRING OPTIONS(description="Archivo crudo de origen tal como lo entregó el operador."),
  objeto_gcs STRING OPTIONS(description="Ruta gs:// del objeto en Bronze (partición ingest_date=…)."),
  ingest_date DATE OPTIONS(description="Fecha de ingesta a Bronze (partición Hive)."),
  via STRING OPTIONS(description="Vía de ingesta derivada del nombre de la fuente: streaming (TM, AM), cdc (padrón), batch (resto)."),
  tipo_contenido STRING OPTIONS(description="operacion (abordajes/viajes), catalogo (estaciones) o padron (CDC)."),
  modo_id STRING OPTIONS(description="Modo al que pertenece la fuente (el padrón es de Transmetro)."),
  n_filas_silver INT64 OPTIONS(description="Filas válidas en Silver provenientes de ese objeto (conteo de apoyo para conciliación).")
)
OPTIONS(
  description="Dimensión de linaje (restricción dura 4). Grano: un objeto crudo ingerido a Bronze (fuente, archivo, objeto_gcs, ingest_date) observado en silver_abordajes, silver_metroriel_viajes, silver_estaciones o silver_padron_scd2. En streaming un archivo lógico se reparte en varios objetos jsonl (lotes de offsets de Kafka).\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- HECHO · fct_abordaje
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.fct_abordaje`
(
  abordaje_sk STRING OPTIONS(description="Llave del abordaje = abordaje_id de Silver: modo|id nativo (TM validacion_id, MR trip_id, AM boarding_id, TU registro_hash|n_repeticion)."),
  tiempo_sk INT64 OPTIONS(description="FK a dim_tiempo: AAAAMMDD*100 + hora del instante local del abordaje."),
  fecha DATE OPTIONS(description="DATE(fecha_hora) local; columna de partición."),
  hora INT64 OPTIONS(description="Hora local 0–23 del abordaje."),
  modo_id STRING OPTIONS(description="FK a dim_modo (TM, TU, MR, AM)."),
  estacion_sk STRING OPTIONS(description="FK a dim_estacion (estación de entrada en MetroRiel)."),
  zona_id STRING OPTIONS(description="FK a dim_zona: zona conformada de la estación/parada."),
  usuario_sk STRING OPTIONS(description="FK a dim_usuario: HMAC-SHA256 de (modo|llave nativa) obtenido de silver_usuarios por (modo_id, llave_nativa). La llave nativa no se copia."),
  usuario_unificado_sk STRING OPTIONS(description="Seudónimo de la persona (dim_usuario.usuario_unificado_sk); permite contar transbordos entre modos."),
  fuente_sk STRING OPTIONS(description="FK a dim_fuente: hash de (fuente|archivo|objeto_gcs|ingest_date) de la fila Silver."),
  fecha_hora DATETIME OPTIONS(description="Instante local del abordaje (DATETIME America/Guatemala) = silver_abordajes.fecha_hora_local."),
  monto_q NUMERIC OPTIONS(description="Medida ADITIVA: monto cobrado en quetzales (NUMERIC); 0 es válido (adulto mayor, transbordo gratuito)."),
  abordajes INT64 OPTIONS(description="Medida ADITIVA: constante 1 (un abordaje = un viaje según definiciones_oficiales.md §1); SUM = viajes."),
  tipo_validacion STRING OPTIONS(description="Tipo nativo: TM ENTRADA/TRANSBORDO; TU OK; MR ENTRADA; AM BOARDING."),
  es_transbordo_interno BOOL OPTIONS(description="TRUE si es un TRANSBORDO de Transmetro (tarifa reducida dentro del mismo sistema)."),
  franja STRING OPTIONS(description="Franja horaria desnormalizada de dim_tiempo (para Tableau)."),
  es_hora_pico BOOL OPTIONS(description="Desnormalizado de dim_tiempo (05–08, 16–19)."),
  es_dia_habil BOOL OPTIONS(description="Desnormalizado de dim_tiempo (lunes–viernes no feriado)."),
  fuente STRING OPTIONS(description="Linaje: nombre lógico de la fuente de Bronze."),
  archivo STRING OPTIONS(description="Linaje: archivo crudo de origen."),
  objeto_gcs STRING OPTIONS(description="Linaje: objeto gs:// de Bronze."),
  ingest_date DATE OPTIONS(description="Linaje: fecha de ingesta a Bronze."),
  linea_num INT64 OPTIONS(description="Linaje streaming (TM, AM): número de línea en el archivo publicado a Kafka; NULL en batch."),
  kafka_offset INT64 OPTIONS(description="Linaje streaming (TM, AM): offset de Kafka; NULL en batch.")
)
PARTITION BY fecha
CLUSTER BY modo_id, zona_id
OPTIONS(
  description="Hecho principal (ADR-004). Grano: una validación de una tarjeta de un usuario en un modo, en una estación o parada, en un instante. Una fila por fila de silver_abordajes (Transmetro válidas, Transurbano cobros exitosos, entrada de cada viaje cerrado de MetroRiel, Aerómetro válidos), con usuario_sk/usuario_unificado_sk de silver_usuarios en lugar de la llave nativa. Particionada por fecha; cluster por modo_id, zona_id.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- HECHO · fct_viaje_metroriel
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.fct_viaje_metroriel`
(
  trip_id INT64 OPTIONS(description="Id del viaje del operador (silver_metroriel_viajes.trip_id)."),
  abordaje_sk STRING OPTIONS(description="'MR|' || trip_id: llave del abordaje correspondiente en fct_abordaje (drill-across)."),
  modo_id STRING OPTIONS(description="Siempre MR (FK a dim_modo)."),
  tiempo_sk_entrada INT64 OPTIONS(description="FK a dim_tiempo de la hora de entrada (role-playing)."),
  tiempo_sk_salida INT64 OPTIONS(description="FK a dim_tiempo de la hora de salida (role-playing), desde fecha_hora_salida_local."),
  fecha_entrada DATE OPTIONS(description="DATE de la entrada; columna de partición."),
  fecha_salida DATE OPTIONS(description="DATE de la salida."),
  hora_entrada INT64 OPTIONS(description="Hora local 0–23 de la entrada."),
  estacion_sk_origen STRING OPTIONS(description="FK a dim_estacion de la estación de entrada."),
  estacion_sk_destino STRING OPTIONS(description="FK a dim_estacion de la estación de salida."),
  zona_id_origen STRING OPTIONS(description="FK a dim_zona de la estación de entrada."),
  zona_id_destino STRING OPTIONS(description="FK a dim_zona de la estación de salida."),
  cambia_de_zona BOOL OPTIONS(description="TRUE si zona de origen ≠ zona de destino."),
  usuario_sk STRING OPTIONS(description="FK a dim_usuario (HMAC de MR|card, desde silver_usuarios)."),
  usuario_unificado_sk STRING OPTIONS(description="Seudónimo de la persona."),
  fuente_sk STRING OPTIONS(description="FK a dim_fuente (archivo metroriel_viajes)."),
  fecha_hora_entrada DATETIME OPTIONS(description="DATETIME local de entrada (entry_ts)."),
  fecha_hora_salida DATETIME OPTIONS(description="DATETIME local de salida (exit_ts)."),
  monto_q NUMERIC OPTIONS(description="Medida ADITIVA: tarifa en quetzales (fare_gtq)."),
  duracion_s INT64 OPTIONS(description="Medida ADITIVA: duración del viaje en segundos (duration_s del operador); útil como total de tiempo a bordo."),
  duracion_min FLOAT64 OPTIONS(description="Medida ADITIVA: duracion_s / 60 redondeado a 2 decimales. El promedio (no aditivo) se recalcula como SUM(duracion_min)/SUM(viajes)."),
  viajes INT64 OPTIONS(description="Medida ADITIVA: constante 1."),
  franja STRING OPTIONS(description="Franja de la hora de entrada (dim_tiempo)."),
  es_hora_pico BOOL OPTIONS(description="Desnormalizado de dim_tiempo para la hora de entrada."),
  es_dia_habil BOOL OPTIONS(description="Desnormalizado de dim_tiempo para la fecha de entrada."),
  fuente STRING OPTIONS(description="Linaje: fuente lógica (metroriel_viajes)."),
  archivo STRING OPTIONS(description="Linaje: archivo crudo."),
  objeto_gcs STRING OPTIONS(description="Linaje: objeto gs:// de Bronze."),
  ingest_date DATE OPTIONS(description="Linaje: fecha de ingesta.")
)
PARTITION BY fecha_entrada
CLUSTER BY zona_id_origen, zona_id_destino
OPTIONS(
  description="Hecho de viaje cerrado de MetroRiel (grano: un viaje con entrada y salida), desde silver_metroriel_viajes con usuario seudonimizado. Conserva origen–destino real; su entrada también está en fct_abordaje (abordaje_sk 'MR|trip_id'). Particionado por fecha_entrada; cluster por zona de origen y destino.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- HECHO · fct_uso_usuario_dia
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.fct_uso_usuario_dia`
(
  usuario_sk STRING OPTIONS(description="FK a dim_usuario (tarjeta seudonimizada)."),
  usuario_unificado_sk STRING OPTIONS(description="Seudónimo de la persona (agrupa las tarjetas de la misma persona entre modos)."),
  fecha DATE OPTIONS(description="Día del snapshot; columna de partición."),
  tiempo_sk_dia INT64 OPTIONS(description="AAAAMMDD*100: tiempo_sk de la hora 0 del día (FK a dim_tiempo a nivel día)."),
  modo_id STRING OPTIONS(description="FK a dim_modo."),
  abordajes INT64 OPTIONS(description="Medida ADITIVA: COUNT de abordajes válidos de la tarjeta ese día en ese modo."),
  monto_q NUMERIC OPTIONS(description="Medida ADITIVA: SUM(monto_q) del día."),
  abordajes_hora_pico INT64 OPTIONS(description="Medida ADITIVA: COUNTIF(es_hora_pico) según dim_tiempo."),
  estaciones_distintas INT64 OPTIONS(description="Medida NO ADITIVA: COUNT(DISTINCT estacion_sk) del día."),
  zona_id_mas_frecuente STRING OPTIONS(description="FK a dim_zona: zona con más abordajes de la tarjeta ese día (empate → menor zona_id)."),
  primera_hora INT64 OPTIONS(description="MIN(hora) del día (0–23)."),
  ultima_hora INT64 OPTIONS(description="MAX(hora) del día (0–23)."),
  es_dia_habil BOOL OPTIONS(description="Desnormalizado de dim_tiempo.")
)
PARTITION BY fecha
CLUSTER BY modo_id, usuario_unificado_sk
OPTIONS(
  description="Snapshot periódico: una fila por tarjeta seudonimizada × fecha × modo, calculada directamente desde silver_abordajes + silver_usuarios + dim_tiempo (camino independiente de fct_abordaje para la prueba de fuego 'viajes del mes'). Base de la pregunta de transbordo. Particionada por fecha; cluster por modo y persona.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- HECHO · fct_cobertura_zona_modo
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.fct_cobertura_zona_modo`
(
  zona_id STRING OPTIONS(description="FK a dim_zona."),
  modo_id STRING OPTIONS(description="FK a dim_modo."),
  n_estaciones INT64 OPTIONS(description="Conteo de apoyo (ADITIVO entre zonas y modos): estaciones/paradas del modo en la zona."),
  n_lineas_rutas INT64 OPTIONS(description="COUNT(DISTINCT linea_ruta_eje) del modo en la zona."),
  fuente_sk STRING OPTIONS(description="FK a dim_fuente del catálogo crudo del operador."),
  tiene_servicio BOOL OPTIONS(description="Constante TRUE: la existencia de la fila es el hecho (factless).")
)
OPTIONS(
  description="Hecho sin medidas (factless): una fila por (zona, modo) con al menos una estación o parada en silver_estaciones. Cobertura del tablero: dim_zona LEFT JOIN este hecho; zona sin fila = sin servicio.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- HECHO · fct_cambio_padron
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.fct_cambio_padron`
(
  seq INT64 OPTIONS(description="Secuencia del log CDC (orden de aplicación); llave del hecho."),
  tiempo_sk INT64 OPTIONS(description="FK a dim_tiempo: AAAAMMDD*100 + hora de commit_ts."),
  fecha DATE OPTIONS(description="DATE(commit_ts)."),
  fecha_hora DATETIME OPTIONS(description="commit_ts de la operación (DATETIME)."),
  usuario_sk STRING OPTIONS(description="FK a dim_usuario (tarjeta seudonimizada)."),
  usuario_unificado_sk STRING OPTIONS(description="Seudónimo de la persona."),
  modo_id STRING OPTIONS(description="Modo del formato de la tarjeta (TM, TU, MR); FK a dim_modo."),
  version INT64 OPTIONS(description="Versión SCD2 que produce la operación (dim_padron_historia.version)."),
  operacion STRING OPTIONS(description="INSERT, UPDATE o DELETE."),
  estado_resultante STRING OPTIONS(description="Estado de la tarjeta tras la operación: INACTIVA si DELETE, ACTIVA en otro caso."),
  estado_previo STRING OPTIONS(description="Estado de la versión anterior de la misma tarjeta (LAG por seq); NULL si la tarjeta no existía."),
  perfil STRING OPTIONS(description="Perfil vigente tras la operación."),
  zona_residencia_id STRING OPTIONS(description="Zona de residencia conformada tras la operación (FK a dim_zona)."),
  alta_implicita BOOL OPTIONS(description="TRUE si la primera operación de la tarjeta no fue INSERT."),
  alta_repetida BOOL OPTIONS(description="TRUE en un INSERT sobre tarjeta ya existente."),
  baja_sin_alta_previa BOOL OPTIONS(description="TRUE en un DELETE sin INSERT anterior."),
  operaciones INT64 OPTIONS(description="Medida ADITIVA: constante 1."),
  delta_activas INT64 OPTIONS(description="Medida ADITIVA (+1, −1, 0): cambio en el número de tarjetas activas que produce la operación."),
  tarjetas_activas_despues INT64 OPTIONS(description="Medida SEMI ADITIVA (saldo): tarjetas activas acumuladas tras esta operación (SUM(delta_activas) OVER (ORDER BY seq)). Se compara entre instantes; no se suma en el tiempo."),
  fuente_sk STRING OPTIONS(description="FK a dim_fuente del log CDC crudo.")
)
CLUSTER BY usuario_sk
OPTIONS(
  description="Hecho de transacción: una operación del log CDC aplicada al padrón (INSERT/UPDATE/DELETE), desde silver_padron_scd2 con usuario_sk de silver_usuarios. Regla de tarjetas_activas_despues: delta_activas = +1 si la operación deja ACTIVA una tarjeta antes INACTIVA o inexistente, −1 si deja INACTIVA una ACTIVA, 0 en otro caso; saldo = SUM(delta) acumulado por seq. Invariante: último saldo = tarjetas vigentes ACTIVA (assert_saldo_tarjetas_activas_igual_vigentes).\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- AGREGADO (Tableau) · agg_demanda_modo_zona_hora
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.agg_demanda_modo_zona_hora`
(
  tiempo_sk INT64 OPTIONS(description="FK a dim_tiempo."),
  fecha DATE OPTIONS(description="Fecha (partición)."),
  hora INT64 OPTIONS(description="Hora 0–23."),
  franja STRING OPTIONS(description="Franja de dim_tiempo."),
  es_hora_pico BOOL OPTIONS(description="De dim_tiempo."),
  es_dia_habil BOOL OPTIONS(description="De dim_tiempo."),
  dia_semana INT64 OPTIONS(description="1 = lunes … 7 = domingo."),
  dia_semana_nombre STRING OPTIONS(description="Nombre del día en español."),
  modo_id STRING OPTIONS(description="FK a dim_modo."),
  zona_id STRING OPTIONS(description="FK a dim_zona."),
  abordajes INT64 OPTIONS(description="Medida ADITIVA: SUM(abordajes)."),
  monto_q NUMERIC OPTIONS(description="Medida ADITIVA: SUM(monto_q)."),
  usuarios_distintos INT64 OPTIONS(description="Medida NO ADITIVA: COUNT(DISTINCT usuario_sk) en la celda; no se suma entre horas, zonas ni modos."),
  estaciones_con_demanda INT64 OPTIONS(description="Medida NO ADITIVA: COUNT(DISTINCT estacion_sk) en la celda.")
)
PARTITION BY fecha
CLUSTER BY modo_id, zona_id
OPTIONS(
  description="Agregado para Tableau (demanda por modo, zona y hora): fct_abordaje × dim_tiempo agrupado por fecha, hora, modo y zona. Particionado por fecha; cluster por modo y zona.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- AGREGADO (Tableau) · agg_cobertura_zona
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.agg_cobertura_zona`
(
  zona_id STRING OPTIONS(description="FK a dim_zona."),
  zona_nombre STRING OPTIONS(description="Nombre canónico."),
  tipo STRING OPTIONS(description="zona_ciudad o municipio."),
  municipio STRING OPTIONS(description="Municipio."),
  orden INT64 OPTIONS(description="Orden de presentación."),
  n_modos_con_servicio INT64 OPTIONS(description="Filas de fct_cobertura_zona_modo en la zona (0–4)."),
  n_estaciones INT64 OPTIONS(description="SUM(n_estaciones) de fct_cobertura_zona_modo."),
  modos_con_servicio STRING OPTIONS(description="Modos con estación en la zona, STRING ordenado."),
  abordajes_totales INT64 OPTIONS(description="Medida ADITIVA: SUM(abordajes) de fct_abordaje en la zona."),
  monto_q_total NUMERIC OPTIONS(description="Medida ADITIVA: SUM(monto_q)."),
  usuarios_distintos INT64 OPTIONS(description="Medida NO ADITIVA: COUNT(DISTINCT usuario_sk) en la zona."),
  n_modos_con_demanda INT64 OPTIONS(description="COUNT(DISTINCT modo_id) con abordajes en la zona."),
  tiene_servicio BOOL OPTIONS(description="TRUE si hay al menos una fila en fct_cobertura_zona_modo."),
  sin_servicio BOOL OPTIONS(description="TRUE si ningún modo tiene estación ni parada en la zona (respuesta directa a la pregunta 2)."),
  tiene_estacion_sin_demanda BOOL OPTIONS(description="TRUE si hay oferta (estaciones) pero ningún abordaje.")
)
OPTIONS(
  description="Agregado para Tableau (cobertura): una fila por zona de dim_zona con oferta (fct_cobertura_zona_modo) y demanda (fct_abordaje). sin_servicio = ninguna estación ni parada de ningún modo.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- AGREGADO (Tableau) · agg_transbordo
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.agg_transbordo`
(
  usuario_unificado_sk STRING OPTIONS(description="Seudónimo de la persona (ADR-008)."),
  n_modos INT64 OPTIONS(description="Medida NO ADITIVA: COUNT(DISTINCT modo_id) de la persona (1–4)."),
  modos STRING OPTIONS(description="Modos usados, STRING ordenado (p. ej. 'MR,TM')."),
  abordajes INT64 OPTIONS(description="Medida ADITIVA: SUM(abordajes)."),
  monto_q NUMERIC OPTIONS(description="Medida ADITIVA: SUM(monto_q)."),
  dias_activos INT64 OPTIONS(description="COUNT(DISTINCT fecha) con al menos un abordaje."),
  dias_tm INT64 OPTIONS(description="Días con abordajes en Transmetro."),
  dias_tu INT64 OPTIONS(description="Días con abordajes en Transurbano."),
  dias_mr INT64 OPTIONS(description="Días con abordajes en MetroRiel."),
  dias_am INT64 OPTIONS(description="Días con abordajes en Aerómetro."),
  es_multimodal BOOL OPTIONS(description="TRUE si n_modos > 1.")
)
CLUSTER BY n_modos
OPTIONS(
  description="Agregado para Tableau (transbordo): una fila por persona seudonimizada (usuario_unificado_sk) desde fct_uso_usuario_dia, con número de modos usados, combinación de modos y abordajes.\n"
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- AGREGADO (Tableau) · agg_transbordo_resumen
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.agg_transbordo_resumen`
(
  n_modos INT64 OPTIONS(description="Número de modos usados por la persona (1–4)."),
  es_multimodal BOOL OPTIONS(description="n_modos > 1."),
  usuarios INT64 OPTIONS(description="Personas con ese número de modos."),
  pct_usuarios FLOAT64 OPTIONS(description="Medida NO ADITIVA: usuarios / total de personas × 100."),
  abordajes INT64 OPTIONS(description="Medida ADITIVA: abordajes de esas personas."),
  abordajes_por_usuario FLOAT64 OPTIONS(description="Medida NO ADITIVA: abordajes / usuarios."),
  combinacion_mas_frecuente STRING OPTIONS(description="Combinación de modos más común dentro del grupo."),
  usuarios_combinacion INT64 OPTIONS(description="Personas con esa combinación.")
)
OPTIONS(
  description="Resumen de agg_transbordo por número de modos: usuarios, porcentaje, abordajes y combinación más frecuente."
);;

-- ---------------------------------------------------------------------------------------------------------------------
-- AGREGADO (Tableau) · agg_metroriel_zonas
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE `cienciadatos-509301.gold.agg_metroriel_zonas`
(
  zona_id STRING OPTIONS(description="FK a dim_zona."),
  zona_nombre STRING OPTIONS(description="Nombre canónico."),
  tipo STRING OPTIONS(description="zona_ciudad o municipio."),
  orden INT64 OPTIONS(description="Orden de presentación."),
  es_zona_metroriel BOOL OPTIONS(description="TRUE para GT-Z12, GT-Z08, GT-Z01, GT-Z06, GT-Z17 (zonas de la línea de MetroRiel según el enunciado)."),
  n_estaciones_mr INT64 OPTIONS(description="Estaciones de MetroRiel en la zona (fct_cobertura_zona_modo)."),
  abordajes_tm INT64 OPTIONS(description="Medida ADITIVA: abordajes de Transmetro en la zona."),
  abordajes_tu INT64 OPTIONS(description="Medida ADITIVA: abordajes de Transurbano."),
  abordajes_mr INT64 OPTIONS(description="Medida ADITIVA: abordajes (entradas) de MetroRiel."),
  abordajes_am INT64 OPTIONS(description="Medida ADITIVA: abordajes de Aerómetro."),
  abordajes_totales INT64 OPTIONS(description="Medida ADITIVA: suma de los cuatro modos."),
  usuarios_distintos INT64 OPTIONS(description="Medida NO ADITIVA: COUNT(DISTINCT usuario_sk) en la zona."),
  personas_distintas INT64 OPTIONS(description="Medida NO ADITIVA: COUNT(DISTINCT usuario_unificado_sk) en la zona."),
  pct_metroriel FLOAT64 OPTIONS(description="Medida NO ADITIVA: abordajes_mr / abordajes_totales × 100."),
  ranking INT64 OPTIONS(description="RANK() por abordajes_totales descendente (1 = zona con más demanda; empates por orden).")
)
OPTIONS(
  description="Agregado para Tableau (caso MetroRiel): una fila por zona con abordajes por modo, totales, usuarios distintos y ranking; es_zona_metroriel marca las zonas 12, 8, 1, 6 y 17 del enunciado.\n"
);;

