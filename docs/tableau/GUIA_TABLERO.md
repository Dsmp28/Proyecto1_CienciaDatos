# Guía del tablero 2.1 · Red Metropolitana (Tableau Desktop sobre BigQuery `gold`)

Objetivo: responder las cuatro preguntas del enunciado con seis hojas y un dashboard, cada cifra verificable con un
SQL de `analysis/` (ejecutados el 2026-09-20; tiempos y bytes en `docs/evidence/tablero_resumen.md`).
Conexión: `docs/tableau/README.md`. Definiciones: `docs/governance/definiciones_oficiales.md` (un viaje = un abordaje
válido; usuario activo = viaje en los 30 días anteriores a `fecha_referencia = 2026-07-16`). Diccionario de columnas:
`docs/governance/diccionario_gold.md`.

## 0. Fuentes de datos en Tableau

| Fuente en Tableau | Tabla(s) Gold | Filas | Uso |
|---|---|---:|---|
| `Red Metropolitana · Gold (BigQuery)` (el `.tds`) | `fct_abordaje` × `dim_tiempo`, `dim_modo`, `dim_zona`, `dim_estacion`, `dim_usuario` | 1 647 569 | detalle, KPIs con filtros de fecha, linaje |
| `agg_demanda` | `agg_demanda_modo_zona_hora` + join izquierdo a `dim_zona` (`zona_id`) y `dim_modo` (`modo_id`) | 37 619 | H1, H2 (rápido: 0,8 MB por consulta) |
| `agg_cobertura` | `agg_cobertura_zona` | 26 | H3 |
| `agg_transbordo_resumen` | `agg_transbordo_resumen` | 4 | H4 |
| `agg_transbordo` | `agg_transbordo` | 56 848 | H4 (detalle por combinación de modos) |
| `agg_metroriel` | `agg_metroriel_zonas` | 26 | H5 |

Regla: los agregados `agg_*` para las hojas (rapidez), `fct_*` cuando hace falta el detalle (KPIs con ventana de
fecha, linaje). Los `agg_*` no tienen columna `fecha` salvo `agg_demanda_modo_zona_hora`, así que el filtro global de
fecha solo afecta a H1, H2 y H6 (ver §8).

Parámetro global: `[Fecha de referencia]` (tipo fecha, valor `2026-07-16`). Nunca usar `TODAY()` (misma regla que
"nunca `CURRENT_DATE`" del pipeline).

## 1. Campos calculados (crear una vez por fuente)

| Nombre | Fórmula de Tableau | Fuente | Nota |
|---|---|---|---|
| `Viajes` | `SUM([abordajes])` | todas | medida aditiva; "un viaje = un abordaje" |
| `% del total` | `SUM([abordajes]) / TOTAL(SUM([abordajes]))` | agg_demanda | cálculo de tabla, "Tabla (hacia abajo)" o según la hoja |
| `% Hora pico` | `SUM(IF [es_hora_pico] THEN [abordajes] ELSE 0 END) / SUM([abordajes])` | agg_demanda, `.tds` | no aditiva |
| `Hora (etiqueta)` | `RIGHT("0" + STR([hora]), 2) + ":00"` | agg_demanda | eje discreto ordenado por `hora` |
| `Modo (nombre)` | `CASE [modo_id] WHEN "TM" THEN "Transmetro" WHEN "TU" THEN "Transurbano" WHEN "MR" THEN "MetroRiel" WHEN "AM" THEN "Aerómetro" END` | agg_demanda | o usar `dim_modo.nombre` vía join |
| `Estado de cobertura` | `IF [sin_servicio] THEN "Sin servicio" ELSE "Con servicio" END` | agg_cobertura | color rojo / gris |
| `Zonas sin servicio` | `SUM(IF [sin_servicio] THEN 1 ELSE 0 END)` | agg_cobertura | KPI |
| `Usuarios multimodales` | `SUM(IF [es_multimodal] THEN [usuarios] ELSE 0 END)` | agg_transbordo_resumen | |
| `% Multimodal` | `SUM(IF [es_multimodal] THEN [usuarios] ELSE 0 END) / SUM([usuarios])` | agg_transbordo_resumen | KPI |
| `Trazado MetroRiel` | `IF [es_zona_metroriel] THEN "En el trazado (12, 8, 1, 6, 17)" ELSE "Fuera del trazado" END` | agg_metroriel | color |
| `Usuarios activos (30 d)` | `COUNTD(IF [fecha] >= DATEADD('day', -30, [Fecha de referencia]) AND [fecha] < [Fecha de referencia] AND [estado_padron] <> "INACTIVA" THEN [usuario_unificado_sk] END)` | `.tds` | definición oficial §2; `estado_padron` viene de `dim_usuario` |
| `Viajes del mes` | `SUM(IF [anio_mes] = [Mes de referencia] THEN [abordajes] ELSE 0 END)` | `.tds` | parámetro `[Mes de referencia]` = `"2026-06"`; `anio_mes` viene de `dim_tiempo` |
| `Zona (nombre corto)` | `REPLACE([zona_nombre], "Zona ", "Z")` | agg_demanda, agg_metroriel | etiquetas cortas en barras |

## 2. H1 · Demanda por modo y hora (mapa de calor)

- **Fuente:** `agg_demanda`.
- **Columnas:** `Modo (nombre)` (ordenado por `dim_modo.orden`: Transmetro, Transurbano, MetroRiel, Aerómetro).
- **Filas:** `hora` (discreto, 4 → 22; no hay servicio de 23 a 3).
- **Marcas:** cuadrado; **Color:** `Viajes` (paleta secuencial naranja, 5 pasos); **Etiqueta:** `Viajes`.
- **Filtros:** `es_dia_habil` (global), `fecha` (global, rango), `modo_id` (global).
- **Resaltar hora pico:** arrastrar `es_hora_pico` a Filas antes de `hora` (agrupa 05–08 y 16–19) o usarlo como
  borde de la marca; añadir una segunda hoja "barras por hora" con `hora` en Columnas, `Viajes` en Filas y
  `es_hora_pico` en Color.
- **Cifra esperada (`analysis/h1_demanda_modo_hora.sql`):** total 1 647 569; hora pico 906 950 = **55,05 %**;
  07:00 = 197 491 (11,99 %, la celda más oscura en los cuatro modos); 17:00 = 167 251; valle 09–15 ≈ 58 500/hora.
  Con filtro `modo_id = TU`, 07:00 = 94 093.

## 3. H2 · Demanda por zona con modo apilado (barras)

- **Fuente:** `agg_demanda`.
- **Filas:** `Zona (nombre corto)` ordenado descendente por `Viajes`.
- **Columnas:** `Viajes`. **Color:** `Modo (nombre)` (apilado). **Etiqueta:** `Viajes` al final de la barra
  (cálculo de tabla `% del total` como segundo campo de etiqueta, "Tabla (hacia abajo)").
- **Filtros:** globales (`fecha`, `modo_id`, `es_dia_habil`); filtro "Top N" opcional: `zona_id` → Top 10 por
  `SUM([abordajes])`.
- **Línea de referencia:** promedio de `Viajes` por zona (1 647 569 / 15 = 109 838).
- **Cifra esperada (`analysis/h2_demanda_zona.sql`):** 15 barras. Zona 17 = **148 554** (9,02 %), Zona 12 = 147 903,
  Zona 8 = 147 081, Zona 6 = 138 899, Zona 1 = 137 170; Mixco = 132 768 con el segmento de Aerómetro más largo
  (57 907). Últimas: Zona 4, 9 y 10 (≈ 75–78 mil, solo dos colores: TM y TU).

## 4. H3 · Cobertura (tabla con zonas sin servicio en rojo)

- **Fuente:** `agg_cobertura`.
- **Filas:** `zona_nombre` (ordenar por `orden`). **Columnas (texto):** `modos_con_servicio`, `n_modos_con_servicio`,
  `n_estaciones`, `abordajes_totales`, `usuarios_distintos`.
- **Color:** `Estado de cobertura` (Sin servicio = rojo `#c0392b`, Con servicio = gris). Marca: cuadrado o texto.
- **Variante mapa:** no hay geometrías de zona en Gold (solo `dim_estacion.lat/lon` de Transmetro). Alternativa
  visual: matriz zona × modo con `fct_cobertura_zona_modo` (fila = zona, columna = modo, marca si existe fila).
- **Filtro:** `tipo` (zona_ciudad / municipio). No aplica el filtro global de fecha (la oferta no depende del día).
- **Enriquecimiento para la recomendación:** unir (relación) `dim_usuario` por `zona_residencia_id = zona_id` y
  mostrar `COUNTD([usuario_unificado_sk])` = personas del padrón que residen en la zona.
- **Cifra esperada (`analysis/h3_cobertura.sql`):** **11 filas rojas** de 26: Zonas 2, 3, 5, 14, 15, 16, 19, 21, 24,
  25 y Santa Catarina Pinula. Santa Catarina Pinula: 0 estaciones y **1 261 personas** (2 677 tarjetas) del padrón.
  `tiene_estacion_sin_demanda` = falso en las 15 zonas con servicio.

## 5. H4 · Transbordo (barras n_modos → usuarios y %)

- **Fuente:** `agg_transbordo_resumen`.
- **Columnas:** `n_modos` (discreto, 1–4). **Filas:** `SUM([usuarios])`. **Color:** `es_multimodal`.
  **Etiqueta:** `SUM([usuarios])` y `pct_usuarios` (ya calculado en la tabla, ATTR o AVG).
- **KPI en la misma hoja (o en H6):** `% Multimodal` como texto grande.
- **Detalle (segunda hoja "Combinaciones"):** fuente `agg_transbordo`; Filas `modos`; Columnas `COUNTD([usuario_unificado_sk])`
  ordenado desc; Color `n_modos`.
- **Filtros:** ninguno global (los agregados de transbordo cubren los 45 días; la definición de persona es ADR-008).
- **Cifra esperada (`analysis/h4_transbordo.sql`):** 1 modo 15 363 (27,02 %) · 2 modos 25 048 (44,06 %) · 3 modos
  14 004 (24,63 %) · 4 modos 2 433 (4,28 %). **% Multimodal = 72,98 %** (41 485 de 56 848). Combinación más
  frecuente: TM,TU = 12 477.

## 6. H5 · Caso MetroRiel (ranking de zonas + barras por modo)

- **Fuente:** `agg_metroriel`.
- **Hoja 5a "Ranking":** Filas `zona_nombre` ordenado por `ranking`; Columnas `SUM([abordajes_totales])`;
  **Color:** `Trazado MetroRiel` (en el trazado = azul `#1f4e79`, fuera = gris); Etiqueta `ranking` y `abordajes_totales`.
  Filtro `abordajes_totales > 0` (deja 15 zonas).
- **Hoja 5b "Por modo":** Filas `zona_nombre` (top 10 por `ranking`); Columnas `Valores de medida` con
  `SUM([abordajes_tm])`, `SUM([abordajes_tu])`, `SUM([abordajes_mr])`, `SUM([abordajes_am])`; Color `Nombres de
  medida`; barras apiladas. Etiqueta `pct_metroriel`.
- **Contraste O–D (opcional, `.tds` + `fct_viaje_metroriel`):** `SUM(IF [cambia_de_zona] THEN 1 ELSE 0 END)/SUM([viajes])`.
- **Cifra esperada (`analysis/h5_caso_metroriel.sql`):** las cinco barras azules son las **cinco primeras**
  (Z17 148 554, Z12 147 903, Z08 147 081, Z06 138 899, Z01 137 170); suman **719 607 = 43,68 %** del total.
  `pct_metroriel` entre 36,19 (Z17) y 48,28 (Z06). Primera zona gris: Mixco (6.ª, 132 768). 83,54 % de los 295 511
  viajes de MetroRiel cambian de zona.

## 7. H6 · KPIs (texto grande, una hoja por KPI o una hoja con `Nombres de medida`)

| KPI | Fuente | Campo / fórmula | Cifra esperada (`analysis/h6_kpis.sql`) |
|---|---|---|---|
| Viajes del mes (junio 2026) | `.tds` | `Viajes del mes` con `[Mes de referencia] = "2026-06"` | **1 093 235** (= `viajes_del_mes_a/b.sql`) |
| Viajes 45 días | `.tds` o `agg_demanda` | `Viajes` | 1 647 569 |
| Usuarios activos (30 d) | `.tds` | `Usuarios activos (30 d)` | **53 820 personas** (110 762 tarjetas si se usa `[usuario_sk]`) |
| Zonas sin servicio | `agg_cobertura` | `Zonas sin servicio` | **11** de 26 |
| % Multimodal | `agg_transbordo_resumen` | `% Multimodal` | **72,98 %** (41 485 personas) |

Formato: fuente 28–36 pt, título del KPI arriba, subtítulo con la definición (p. ej. "tarjetas con ≥ 1 viaje entre
2026-06-16 y 2026-07-15"). El KPI de viajes responde a los filtros globales; los otros tres no (ver §8).

## 8. Dashboard "Red Metropolitana · demanda, cobertura, transbordo y MetroRiel"

- Tamaño 1400 × 900 (o automático). Disposición: fila superior H6 (cinco KPIs); fila media H1 (izquierda) y H2
  (derecha); fila inferior H3, H4, H5a.
- **Filtros globales** (mostrar como tarjetas a la derecha, "Aplicar a hojas relacionadas → todas las que usen
  esta fuente"): `fecha` (rango, `agg_demanda`), `modo_id` (lista múltiple), `es_dia_habil` (verdadero/falso).
  Como H3, H4 y H5 usan agregados sin fecha, indicar en el subtítulo "Cobertura, transbordo y caso MetroRiel
  cubren los 45 días (2026-06-01 … 2026-07-15) y no cambian con los filtros de fecha".
- **Acciones:** al seleccionar una zona en H2 → filtra H1 (misma fuente) y resalta la zona en H5a (acción de
  resaltado por `zona_id`).
- Nota al pie con el linaje (§9) y la fecha del build de Gold (2026-09-20, `docs/evidence/gold_resumen.md`).

## 9. Linaje: de una cifra del tablero al archivo crudo

Cada fila de `fct_abordaje` lleva `fuente_sk`, `fuente`, `archivo`, `objeto_gcs`, `ingest_date` y, en streaming,
`linea_num` y `kafka_offset`. Camino de una cifra:

1. **Cifra del tablero** (p. ej. H2 filtrada a `fecha = 2026-06-01`, `modo_id = TM`, `zona_id = GT-Z17`: 725 viajes).
2. **Gold:** en el `.tds`, hoja de detalle con Filas `fuente_sk`, `objeto_gcs`, `MIN([kafka_offset])`,
   `MAX([kafka_offset])` y `Viajes`: la cifra se reparte en 2 objetos (388 + 337 = 725) sin pérdida.
3. **`dim_fuente`** (unir por `fuente_sk`, o leer las columnas desnormalizadas): `fuente = transmetro_validaciones`
   (= nombre de la tabla externa Hive `bronze.transmetro_validaciones`), `archivo = transmetro_validaciones.csv`,
   `objeto_gcs = gs://cienciadatos-509301-lake/bronze/transmetro_validaciones/ingest_date=2026-09-20/topico=transmetro.validaciones/particion=1/offsets=000000000000-000000004999.jsonl`,
   `ingest_date = 2026-09-20`, `n_filas_silver = 4 980`.
4. **Bronze / GCS:** el objeto `.jsonl` contiene los mensajes de Kafka (offsets 3 … 4 985) con el `linea_num` de la
   línea original del CSV del operador (líneas 4 … 4 986). En batch (Transurbano, MetroRiel) el objeto es el propio
   archivo CSV en su partición `ingest_date=`.
5. **Verificación SQL:** `analysis/h7_linaje_de_una_cifra.sql` (0,17 s, 4,2 MB gracias a partición por `fecha` y
   cluster por `modo_id, zona_id`).

Dirección inversa (auditoría): `dim_fuente.n_filas_silver` por objeto = filas válidas; la conciliación
staging = silver + cuarentena está en `docs/evidence/calidad_resumen.md`.

## 10. Qué no se pudo verificar

- El tablero no se construyó ni se abrió en Tableau Desktop desde este entorno (no disponible); la guía describe la
  configuración y cada cifra proviene de SQL ejecutado en BigQuery. Al reproducirlo, cualquier diferencia entre la
  cifra de Tableau y la del SQL debe tratarse como defecto (joins duplicando filas, filtros de contexto, caché).
- La validez sintáctica del `.tds` ante Tableau (ver advertencia en `docs/tableau/README.md`).
