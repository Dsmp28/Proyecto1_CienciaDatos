# Tableau Desktop → BigQuery `gold`

Tableau se conecta **solo** a la capa Gold (`cienciadatos-509301.gold`, región `us-central1`), nunca a Silver ni a
Bronze (CLAUDE.md, stack). Todas las cifras del tablero se verifican con los SQL de `analysis/` (ver
`docs/tableau/GUIA_TABLERO.md` y `docs/evidence/tablero_resumen.md`).

## Archivos

| Archivo | Qué es |
|---|---|
| `red_metropolitana_gold.tds` | Fuente de datos de Tableau (XML) con el conector nativo de Google BigQuery, sin credenciales: estrella `fct_abordaje` × `dim_tiempo`, `dim_modo`, `dim_zona`, `dim_estacion`, `dim_usuario` |
| `GUIA_TABLERO.md` | Guía hoja por hoja (H1–H6 + dashboard): tablas, campos, filtros, gráfico, campos calculados y cifra esperada |
| `../../analysis/h1…h8*.sql` | SQL de verificación de cada hoja, ejecutados en BigQuery con tiempo y bytes |

## Requisitos

- Tableau Desktop 2021.1 o posterior (el conector de Google BigQuery viene incluido; no hace falta driver).
- Una cuenta de Google con permiso `BigQuery Data Viewer` sobre el dataset `gold` y `BigQuery Job User` sobre el
  proyecto `cienciadatos-509301` (los jobs se facturan a ese proyecto). La cuenta que corre el pipeline con ADC ya
  tiene ambos roles; cualquier otra cuenta debe recibirlos en IAM antes de abrir el tablero.
- Sin Tableau Prep, sin extractos obligatorios: conexión **en vivo** (BigQuery responde en < 5 s a todas las consultas
  del tablero, `docs/evidence/tablero_resumen.md`). Puede crearse un extracto para trabajar sin conexión.

## Opción A · Abrir el archivo `.tds`

1. Doble clic en `docs/tableau/red_metropolitana_gold.tds` (o en Tableau: **Archivo → Abrir**).
2. Tableau muestra el cuadro de inicio de sesión de Google BigQuery. Elegir **Iniciar sesión con OAuth**, autenticar
   con la cuenta de Google y aceptar los permisos de BigQuery. El archivo no contiene contraseñas ni tokens.
3. Si aparece "no se pudo conectar" o el proyecto de facturación sale vacío: **Datos → `Red Metropolitana · Gold
   (BigQuery)` → Editar conexión…** y seleccionar Proyecto de facturación `cienciadatos-509301`, Proyecto
   `cienciadatos-509301`, Dataset `gold`. Al aceptar, el diagrama de joins (fct_abordaje al centro) se conserva.
4. Verificar en la pestaña **Fuente de datos** que aparecen las seis tablas y que la vista previa carga filas.

> Advertencia sobre validez: el `.tds` se escribió a mano siguiendo el ejemplo oficial de atributos de conexión de
> BigQuery de la documentación de Tableau (`class='bigquery'`, `connection-dialect='google-bql'`, `CATALOG`,
> `EXECCATALOG`, `project`, `schema`) y la estructura de joins estándar de los archivos `.tds`. **No se pudo abrir en
> Tableau Desktop desde este entorno.** Si Tableau rechaza el archivo, usar la opción B (dos minutos) y, si se desea,
> guardar la fuente resultante con **Datos → Agregar a fuentes guardadas** para reemplazar este `.tds`.

## Opción B · Conexión manual (siempre funciona)

1. Tableau Desktop → panel **Conectar → A un servidor → Google BigQuery**.
2. Autenticación: **Iniciar sesión con OAuth** → cuenta de Google → **Permitir**.
3. En la pestaña Fuente de datos:
   - **Proyecto de facturación:** `cienciadatos-509301`
   - **Proyecto:** `cienciadatos-509301`
   - **Conjunto de datos:** `gold`
4. Arrastrar `fct_abordaje` al lienzo. Luego arrastrar cada dimensión y confirmar el join (Tableau lo propone por
   nombre de columna; si no, elegirlo a mano):

   | Tabla | Join | Condición |
   |---|---|---|
   | `dim_tiempo` | interno | `fct_abordaje.tiempo_sk = dim_tiempo.tiempo_sk` |
   | `dim_modo` | izquierdo | `fct_abordaje.modo_id = dim_modo.modo_id` |
   | `dim_zona` | izquierdo | `fct_abordaje.zona_id = dim_zona.zona_id` |
   | `dim_estacion` | izquierdo | `fct_abordaje.estacion_sk = dim_estacion.estacion_sk` |
   | `dim_usuario` | izquierdo | `fct_abordaje.usuario_sk = dim_usuario.usuario_sk` |

   Con Tableau 2020.2+ pueden usarse **relaciones** (capa lógica) en lugar de joins físicos, con las mismas llaves;
   el resultado es idéntico para el tablero porque todas las FK existen (pruebas `relationships` de dbt en PASS).
5. Dejar **En vivo**. Nombrar la fuente `Red Metropolitana · Gold (BigQuery)`.
6. Repetir **Conectar → Google BigQuery** para cada agregado que la guía use como fuente independiente (más rápido
   que la estrella completa): `agg_demanda_modo_zona_hora`, `agg_cobertura_zona`, `agg_transbordo_resumen`,
   `agg_metroriel_zonas`, `agg_transbordo`. Son tablas pequeñas (26 a 56 848 filas) pensadas para Tableau.

## Notas

- Ubicación del dataset: `us-central1`. El conector la detecta automáticamente; no hay que configurarla.
- `fct_abordaje` está particionada por `fecha` y agrupada por `modo_id, zona_id`: los filtros de fecha y modo del
  dashboard reducen los bytes leídos (H7 lee 4,2 MB de 1,65 M de filas).
- Costo: consultas del tablero entre 0,3 MB y 257 MB procesados; muy por debajo del TB gratuito mensual.
- Nunca conectar a `silver`, `staging` ni `bronze` desde Tableau: rompe la restricción "Tableau → Gold únicamente".
