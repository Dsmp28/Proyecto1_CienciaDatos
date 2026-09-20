# Definiciones oficiales y dueños por dominio

Entregable 3.1. Los cuatro operadores miden distinto; la Agencia fija aquí una sola definición
por concepto. Toda cifra del tablero, de `docs/METRICAS.md` y de la recomendación usa estas
definiciones. Cambiarlas requiere la autorización del dueño indicado y un ADR en `docs/DECISIONS.md`.

## 1. Un viaje
**Definición oficial:** *un viaje es un abordaje válido*: una validación de tarjeta de un usuario en un
modo, en una estación o parada, en un instante, que superó todas las reglas de calidad
(`docs/governance/reglas_calidad.md`) y por tanto existe en `silver.abordajes` y en `gold.fct_abordaje`.

Cómo se traduce por operador:

| Operador | Lo que entrega | Cómo cuenta como viaje |
|---|---|---|
| Transmetro | una validación de torniquete | 1 validación válida = 1 viaje. Los duplicados de torniquete (misma `validacion_id`, fila completa repetida por el lector; regla R01) cuentan una sola vez: se conserva la primera aparición y el resto va a cuarentena |
| Transurbano | una transacción de cobro | 1 transacción válida = 1 viaje |
| MetroRiel | un viaje cerrado (entrada y salida) | 1 viaje cerrado = 1 viaje (su entrada es el abordaje). Un viaje sin salida (R04) va a cuarentena y **no** cuenta |
| Aerómetro | un boarding | 1 boarding válido = 1 viaje |

Consecuencias: los transbordos entre modos cuentan como viajes separados (un usuario que toma Transmetro y luego
MetroRiel hizo 2 viajes). Esta es la definición que permite comparar los cuatro modos sin inferencias; el
"viaje puerta a puerta" es un análisis derivado (extra opcional), no la definición oficial.

**Prueba de fuego:** `analysis/viajes_del_mes_a.sql` (desde `gold.fct_abordaje` × `dim_tiempo`) y
`analysis/viajes_del_mes_b.sql` (desde `gold.fct_uso_usuario_dia`) deben devolver el mismo número para el mismo mes.

## 2. Un usuario activo
**Definición oficial:** *un usuario está activo en una fecha de referencia si tiene al menos un viaje (según la
definición 1) en los 30 días anteriores a esa fecha, inclusive.* La fecha de referencia es el parámetro fijo del
pipeline (`var('fecha_referencia')`), nunca la fecha del sistema.

- Además, la persona no debe estar dada de baja en el padrón central (ADR-009: el padrón describe personas, no un
  solo operador; su estado se propaga a todas sus tarjetas por la identidad unificada). Una tarjeta dada de baja
  (DELETE del CDC) conserva su historial de viajes pero no cuenta como usuario activo.
- Para los otros tres operadores no existe padrón: "usuario" es la llave distinta observada en sus archivos de operación.
- "Usuario" se cuenta a nivel de **persona** (identidad unificada `usuario_unificado_sk`, ADR-008) en todos los KPI
  y en las features; el conteo por tarjeta seudonimizada (`usuario_sk`) se reporta solo como detalle. Con la fecha de
  referencia 2026-07-16 la ventana es 2026-06-16 a 2026-07-15 y el resultado oficial es **53 820 personas activas**
  (110 762 tarjetas), calculado igual en `analysis/h6_kpis.sql` y en `features.usuario_features`.

## 3. Dueños por dominio

| Dimensión conformada / concepto | Dueño (responde por la definición) | Quién autoriza cambios |
|---|---|---|
| `dim_zona` (mapeo Z10 / Zona 10 / district → zona canónica) | Agencia · Planificación territorial | Comité de datos de la Agencia (Planificación + Ingeniería de datos) con ADR |
| `dim_tiempo` (día hábil, hora pico, feriados) | Agencia · Planificación de operación | Comité de datos; los operadores son consultados |
| `dim_estacion` (catálogo unificado) | Cada operador para su código nativo; Agencia para la conformación y la zona asignada | Operador para altas/bajas propias; Agencia para el mapeo a zona |
| `dim_modo` | Agencia · Arquitectura de datos | Comité de datos |
| `dim_usuario` y seudonimización (sal HMAC) | Transmetro para el padrón; Agencia · Seguridad de la información para la sal y su rotación | Oficial de protección de datos de la Agencia |
| Definición de "un viaje" y "usuario activo" | Agencia · Ingeniería de datos | Comité de datos con ADR |
| Reglas de calidad y cuarentena | Agencia · Ingeniería de datos | Comité de datos; cada operador es notificado de sus conteos |

Ejemplo del enunciado: si mañana cambia la definición de zona (p. ej. se subdivide la Zona 18), Planificación
territorial propone, el Comité de datos autoriza, se versiona el seed `zonas_mapeo.csv`, se registra el ADR y se
reconstruye Gold. Sin ese flujo, cada operador seguiría midiendo a su manera.

## 4. Linaje
Cada métrica del tablero llega hasta el archivo crudo por las columnas `fuente`, `archivo`, `fecha_ingesta`
(y `kafka_offset` para streaming) presentes en Silver y en Gold (`dim_fuente`), y por el grafo de `dbt docs`
(`docs/evidence/dbt_docs/`).
