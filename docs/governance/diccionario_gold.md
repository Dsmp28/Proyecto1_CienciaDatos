# Diccionario de datos · capa Gold

Generado por `scripts/exportar_diccionario.py` desde `dbt/target/manifest.json` (descripciones de
`dbt/models/gold/schema.yml`) y `dbt/target/catalog.json` (tipos reales de BigQuery). No editar a mano:
la fuente de verdad es el YAML, que también se persiste en BigQuery (`persist_docs`).

Convenciones: cada descripción indica significado, fuente y transformación. Las medidas están clasificadas
como **ADITIVA**, **SEMI ADITIVA** o **NO ADITIVA** (matriz del bus §4). Llaves: `*_sk` sustitutas,
`*_id` naturales conformadas. Ninguna tabla contiene la llave nativa del usuario (seguridad.md §2).

## Índice

- [`dim_estacion`](#dim_estacion)
- [`dim_fuente`](#dim_fuente)
- [`dim_modo`](#dim_modo)
- [`dim_padron_historia`](#dim_padron_historia)
- [`dim_tiempo`](#dim_tiempo)
- [`dim_usuario`](#dim_usuario)
- [`dim_zona`](#dim_zona)
- [`fct_abordaje`](#fct_abordaje)
- [`fct_cambio_padron`](#fct_cambio_padron)
- [`fct_cobertura_zona_modo`](#fct_cobertura_zona_modo)
- [`fct_uso_usuario_dia`](#fct_uso_usuario_dia)
- [`fct_viaje_metroriel`](#fct_viaje_metroriel)
- [`agg_cobertura_zona`](#agg_cobertura_zona)
- [`agg_demanda_modo_zona_hora`](#agg_demanda_modo_zona_hora)
- [`agg_metroriel_zonas`](#agg_metroriel_zonas)
- [`agg_transbordo`](#agg_transbordo)
- [`agg_transbordo_resumen`](#agg_transbordo_resumen)

## Dimensiones

### dim_estacion

Dimensión de estación o parada de cualquier modo. Copia conformada de silver_estaciones (catálogos de los 4 operadores validados y con zona conformada por zonas_mapeo). Dueño: cada operador para su código; Agencia para la conformación.

- **Tabla:** `gold.dim_estacion` · materialización `table`
- **Fuentes (`ref`):** `silver_estaciones`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `estacion_sk` | STRING | Llave sustituta determinista TO_HEX(SHA256(modo_id\|codigo_nativo)) heredada de silver_estaciones (código público de infraestructura, no dato personal). | unique, not_null |
| `modo_id` | STRING | Modo dueño de la estación (FK a dim_modo). | not_null, relationships→dim_modo |
| `codigo_nativo` | STRING | Código nativo del operador (TM: estacion_id; TU: cod_parada; MR: id_estacion; AM: station_code). | not_null |
| `nombre` | STRING | Nombre publicado por el operador. |  |
| `linea_ruta_eje` | STRING | Línea (TM), ruta (TU) o eje (AM); NULL en MetroRiel (línea única). |  |
| `zona_id` | STRING | Zona conformada (FK a dim_zona), asignada en Silver por zonas_mapeo. | not_null, relationships→dim_zona |
| `lat` | FLOAT64 | Latitud (solo Transmetro). |  |
| `lon` | FLOAT64 | Longitud (solo Transmetro). |  |
| `km` | FLOAT64 | Kilómetro sobre la línea (solo MetroRiel). |  |
| `archivo_origen` | STRING | Archivo crudo del catálogo del operador (linaje). | not_null |
| `fuente_sk` | STRING | FK a dim_fuente del catálogo crudo. | not_null, relationships→dim_fuente |

### dim_fuente

Dimensión de linaje (restricción dura 4). Grano: un objeto crudo ingerido a Bronze (fuente, archivo, objeto_gcs, ingest_date) observado en silver_abordajes, silver_metroriel_viajes, silver_estaciones o silver_padron_scd2. En streaming un archivo lógico se reparte en varios objetos jsonl (lotes de offsets de Kafka).

- **Tabla:** `gold.dim_fuente` · materialización `table`
- **Fuentes (`ref`):** `silver_abordajes`, `silver_estaciones`, `silver_metroriel_viajes`, `silver_padron_scd2`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `fuente_sk` | STRING | TO_HEX(SHA256(fuente\|archivo\|objeto_gcs\|ingest_date)); la misma expresión se calcula en cada hecho. | unique, not_null |
| `fuente` | STRING | Nombre lógico de la fuente (igual a la tabla externa de Bronze): transmetro_validaciones, tu_paradas, … | not_null |
| `archivo` | STRING | Archivo crudo de origen tal como lo entregó el operador. | not_null |
| `objeto_gcs` | STRING | Ruta gs:// del objeto en Bronze (partición ingest_date=…). | not_null |
| `ingest_date` | DATE | Fecha de ingesta a Bronze (partición Hive). | not_null |
| `via` | STRING | Vía de ingesta derivada del nombre de la fuente: streaming (TM, AM), cdc (padrón), batch (resto). | not_null, accepted_values |
| `tipo_contenido` | STRING | operacion (abordajes/viajes), catalogo (estaciones) o padron (CDC). | accepted_values |
| `modo_id` | STRING | Modo al que pertenece la fuente (el padrón es de Transmetro). | relationships→dim_modo |
| `n_filas_silver` | INT64 | Filas válidas en Silver provenientes de ese objeto (conteo de apoyo para conciliación). |  |

### dim_modo

Dimensión de modo/operador. Cuatro filas fijas definidas en el modelo (SELECT … UNNEST de STRUCTs, no seed): TM Transmetro (BRT, streaming), TU Transurbano (bus, batch), MR MetroRiel (tren ligero, batch), AM Aerómetro (teleférico, streaming). Dueño: Agencia · Arquitectura de datos.

- **Tabla:** `gold.dim_modo` · materialización `table`
- **Fuentes (`ref`):** 

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `modo_id` | STRING | Llave natural del modo: TM, TU, MR, AM. Misma codificación que Silver. | unique, not_null, accepted_values |
| `nombre` | STRING | Nombre del operador: Transmetro, Transurbano, MetroRiel, Aerómetro. | unique, not_null |
| `tipo` | STRING | Tecnología: BRT, bus, tren ligero, teleférico. |  |
| `via_ingesta` | STRING | Cómo llega la operación a Bronze: streaming (Kafka → GCS) o batch (archivo). | accepted_values |
| `fuente_operacion` | STRING | Nombre lógico de la fuente de operación del modo en Silver/dim_fuente (transmetro_validaciones, …). |  |
| `orden` | INT64 | Orden de presentación en el tablero (1–4). |  |

### dim_padron_historia

Historia SCD Tipo 2 del padrón de Transmetro, seudonimizada: una fila por versión de cada tarjeta, desde silver_padron_scd2 (ADR-009) unido a silver_usuarios por (modo, tarjeta) para sustituir la llave nativa por usuario_sk. Conserva las tarjetas dadas de baja (historizar, no borrar). Agrupada por usuario_sk.

- **Tabla:** `gold.dim_padron_historia` · materialización `table` · cluster por `usuario_sk`
- **Fuentes (`ref`):** `silver_padron_scd2`, `silver_usuarios`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `usuario_sk` | STRING | Seudónimo de la tarjeta (FK a dim_usuario). | not_null, relationships→dim_usuario |
| `usuario_unificado_sk` | STRING | Seudónimo de la persona (dim_usuario). |  |
| `modo_id` | STRING | Modo del formato de la tarjeta del padrón (TM, TU, MR). |  |
| `version` | INT64 | Número de versión por tarjeta (ROW_NUMBER por seq en Silver). | not_null |
| `seq` | INT64 | Secuencia del log CDC que originó la versión; única en el log. | unique, not_null |
| `operacion` | STRING | Operación del log: INSERT, UPDATE, DELETE. | accepted_values |
| `vigente_desde` | DATETIME | commit_ts de la operación (DATETIME). | not_null |
| `vigente_hasta` | DATETIME | commit_ts de la siguiente versión de la misma tarjeta (orden seq); NULL en la vigente. |  |
| `es_vigente` | BOOL | TRUE en la última versión de cada tarjeta (una por tarjeta). | not_null |
| `estado` | STRING | INACTIVA si la operación fue DELETE; ACTIVA en caso contrario. | accepted_values |
| `perfil` | STRING | Perfil vigente en esa versión (último no nulo hasta la operación). |  |
| `zona_residencia_id` | STRING | Zona de residencia conformada vigente en esa versión (FK a dim_zona). | relationships→dim_zona |
| `alta_implicita` | BOOL | TRUE en la primera versión de una tarjeta cuya primera operación no fue INSERT. |  |
| `alta_repetida` | BOOL | TRUE en un INSERT sobre tarjeta ya existente (aplicado como UPDATE). |  |
| `baja_sin_alta_previa` | BOOL | TRUE en un DELETE sin INSERT anterior. |  |
| `commit_ts_fuera_de_orden` | BOOL | TRUE cuando vigente_hasta < vigente_desde (hora aleatoria dentro del día en el generador); la vigencia sigue seq. |  |
| `fuente_sk` | STRING | FK a dim_fuente del log CDC crudo. | not_null, relationships→dim_fuente |

### dim_tiempo

Dimensión conformada de tiempo. Grano: una hora de un día. Rango derivado de los datos: desde el mínimo de silver_abordajes.fecha (y del padrón) hasta el máximo de abordajes, salida de MetroRiel y padrón, para que toda llave de los hechos exista. Hora pico y franja: seed franjas_horarias; feriados: seed feriados_gt. Dueño: Agencia · Planificación de operación.

- **Tabla:** `gold.dim_tiempo` · materialización `table`
- **Fuentes (`ref`):** `feriados_gt`, `franjas_horarias`, `silver_abordajes`, `silver_metroriel_viajes`, `silver_padron_scd2`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `tiempo_sk` | INT64 | Llave sustituta INT64 = AAAAMMDD*100 + hora (2026060107 = 2026-06-01 07:00). Calculada: CAST(FORMAT_DATE('%Y%m%d', fecha) AS INT64)*100 + hora. | unique, not_null |
| `fecha` | DATE | Fecha calendario (DATE), generada con GENERATE_DATE_ARRAY entre el mínimo y el máximo observados en Silver. | not_null |
| `hora` | INT64 | Hora del día 0–23 (INT64), generada con GENERATE_ARRAY(0, 23). | not_null, accepted_range |
| `fecha_hora_inicio` | DATETIME | DATETIME de inicio de la hora (fecha + hora:00:00); comodidad para ejes temporales en Tableau. |  |
| `franja` | STRING | Franja del día según el seed franjas_horarias: madrugada, pico_manana, valle, pico_tarde, noche. | not_null, accepted_values |
| `es_hora_pico` | BOOL | TRUE en 05–08 y 16–19 (seed franjas_horarias, definición oficial de la Agencia). | not_null |
| `dia_semana` | INT64 | Día de la semana ISO: 1 = lunes … 7 = domingo. Transformación de EXTRACT(DAYOFWEEK) de BigQuery (1 = domingo): MOD(DAYOFWEEK + 5, 7) + 1. | accepted_range |
| `dia_semana_nombre` | STRING | Nombre del día en español (lunes … domingo). |  |
| `es_fin_de_semana` | BOOL | TRUE si dia_semana es 6 (sábado) o 7 (domingo). |  |
| `es_feriado` | BOOL | TRUE si la fecha está en el seed feriados_gt (Guatemala 2026). |  |
| `nombre_feriado` | STRING | Nombre del feriado (seed feriados_gt); NULL si no es feriado. |  |
| `es_dia_habil` | BOOL | Definición oficial: lunes a viernes y no feriado (NOT es_fin_de_semana AND NOT es_feriado). | not_null |
| `semana_iso` | INT64 | Semana ISO 8601 del año (EXTRACT(ISOWEEK)). |  |
| `mes` | INT64 | Mes 1–12 (EXTRACT(MONTH)). |  |
| `anio_mes` | STRING | Año-mes 'AAAA-MM' (FORMAT_DATE('%Y-%m')); llave de agrupación para 'viajes del mes'. |  |
| `anio` | INT64 | Año (EXTRACT(YEAR)). |  |

### dim_usuario

Dimensión de usuario seudonimizado. Grano: una tarjeta por modo (ADR-008). Fuente: silver_usuarios SIN llave_nativa ni usuario_base_id (seguridad.md §2). usuario_sk = HMAC-SHA256(sal secreta, modo\|llave) calculado en Silver (ADR-007); usuario_unificado_sk une las tarjetas de la misma persona. n_modos_usados y es_multimodal se calculan sobre silver_abordajes por persona. Agrupada (cluster) por modo_id.

- **Tabla:** `gold.dim_usuario` · materialización `table` · cluster por `modo_id`
- **Fuentes (`ref`):** `silver_abordajes`, `silver_usuarios`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `usuario_sk` | STRING | Seudónimo estable de la tarjeta: HMAC-SHA256(sal, modo_id\|llave_nativa), 64 hex (silver_usuarios). Única llave de usuario en Gold. | unique, not_null |
| `usuario_unificado_sk` | STRING | Seudónimo de la persona: HMAC-SHA256(sal, 'BASE\|' \|\| usuario_base_id); NULL si la tarjeta no se pudo vincular (ADR-008). |  |
| `modo_id` | STRING | Modo emisor de la tarjeta (FK a dim_modo). | not_null, relationships→dim_modo |
| `metodo_vinculo` | STRING | Cómo se vinculó la tarjeta a la persona: formato (regex TC-/10 dígitos/MR) o inversion_md5 (Aerómetro); NULL sin vínculo. | accepted_values |
| `tiene_vinculo` | BOOL | TRUE si usuario_unificado_sk no es nulo. |  |
| `en_padron` | BOOL | TRUE si la persona tiene fila en el padrón aplicado de Transmetro (silver_usuarios). | not_null |
| `perfil` | STRING | Perfil vigente del padrón (silver_usuarios); NULL si no está en el padrón. |  |
| `zona_residencia_id` | STRING | Zona de residencia conformada del padrón (FK a dim_zona); NULL si no está en el padrón. | relationships→dim_zona |
| `estado_padron` | STRING | ACTIVA / INACTIVA según el padrón aplicado; SIN_PADRON si la persona no aparece en él. | not_null, accepted_values |
| `n_abordajes_tarjeta` | INT64 | Abordajes válidos de esta tarjeta en silver_abordajes (COUNT por modo, llave). | not_null |
| `n_abordajes_persona` | INT64 | Abordajes válidos de la persona en todos sus modos (COUNT por usuario_unificado_sk). |  |
| `n_modos_usados` | INT64 | COUNT(DISTINCT modo_id) de silver_abordajes por usuario_unificado_sk (persona); 0 si nunca abordó. | not_null, accepted_range |
| `es_multimodal` | BOOL | TRUE si n_modos_usados > 1 (la persona usa más de un sistema). | not_null |

### dim_zona

Dimensión conformada de zona. Universo completo del seed zonas (26 filas: 22 zonas de la Ciudad de Guatemala y 4 municipios), incluidas las zonas sin datos, para que 'zona sin servicio' sea una fila. Atributos de cobertura calculados desde silver_estaciones. Dueño: Agencia · Planificación territorial.

- **Tabla:** `gold.dim_zona` · materialización `table`
- **Fuentes (`ref`):** `silver_estaciones`, `zonas`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `zona_id` | STRING | Llave natural conformada del seed zonas (GT-Z01 … GT-Z25, GT-MIXCO, …). | unique, not_null, relationships→zonas |
| `zona_nombre` | STRING | Nombre canónico ('Zona 10', 'Mixco') del seed zonas. | unique, not_null |
| `tipo` | STRING | zona_ciudad o municipio (seed zonas). |  |
| `municipio` | STRING | Municipio al que pertenece (Guatemala para las zonas de la ciudad). |  |
| `presente_en_datos` | BOOL | Marca del seed: algún operador o el padrón menciona la zona. |  |
| `orden` | INT64 | Orden de presentación (número de zona; municipios 101+). |  |
| `n_estaciones_total` | INT64 | Estaciones y paradas de todos los modos en la zona: COUNT(*) de silver_estaciones por zona_id; 0 si no hay. | not_null |
| `n_modos_con_servicio` | INT64 | COUNT(DISTINCT modo_id) de silver_estaciones en la zona; 0 = zona sin servicio. | not_null |
| `modos_con_servicio` | STRING | Modos con al menos una estación en la zona, STRING ordenado ('AM,MR,TM,TU'); NULL si ninguno. |  |
| `tiene_servicio` | BOOL | TRUE si al menos un modo tiene una estación o parada en la zona. | not_null |

## Hechos

### fct_abordaje

Hecho principal (ADR-004). Grano: una validación de una tarjeta de un usuario en un modo, en una estación o parada, en un instante. Una fila por fila de silver_abordajes (Transmetro válidas, Transurbano cobros exitosos, entrada de cada viaje cerrado de MetroRiel, Aerómetro válidos), con usuario_sk/usuario_unificado_sk de silver_usuarios en lugar de la llave nativa. Particionada por fecha; cluster por modo_id, zona_id.

- **Tabla:** `gold.fct_abordaje` · materialización `table` · partición por `fecha` · cluster por `modo_id`, `zona_id`
- **Fuentes (`ref`):** `dim_tiempo`, `silver_abordajes`, `silver_usuarios`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `abordaje_sk` | STRING | Llave del abordaje = abordaje_id de Silver: modo\|id nativo (TM validacion_id, MR trip_id, AM boarding_id, TU registro_hash\|n_repeticion). | unique, not_null |
| `tiempo_sk` | INT64 | FK a dim_tiempo: AAAAMMDD*100 + hora del instante local del abordaje. | not_null, relationships→dim_tiempo |
| `fecha` | DATE | DATE(fecha_hora) local; columna de partición. | not_null |
| `hora` | INT64 | Hora local 0–23 del abordaje. | not_null |
| `modo_id` | STRING | FK a dim_modo (TM, TU, MR, AM). | not_null, accepted_values, relationships→dim_modo |
| `estacion_sk` | STRING | FK a dim_estacion (estación de entrada en MetroRiel). | not_null, relationships→dim_estacion |
| `zona_id` | STRING | FK a dim_zona: zona conformada de la estación/parada. | not_null, relationships→dim_zona |
| `usuario_sk` | STRING | FK a dim_usuario: HMAC-SHA256 de (modo\|llave nativa) obtenido de silver_usuarios por (modo_id, llave_nativa). La llave nativa no se copia. | not_null, relationships→dim_usuario |
| `usuario_unificado_sk` | STRING | Seudónimo de la persona (dim_usuario.usuario_unificado_sk); permite contar transbordos entre modos. |  |
| `fuente_sk` | STRING | FK a dim_fuente: hash de (fuente\|archivo\|objeto_gcs\|ingest_date) de la fila Silver. | not_null, relationships→dim_fuente |
| `fecha_hora` | DATETIME | Instante local del abordaje (DATETIME America/Guatemala) = silver_abordajes.fecha_hora_local. | not_null |
| `monto_q` | NUMERIC | Medida ADITIVA: monto cobrado en quetzales (NUMERIC); 0 es válido (adulto mayor, transbordo gratuito). | not_null |
| `abordajes` | INT64 | Medida ADITIVA: constante 1 (un abordaje = un viaje según definiciones_oficiales.md §1); SUM = viajes. | not_null, accepted_values |
| `tipo_validacion` | STRING | Tipo nativo: TM ENTRADA/TRANSBORDO; TU OK; MR ENTRADA; AM BOARDING. | accepted_values |
| `es_transbordo_interno` | BOOL | TRUE si es un TRANSBORDO de Transmetro (tarifa reducida dentro del mismo sistema). | not_null |
| `franja` | STRING | Franja horaria desnormalizada de dim_tiempo (para Tableau). |  |
| `es_hora_pico` | BOOL | Desnormalizado de dim_tiempo (05–08, 16–19). | not_null |
| `es_dia_habil` | BOOL | Desnormalizado de dim_tiempo (lunes–viernes no feriado). | not_null |
| `fuente` | STRING | Linaje: nombre lógico de la fuente de Bronze. | not_null |
| `archivo` | STRING | Linaje: archivo crudo de origen. | not_null |
| `objeto_gcs` | STRING | Linaje: objeto gs:// de Bronze. |  |
| `ingest_date` | DATE | Linaje: fecha de ingesta a Bronze. | not_null |
| `linea_num` | INT64 | Linaje streaming (TM, AM): número de línea en el archivo publicado a Kafka; NULL en batch. |  |
| `kafka_offset` | INT64 | Linaje streaming (TM, AM): offset de Kafka; NULL en batch. |  |

### fct_cambio_padron

Hecho de transacción: una operación del log CDC aplicada al padrón (INSERT/UPDATE/DELETE), desde silver_padron_scd2 con usuario_sk de silver_usuarios. Regla de tarjetas_activas_despues: delta_activas = +1 si la operación deja ACTIVA una tarjeta antes INACTIVA o inexistente, −1 si deja INACTIVA una ACTIVA, 0 en otro caso; saldo = SUM(delta) acumulado por seq. Invariante: último saldo = tarjetas vigentes ACTIVA (assert_saldo_tarjetas_activas_igual_vigentes).

- **Tabla:** `gold.fct_cambio_padron` · materialización `table` · cluster por `usuario_sk`
- **Fuentes (`ref`):** `silver_padron_scd2`, `silver_usuarios`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `seq` | INT64 | Secuencia del log CDC (orden de aplicación); llave del hecho. | unique, not_null |
| `tiempo_sk` | INT64 | FK a dim_tiempo: AAAAMMDD*100 + hora de commit_ts. | not_null, relationships→dim_tiempo |
| `fecha` | DATE | DATE(commit_ts). | not_null |
| `fecha_hora` | DATETIME | commit_ts de la operación (DATETIME). |  |
| `usuario_sk` | STRING | FK a dim_usuario (tarjeta seudonimizada). | not_null, relationships→dim_usuario |
| `usuario_unificado_sk` | STRING | Seudónimo de la persona. |  |
| `modo_id` | STRING | Modo del formato de la tarjeta (TM, TU, MR); FK a dim_modo. | relationships→dim_modo |
| `version` | INT64 | Versión SCD2 que produce la operación (dim_padron_historia.version). |  |
| `operacion` | STRING | INSERT, UPDATE o DELETE. | not_null, accepted_values |
| `estado_resultante` | STRING | Estado de la tarjeta tras la operación: INACTIVA si DELETE, ACTIVA en otro caso. |  |
| `estado_previo` | STRING | Estado de la versión anterior de la misma tarjeta (LAG por seq); NULL si la tarjeta no existía. |  |
| `perfil` | STRING | Perfil vigente tras la operación. |  |
| `zona_residencia_id` | STRING | Zona de residencia conformada tras la operación (FK a dim_zona). | relationships→dim_zona |
| `alta_implicita` | BOOL | TRUE si la primera operación de la tarjeta no fue INSERT. |  |
| `baja_sin_alta_previa` | BOOL | TRUE en un DELETE sin INSERT anterior. |  |
| `alta_repetida` | BOOL | TRUE en un INSERT sobre tarjeta ya existente. |  |
| `operaciones` | INT64 | Medida ADITIVA: constante 1. |  |
| `delta_activas` | INT64 | Medida ADITIVA (+1, −1, 0): cambio en el número de tarjetas activas que produce la operación. | accepted_values |
| `tarjetas_activas_despues` | INT64 | Medida SEMI ADITIVA (saldo): tarjetas activas acumuladas tras esta operación (SUM(delta_activas) OVER (ORDER BY seq)). Se compara entre instantes; no se suma en el tiempo. | not_null, accepted_range |
| `fuente_sk` | STRING | FK a dim_fuente del log CDC crudo. | not_null, relationships→dim_fuente |

### fct_cobertura_zona_modo

Hecho sin medidas (factless): una fila por (zona, modo) con al menos una estación o parada en silver_estaciones. Cobertura del tablero: dim_zona LEFT JOIN este hecho; zona sin fila = sin servicio.

- **Tabla:** `gold.fct_cobertura_zona_modo` · materialización `table`
- **Fuentes (`ref`):** `silver_estaciones`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `zona_id` | STRING | FK a dim_zona. | not_null, relationships→dim_zona |
| `modo_id` | STRING | FK a dim_modo. | not_null, accepted_values, relationships→dim_modo |
| `n_estaciones` | INT64 | Conteo de apoyo (ADITIVO entre zonas y modos): estaciones/paradas del modo en la zona. | not_null |
| `n_lineas_rutas` | INT64 | COUNT(DISTINCT linea_ruta_eje) del modo en la zona. |  |
| `fuente_sk` | STRING | FK a dim_fuente del catálogo crudo del operador. | not_null, relationships→dim_fuente |
| `tiene_servicio` | BOOL | Constante TRUE: la existencia de la fila es el hecho (factless). |  |

### fct_uso_usuario_dia

Snapshot periódico: una fila por tarjeta seudonimizada × fecha × modo, calculada directamente desde silver_abordajes + silver_usuarios + dim_tiempo (camino independiente de fct_abordaje para la prueba de fuego 'viajes del mes'). Base de la pregunta de transbordo. Particionada por fecha; cluster por modo y persona.

- **Tabla:** `gold.fct_uso_usuario_dia` · materialización `table` · partición por `fecha` · cluster por `modo_id`, `usuario_unificado_sk`
- **Fuentes (`ref`):** `dim_tiempo`, `silver_abordajes`, `silver_usuarios`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `usuario_sk` | STRING | FK a dim_usuario (tarjeta seudonimizada). | not_null, relationships→dim_usuario |
| `usuario_unificado_sk` | STRING | Seudónimo de la persona (agrupa las tarjetas de la misma persona entre modos). |  |
| `fecha` | DATE | Día del snapshot; columna de partición. | not_null |
| `tiempo_sk_dia` | INT64 | AAAAMMDD*100: tiempo_sk de la hora 0 del día (FK a dim_tiempo a nivel día). | relationships→dim_tiempo |
| `modo_id` | STRING | FK a dim_modo. | not_null, relationships→dim_modo |
| `abordajes` | INT64 | Medida ADITIVA: COUNT de abordajes válidos de la tarjeta ese día en ese modo. | not_null |
| `monto_q` | NUMERIC | Medida ADITIVA: SUM(monto_q) del día. | not_null |
| `abordajes_hora_pico` | INT64 | Medida ADITIVA: COUNTIF(es_hora_pico) según dim_tiempo. | not_null |
| `estaciones_distintas` | INT64 | Medida NO ADITIVA: COUNT(DISTINCT estacion_sk) del día. |  |
| `zona_id_mas_frecuente` | STRING | FK a dim_zona: zona con más abordajes de la tarjeta ese día (empate → menor zona_id). | not_null, relationships→dim_zona |
| `primera_hora` | INT64 | MIN(hora) del día (0–23). |  |
| `ultima_hora` | INT64 | MAX(hora) del día (0–23). |  |
| `es_dia_habil` | BOOL | Desnormalizado de dim_tiempo. |  |

### fct_viaje_metroriel

Hecho de viaje cerrado de MetroRiel (grano: un viaje con entrada y salida), desde silver_metroriel_viajes con usuario seudonimizado. Conserva origen–destino real; su entrada también está en fct_abordaje (abordaje_sk 'MR\|trip_id'). Particionado por fecha_entrada; cluster por zona de origen y destino.

- **Tabla:** `gold.fct_viaje_metroriel` · materialización `table` · partición por `fecha_entrada` · cluster por `zona_id_origen`, `zona_id_destino`
- **Fuentes (`ref`):** `dim_tiempo`, `silver_metroriel_viajes`, `silver_usuarios`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `trip_id` | INT64 | Id del viaje del operador (silver_metroriel_viajes.trip_id). | unique, not_null |
| `abordaje_sk` | STRING | 'MR\|' \|\| trip_id: llave del abordaje correspondiente en fct_abordaje (drill-across). | not_null, relationships→fct_abordaje |
| `modo_id` | STRING | Siempre MR (FK a dim_modo). | relationships→dim_modo |
| `tiempo_sk_entrada` | INT64 | FK a dim_tiempo de la hora de entrada (role-playing). | not_null, relationships→dim_tiempo |
| `tiempo_sk_salida` | INT64 | FK a dim_tiempo de la hora de salida (role-playing), desde fecha_hora_salida_local. | not_null, relationships→dim_tiempo |
| `fecha_entrada` | DATE | DATE de la entrada; columna de partición. | not_null |
| `fecha_salida` | DATE | DATE de la salida. |  |
| `hora_entrada` | INT64 | Hora local 0–23 de la entrada. |  |
| `estacion_sk_origen` | STRING | FK a dim_estacion de la estación de entrada. | not_null, relationships→dim_estacion |
| `estacion_sk_destino` | STRING | FK a dim_estacion de la estación de salida. | not_null, relationships→dim_estacion |
| `zona_id_origen` | STRING | FK a dim_zona de la estación de entrada. | not_null, relationships→dim_zona |
| `zona_id_destino` | STRING | FK a dim_zona de la estación de salida. | not_null, relationships→dim_zona |
| `cambia_de_zona` | BOOL | TRUE si zona de origen ≠ zona de destino. |  |
| `usuario_sk` | STRING | FK a dim_usuario (HMAC de MR\|card, desde silver_usuarios). | not_null, relationships→dim_usuario |
| `usuario_unificado_sk` | STRING | Seudónimo de la persona. |  |
| `fuente_sk` | STRING | FK a dim_fuente (archivo metroriel_viajes). | not_null, relationships→dim_fuente |
| `fecha_hora_entrada` | DATETIME | DATETIME local de entrada (entry_ts). | not_null |
| `fecha_hora_salida` | DATETIME | DATETIME local de salida (exit_ts). | not_null |
| `monto_q` | NUMERIC | Medida ADITIVA: tarifa en quetzales (fare_gtq). | not_null |
| `duracion_s` | INT64 | Medida ADITIVA: duración del viaje en segundos (duration_s del operador); útil como total de tiempo a bordo. | not_null |
| `duracion_min` | FLOAT64 | Medida ADITIVA: duracion_s / 60 redondeado a 2 decimales. El promedio (no aditivo) se recalcula como SUM(duracion_min)/SUM(viajes). |  |
| `viajes` | INT64 | Medida ADITIVA: constante 1. | not_null |
| `franja` | STRING | Franja de la hora de entrada (dim_tiempo). |  |
| `es_hora_pico` | BOOL | Desnormalizado de dim_tiempo para la hora de entrada. |  |
| `es_dia_habil` | BOOL | Desnormalizado de dim_tiempo para la fecha de entrada. |  |
| `fuente` | STRING | Linaje: fuente lógica (metroriel_viajes). |  |
| `archivo` | STRING | Linaje: archivo crudo. |  |
| `objeto_gcs` | STRING | Linaje: objeto gs:// de Bronze. |  |
| `ingest_date` | DATE | Linaje: fecha de ingesta. |  |

## Agregados para Tableau

### agg_cobertura_zona

Agregado para Tableau (cobertura): una fila por zona de dim_zona con oferta (fct_cobertura_zona_modo) y demanda (fct_abordaje). sin_servicio = ninguna estación ni parada de ningún modo.

- **Tabla:** `gold.agg_cobertura_zona` · materialización `table`
- **Fuentes (`ref`):** `dim_zona`, `fct_abordaje`, `fct_cobertura_zona_modo`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `zona_id` | STRING | FK a dim_zona. | unique, not_null, relationships→dim_zona |
| `zona_nombre` | STRING | Nombre canónico. |  |
| `tipo` | STRING | zona_ciudad o municipio. |  |
| `municipio` | STRING | Municipio. |  |
| `orden` | INT64 | Orden de presentación. |  |
| `n_modos_con_servicio` | INT64 | Filas de fct_cobertura_zona_modo en la zona (0–4). | not_null |
| `n_estaciones` | INT64 | SUM(n_estaciones) de fct_cobertura_zona_modo. |  |
| `modos_con_servicio` | STRING | Modos con estación en la zona, STRING ordenado. |  |
| `abordajes_totales` | INT64 | Medida ADITIVA: SUM(abordajes) de fct_abordaje en la zona. |  |
| `monto_q_total` | NUMERIC | Medida ADITIVA: SUM(monto_q). |  |
| `usuarios_distintos` | INT64 | Medida NO ADITIVA: COUNT(DISTINCT usuario_sk) en la zona. |  |
| `n_modos_con_demanda` | INT64 | COUNT(DISTINCT modo_id) con abordajes en la zona. |  |
| `tiene_servicio` | BOOL | TRUE si hay al menos una fila en fct_cobertura_zona_modo. | not_null |
| `sin_servicio` | BOOL | TRUE si ningún modo tiene estación ni parada en la zona (respuesta directa a la pregunta 2). | not_null |
| `tiene_estacion_sin_demanda` | BOOL | TRUE si hay oferta (estaciones) pero ningún abordaje. |  |

### agg_demanda_modo_zona_hora

Agregado para Tableau (demanda por modo, zona y hora): fct_abordaje × dim_tiempo agrupado por fecha, hora, modo y zona. Particionado por fecha; cluster por modo y zona.

- **Tabla:** `gold.agg_demanda_modo_zona_hora` · materialización `table` · partición por `fecha` · cluster por `modo_id`, `zona_id`
- **Fuentes (`ref`):** `dim_tiempo`, `fct_abordaje`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `tiempo_sk` | INT64 | FK a dim_tiempo. | not_null, relationships→dim_tiempo |
| `fecha` | DATE | Fecha (partición). |  |
| `hora` | INT64 | Hora 0–23. |  |
| `franja` | STRING | Franja de dim_tiempo. |  |
| `es_hora_pico` | BOOL | De dim_tiempo. |  |
| `es_dia_habil` | BOOL | De dim_tiempo. |  |
| `dia_semana` | INT64 | 1 = lunes … 7 = domingo. |  |
| `dia_semana_nombre` | STRING | Nombre del día en español. |  |
| `modo_id` | STRING | FK a dim_modo. | relationships→dim_modo |
| `zona_id` | STRING | FK a dim_zona. | relationships→dim_zona |
| `abordajes` | INT64 | Medida ADITIVA: SUM(abordajes). |  |
| `monto_q` | NUMERIC | Medida ADITIVA: SUM(monto_q). |  |
| `usuarios_distintos` | INT64 | Medida NO ADITIVA: COUNT(DISTINCT usuario_sk) en la celda; no se suma entre horas, zonas ni modos. |  |
| `estaciones_con_demanda` | INT64 | Medida NO ADITIVA: COUNT(DISTINCT estacion_sk) en la celda. |  |

### agg_metroriel_zonas

Agregado para Tableau (caso MetroRiel): una fila por zona con abordajes por modo, totales, usuarios distintos y ranking; es_zona_metroriel marca las zonas 12, 8, 1, 6 y 17 del enunciado.

- **Tabla:** `gold.agg_metroriel_zonas` · materialización `table`
- **Fuentes (`ref`):** `dim_zona`, `fct_abordaje`, `fct_cobertura_zona_modo`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `zona_id` | STRING | FK a dim_zona. | unique, not_null, relationships→dim_zona |
| `zona_nombre` | STRING | Nombre canónico. |  |
| `tipo` | STRING | zona_ciudad o municipio. |  |
| `orden` | INT64 | Orden de presentación. |  |
| `es_zona_metroriel` | BOOL | TRUE para GT-Z12, GT-Z08, GT-Z01, GT-Z06, GT-Z17 (zonas de la línea de MetroRiel según el enunciado). | not_null |
| `n_estaciones_mr` | INT64 | Estaciones de MetroRiel en la zona (fct_cobertura_zona_modo). |  |
| `abordajes_tm` | INT64 | Medida ADITIVA: abordajes de Transmetro en la zona. |  |
| `abordajes_tu` | INT64 | Medida ADITIVA: abordajes de Transurbano. |  |
| `abordajes_mr` | INT64 | Medida ADITIVA: abordajes (entradas) de MetroRiel. |  |
| `abordajes_am` | INT64 | Medida ADITIVA: abordajes de Aerómetro. |  |
| `abordajes_totales` | INT64 | Medida ADITIVA: suma de los cuatro modos. |  |
| `usuarios_distintos` | INT64 | Medida NO ADITIVA: COUNT(DISTINCT usuario_sk) en la zona. |  |
| `personas_distintas` | INT64 | Medida NO ADITIVA: COUNT(DISTINCT usuario_unificado_sk) en la zona. |  |
| `pct_metroriel` | FLOAT64 | Medida NO ADITIVA: abordajes_mr / abordajes_totales × 100. |  |
| `ranking` | INT64 | RANK() por abordajes_totales descendente (1 = zona con más demanda; empates por orden). |  |

### agg_transbordo

Agregado para Tableau (transbordo): una fila por persona seudonimizada (usuario_unificado_sk) desde fct_uso_usuario_dia, con número de modos usados, combinación de modos y abordajes.

- **Tabla:** `gold.agg_transbordo` · materialización `table` · cluster por `n_modos`
- **Fuentes (`ref`):** `fct_uso_usuario_dia`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `usuario_unificado_sk` | STRING | Seudónimo de la persona (ADR-008). | unique, not_null |
| `n_modos` | INT64 | Medida NO ADITIVA: COUNT(DISTINCT modo_id) de la persona (1–4). | not_null, accepted_range |
| `modos` | STRING | Modos usados, STRING ordenado (p. ej. 'MR,TM'). |  |
| `abordajes` | INT64 | Medida ADITIVA: SUM(abordajes). |  |
| `monto_q` | NUMERIC | Medida ADITIVA: SUM(monto_q). |  |
| `dias_activos` | INT64 | COUNT(DISTINCT fecha) con al menos un abordaje. |  |
| `dias_tm` | INT64 | Días con abordajes en Transmetro. |  |
| `dias_tu` | INT64 | Días con abordajes en Transurbano. |  |
| `dias_mr` | INT64 | Días con abordajes en MetroRiel. |  |
| `dias_am` | INT64 | Días con abordajes en Aerómetro. |  |
| `es_multimodal` | BOOL | TRUE si n_modos > 1. | not_null |

### agg_transbordo_resumen

Resumen de agg_transbordo por número de modos: usuarios, porcentaje, abordajes y combinación más frecuente.

- **Tabla:** `gold.agg_transbordo_resumen` · materialización `table`
- **Fuentes (`ref`):** `agg_transbordo`

| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |
|---|---|---|---|
| `n_modos` | INT64 | Número de modos usados por la persona (1–4). | unique, not_null |
| `es_multimodal` | BOOL | n_modos > 1. |  |
| `usuarios` | INT64 | Personas con ese número de modos. | not_null |
| `pct_usuarios` | FLOAT64 | Medida NO ADITIVA: usuarios / total de personas × 100. |  |
| `abordajes` | INT64 | Medida ADITIVA: abordajes de esas personas. |  |
| `abordajes_por_usuario` | FLOAT64 | Medida NO ADITIVA: abordajes / usuarios. |  |
| `combinacion_mas_frecuente` | STRING | Combinación de modos más común dentro del grupo. |  |
| `usuarios_combinacion` | INT64 | Personas con esa combinación. |  |

