# Grano y matriz del bus

> Escrito antes de cualquier tabla, siguiendo la advertencia del enunciado. Lo marcado
> *[verificar en generador]* se revisa en F1 al leer `generar_red_metropolitana.py`.

## 1. Grano de la tabla de hechos principal

**`fct_abordaje`: una fila es una validación de una tarjeta de un usuario en un modo, en una estación o parada, en un instante.**

### Defensa frente a la alternativa "un viaje puerta a puerta"

| Criterio | Un abordaje (elegido) | Un viaje puerta a puerta |
|---|---|---|
| Fuentes que lo entregan de forma nativa | 3 de 4 (Transmetro, Transurbano, Aerómetro) | 1 de 4 (MetroRiel) |
| Inferencia requerida | Ninguna | Ventanas de tiempo y proximidad para 3 sistemas, no verificables con datos generados |
| Preguntas del tablero | Demanda por modo/zona/hora, cobertura y caso MetroRiel salen directo; transbordo por usuario con `fct_uso_usuario_dia` | Igual, pero cada cifra hereda el error de la inferencia |
| Principio Kimball | Grano más atómico disponible; nunca se pierde capacidad de agregar | Grano derivado; no se puede volver al detalle |

**Qué pasa con MetroRiel.** No se desperdicia: cada viaje aporta su *entrada* (estación y hora de entrada) como
un abordaje a `fct_abordaje`, y el viaje completo (entrada, salida, duración, tarifa) se conserva en
`fct_viaje_metroriel`. Así el caso MetroRiel (zonas 12, 8, 1, 6 y 17) se analiza con origen–destino real.
La inferencia de viajes multimodales queda como extra opcional sin tocar el grano principal.

## 2. Dimensiones conformadas

| Dimensión | Grano | Atributos clave | Dueño (gobernanza) |
|---|---|---|---|
| `dim_tiempo` | una hora de un día | fecha, hora del día (0–23), día de semana, `es_dia_habil`, `es_hora_pico`, `franja` | Agencia / Planificación (seeds `franjas_horarias`, `feriados_gt`) |
| `dim_modo` | un operador | `modo_id` (TM, TU, MR, AM), nombre, tipo (BRT, bus, tren ligero, teleférico), vía de ingesta | Agencia / Arquitectura de datos |
| `dim_estacion` | una estación o parada de cualquier modo | `estacion_sk`, modo, código nativo, nombre, línea/ruta/eje, `zona_sk`, lat/lon *[verificar]* | Cada operador (código nativo); Agencia (conformación) |
| `dim_zona` | una zona conformada | `zona_sk`, `zona_num`, nombre canónico "Zona N", municipio, formas de origen (`Z10`, `Zona 10`, `district`) | Agencia / Planificación (seed versionado `zonas_mapeo`) |
| `dim_usuario` | una tarjeta seudonimizada (por modo) | `usuario_sk` (HMAC), modo de origen, `usuario_unificado_sk` (solo si hay vínculo determinista), atributos SCD2 del padrón **solo Transmetro** (`vigente_desde`, `vigente_hasta`, `activo`) | Transmetro (padrón); Agencia (seudonimización) |
| `dim_fuente` | un archivo crudo ingerido | `fuente_sk`, fuente, archivo, vía (batch/streaming/cdc), `fecha_ingesta`, `run_id`, sha256 | Agencia / Ingeniería de datos (linaje) |

## 3. Matriz del bus

| Proceso de negocio (hecho) | Grano | tiempo | modo | estación | zona | usuario | fuente | Tipo de hecho |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|---|
| `fct_abordaje` | un abordaje, 4 modos | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | transacción |
| `fct_viaje_metroriel` | un viaje cerrado de MetroRiel | ✔ entrada y salida | ✔ | ✔ origen y destino (role-playing) | ✔ origen y destino | ✔ | ✔ | transacción |
| `fct_uso_usuario_dia` | usuario × día × modo | ✔ día | ✔ | | | ✔ | ✔ | snapshot periódico |
| `fct_cobertura_zona_modo` | zona × modo con al menos una estación/parada | | ✔ | | ✔ | | ✔ | factless |
| `fct_cambio_padron` | una operación CDC aplicada al padrón | ✔ | ✔ (TM) | | | ✔ | ✔ | transacción |

### Cómo responde el tablero sin tocar Silver
- **Demanda por modo, zona y hora:** `fct_abordaje` × `dim_tiempo` × `dim_zona` × `dim_modo`.
- **Cobertura (zonas sin servicio de ningún modo):** `dim_zona` LEFT JOIN `fct_cobertura_zona_modo`; zona sin fila = sin servicio. Se contrasta con abordajes reales por zona (zonas con estación pero sin demanda).
- **Transbordo (usuarios con más de un sistema):** `fct_uso_usuario_dia` agrupado por `usuario_unificado_sk` → `COUNT(DISTINCT modo) > 1`. Depende de ADR-008.
- **Caso MetroRiel:** abordajes por zona en 12, 8, 1, 6, 17 frente al resto, más origen–destino de `fct_viaje_metroriel`.

## 4. Clasificación de medidas

| Medida | Hecho | Clase | Por qué |
|---|---|---|---|
| `abordajes` (conteo) | `fct_abordaje`, `fct_uso_usuario_dia` | aditiva | se suma por cualquier dimensión |
| `monto_q` | `fct_abordaje`, `fct_uso_usuario_dia` | aditiva | quetzales; se suma en todas las dimensiones |
| `duracion_min` | `fct_viaje_metroriel` | aditiva | se suma entre viajes (útil como total de minutos a bordo) |
| `tarjetas_activas` | `fct_cambio_padron` | semi aditiva | es un saldo: se suma entre usuarios, no en el tiempo |
| `usuarios_activos_dia` | `fct_uso_usuario_dia` | semi aditiva | se suma entre modos/zonas de un día, no entre días |
| `usuarios_distintos` | derivada | no aditiva | `COUNT(DISTINCT)`; no se suma por ninguna dimensión |
| `monto_promedio_por_abordaje` | derivada | no aditiva | cociente; se recalcula desde sumas |
| `proporcion_hora_pico` | derivada | no aditiva | cociente |
| `duracion_promedio` | derivada de `fct_viaje_metroriel` | no aditiva | cociente |
| `tiene_servicio` | `fct_cobertura_zona_modo` | factless (conteo de existencia) | no hay medida numérica; se cuenta la fila |
