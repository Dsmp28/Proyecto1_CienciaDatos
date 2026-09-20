# Evidencia F4 · Gold dimensional

Corrida: `dbt build --select tag:gold` (dbt-core 1.12.5, dbt-bigquery 1.12.1, BigQuery `cienciadatos-509301`, `us-central1`),
2026-09-20, `fecha_referencia = 2026-07-16`, `run_id = manual`. Fuente de las cifras: consultas directas a `gold.*`
tras la corrida 1; la corrida 2 produjo conteos idénticos (§3). Modelo: `docs/modelo/matriz_bus.md`,
`docs/modelo/modelo_gold.mmd`; DDL real: `docs/modelo/ddl_gold.sql`; diccionario: `docs/governance/diccionario_gold.md`.

## 1. Resultado del build (dos corridas)

| Corrida | Modelos | Pruebas | Resultado | Tiempo |
|---|---|---|---|---|
| 1 | 17 tablas (7 `dim_*`, 5 `fct_*`, 5 `agg_*`) | 197 (193 genéricas + 4 singulares) | PASS=214 WARN=0 ERROR=0 SKIP=0 | 2 min 41 s (160,96 s) |
| 2 | 17 tablas | 197 | PASS=214 WARN=0 ERROR=0 SKIP=0 | 2 min 48 s (168,01 s) |

- `dbt parse` sin errores. `dbt docs generate` genera `manifest.json` y `catalog.json` (base del diccionario).
- `pytest -q tests/test_gold_lineage.py tests/test_no_current_date.py`: **4 passed** (ningún modelo de Gold tiene un
  padre en staging ni en sources; ningún SQL usa la fecha del sistema). Antes de F4 `test_gold_existe` fallaba por no
  existir Gold.
- Pruebas singulares (`dbt/tests/gold/`): `assert_gold_sin_llaves_nativas` (INFORMATION_SCHEMA.COLUMNS de `gold`
  sin `llave_nativa`, `tarjeta`, `num_tarjeta`, `card`, `user_hash`, `usuario_base_id`),
  `assert_abordajes_gold_igual_silver` (total y por modo), `assert_viajes_del_mes_dos_caminos`,
  `assert_saldo_tarjetas_activas_igual_vigentes`. Las cuatro en PASS.

## 2. Conteos por tabla de Gold (corrida 1)

| Tabla | Tipo | Filas | Comprobación |
|---|---|---:|---|
| `dim_tiempo` | dimensión | 1 080 | 45 días (2026-06-01…2026-07-15) × 24 horas |
| `dim_modo` | dimensión | 4 | 4 modos fijos |
| `dim_zona` | dimensión | 26 | = seed `zonas` (26, incluidas 11 sin servicio) |
| `dim_estacion` | dimensión | 468 | = `silver_estaciones` (104 TM + 328 TU + 22 MR + 14 AM) |
| `dim_usuario` | dimensión | 117 205 | = `silver_usuarios` (43 257 TM + 36 567 TU + 22 885 MR + 14 496 AM) |
| `dim_padron_historia` | dimensión | 28 844 | = `silver_padron_scd2` |
| `dim_fuente` | dimensión | 121 | 73 objetos TM + 41 AM + 7 archivos batch/CDC/catálogos |
| `fct_abordaje` | hecho | 1 647 569 | = `silver_abordajes` (362 106 TM + 786 398 TU + 295 511 MR + 203 554 AM) |
| `fct_viaje_metroriel` | hecho | 295 511 | = `silver_metroriel_viajes` |
| `fct_uso_usuario_dia` | hecho | 1 376 322 | tarjeta × día × modo |
| `fct_cobertura_zona_modo` | hecho | 44 | pares (zona, modo) con estación |
| `fct_cambio_padron` | hecho | 28 844 | = operaciones CDC válidas |
| `agg_demanda_modo_zona_hora` | agregado | 37 619 | celdas fecha × hora × modo × zona |
| `agg_cobertura_zona` | agregado | 26 | = dim_zona |
| `agg_transbordo` | agregado | 56 848 | personas con vínculo (ADR-008: 56 848) |
| `agg_transbordo_resumen` | agregado | 4 | n_modos 1…4 |
| `agg_metroriel_zonas` | agregado | 26 | = dim_zona |

## 3. Idempotencia: corrida 1 vs corrida 2

`SELECT table_id, row_count FROM gold.__TABLES__` después de cada corrida: **las 17 tablas tienen conteos idénticos**
(diferencia 0 en todas; total 3 590 561 filas en ambas). Los seudónimos HMAC son estables mientras la sal no rote (ADR-007).

## 4. Prueba de fuego de gobernanza: "viajes del mes" por dos caminos (junio 2026)

Definición oficial (`docs/governance/definiciones_oficiales.md` §1): un viaje = un abordaje válido.

| Camino | Consulta | Viajes 2026-06 | Tiempo del job (sin caché) | Bytes |
|---|---|---:|---:|---:|
| A | `analysis/viajes_del_mes_a.sql`: `gold.fct_abordaje` × `gold.dim_tiempo` (`anio_mes = '2026-06'`) | **1 093 235** | 0,662 s (5 735 slot-ms) | 168,1 MB |
| B | `analysis/viajes_del_mes_b.sql`: `gold.fct_uso_usuario_dia` (`SUM(abordajes)` en junio) | **1 093 235** | 0,345 s (2 924 slot-ms) | 93,2 MB |

Por modo, ambos caminos: AM 133 892 · MR 195 236 · TM 243 073 · TU 521 034 (monto Q 1 817 256,35; 117 069 tarjetas
distintas). `fct_uso_usuario_dia` se construye desde Silver, no desde `fct_abordaje`, por lo que los caminos son
independientes. La prueba `assert_viajes_del_mes_dos_caminos` lo verifica en cada build; se reconfirmó tras la corrida 2.

## 5. Cobertura: zonas sin servicio (`gold.agg_cobertura_zona`)

| Zona | Tipo | Modos con servicio | Estaciones | Abordajes | Usuarios distintos | Sin servicio |
|---|---|---|---:|---:|---:|---|
| Zona 1 (`GT-Z01`) | zona_ciudad | AM,MR,TM,TU | 31 | 137 170 | 73 221 | no |
| Zona 2 (`GT-Z02`) | zona_ciudad | — | 0 | 0 | 0 | **sí** |
| Zona 3 (`GT-Z03`) | zona_ciudad | — | 0 | 0 | 0 | **sí** |
| Zona 4 (`GT-Z04`) | zona_ciudad | TM,TU | 29 | 77 918 | 47 713 | no |
| Zona 5 (`GT-Z05`) | zona_ciudad | — | 0 | 0 | 0 | **sí** |
| Zona 6 (`GT-Z06`) | zona_ciudad | MR,TM,TU | 32 | 138 899 | 65 871 | no |
| Zona 7 (`GT-Z07`) | zona_ciudad | AM,TM,TU | 31 | 117 431 | 58 263 | no |
| Zona 8 (`GT-Z08`) | zona_ciudad | MR,TM,TU | 35 | 147 081 | 69 813 | no |
| Zona 9 (`GT-Z09`) | zona_ciudad | TM,TU | 29 | 76 363 | 45 237 | no |
| Zona 10 (`GT-Z10`) | zona_ciudad | TM,TU | 29 | 75 304 | 44 859 | no |
| Zona 11 (`GT-Z11`) | zona_ciudad | TM,TU | 32 | 85 943 | 49 554 | no |
| Zona 12 (`GT-Z12`) | zona_ciudad | AM,MR,TM,TU | 35 | 147 903 | 76 841 | no |
| Zona 13 (`GT-Z13`) | zona_ciudad | AM,TM,TU | 31 | 94 131 | 56 354 | no |
| Zona 14 (`GT-Z14`) | zona_ciudad | — | 0 | 0 | 0 | **sí** |
| Zona 15 (`GT-Z15`) | zona_ciudad | — | 0 | 0 | 0 | **sí** |
| Zona 16 (`GT-Z16`) | zona_ciudad | — | 0 | 0 | 0 | **sí** |
| Zona 17 (`GT-Z17`) | zona_ciudad | AM,MR,TM,TU | 35 | 148 554 | 78 226 | no |
| Zona 18 (`GT-Z18`) | zona_ciudad | AM,TM,TU | 30 | 91 842 | 55 599 | no |
| Zona 19 (`GT-Z19`) | zona_ciudad | — | 0 | 0 | 0 | **sí** |
| Zona 21 (`GT-Z21`) | zona_ciudad | — | 0 | 0 | 0 | **sí** |
| Zona 24 (`GT-Z24`) | zona_ciudad | — | 0 | 0 | 0 | **sí** |
| Zona 25 (`GT-Z25`) | zona_ciudad | — | 0 | 0 | 0 | **sí** |
| Mixco (`GT-MIXCO`) | municipio | AM,TM,TU | 32 | 132 768 | 60 236 | no |
| Villa Nueva (`GT-VILLA-NUEVA`) | municipio | AM,TM,TU | 30 | 93 005 | 57 112 | no |
| San Miguel Petapa (`GT-SAN-MIGUEL-PETAPA`) | municipio | AM,TM,TU | 27 | 83 257 | 52 339 | no |
| Santa Catarina Pinula (`GT-SANTA-CATARINA-PINULA`) | municipio | — | 0 | 0 | 0 | **sí** |

**11 zonas sin servicio de ningún modo** (26 en `dim_zona` − 15 con al menos una estación): las zonas 2, 3, 5, 14, 15, 16,
19, 21, 24 y 25 de la ciudad y el municipio de Santa Catarina Pinula (`sin_servicio = true`).
Ninguna zona tiene estaciones sin demanda (`tiene_estacion_sin_demanda = false` en todas): oferta y operación coinciden.
Cobertura por modo: TM y TU llegan a 15 zonas, AM a 9, MR a 5 (`fct_cobertura_zona_modo`: 44 pares zona-modo).

## 6. Transbordo: usuarios por número de modos (`gold.agg_transbordo_resumen`)

| Modos usados | Personas | % | Abordajes | Abordajes / persona | Combinación más frecuente |
|---:|---:|---:|---:|---:|---|
| 1 | 15 363 | 27,02 % | 204 814 | 13,33 | TM (7 822) |
| 2 | 25 048 | 44,06 % | 707 002 | 28,23 | TM,TU (12 477) |
| 3 | 14 004 | 24,63 % | 596 859 | 42,62 | MR,TM,TU (7 563) |
| 4 | 2 433 | 4,28 % | 138 894 | 57,09 | AM,MR,TM,TU (2 433) |

Total de personas con vínculo (`usuario_unificado_sk`): 56 848; **41 485 (72,98 %) usan más de un sistema**. Coincide con
el resultado medido en ADR-008 (56 848 personas; 2 sistemas 25 048; 3: 14 004; 4: 2 433), ahora calculado íntegramente
en Gold sobre seudónimos.

## 7. Caso MetroRiel (`gold.agg_metroriel_zonas`, zonas 12, 8, 1, 6 y 17)

| Ranking | Zona | Zona MetroRiel | Estaciones MR | TM | TU | MR | AM | Total | % MetroRiel |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | GT-Z17 | sí | 4 | 27 870 | 52 617 | 53 755 | 14 312 | 148 554 | 36,19 |
| 2 | GT-Z12 | sí | 4 | 24 277 | 55 057 | 53 970 | 14 599 | 147 903 | 36,49 |
| 3 | GT-Z08 | sí | 5 | 27 891 | 52 266 | 66 924 | 0 | 147 081 | 45,5 |
| 4 | GT-Z06 | sí | 5 | 21 181 | 50 659 | 67 059 | 0 | 138 899 | 48,28 |
| 5 | GT-Z01 | sí | 4 | 20 835 | 48 022 | 53 803 | 14 510 | 137 170 | 39,22 |
| 6 | GT-MIXCO | no | 0 | 24 263 | 50 598 | 0 | 57 907 | 132 768 | 0,0 |
| 7 | GT-Z07 | no | 0 | 20 743 | 52 880 | 0 | 43 808 | 117 431 | 0,0 |
| 8 | GT-Z13 | no | 0 | 24 646 | 54 713 | 0 | 14 772 | 94 131 | 0,0 |
| 9 | GT-VILLA-NUEVA | no | 0 | 27 937 | 50 405 | 0 | 14 663 | 93 005 | 0,0 |
| 10 | GT-Z18 | no | 0 | 24 416 | 52 926 | 0 | 14 500 | 91 842 | 0,0 |

Las cinco zonas de MetroRiel ocupan los cinco primeros puestos de demanda total; en ellas MetroRiel aporta entre el 36 % y
el 48 % de los abordajes. (Se muestran las 10 primeras de 26; el resto está en la tabla.)

## 8. Padrón historizado (`gold.fct_cambio_padron`, `gold.dim_padron_historia`)

28 844 operaciones CDC (10 003 INSERT, 15 069 UPDATE, 3 772 DELETE). Saldo de tarjetas activas (`tarjetas_activas_despues`,
semi aditiva): mínimo 1, máximo 19 499, **final 19 469** = tarjetas vigentes con estado ACTIVA en `dim_padron_historia`
(prueba `assert_saldo_tarjetas_activas_igual_vigentes`). Las bajas se conservan como versiones INACTIVA (historizar, no borrar).

## 9. Seguridad y linaje
- `assert_gold_sin_llaves_nativas`: 0 columnas con llave nativa o `usuario_base_id` en las 17 tablas de `gold`
  (`dim_usuario` y `dim_padron_historia` salen de Silver sin esas columnas).
- Linaje: cada hecho lleva `fuente_sk` → `dim_fuente` (121 objetos crudos: fuente, archivo, `gs://` de Bronze, `ingest_date`)
  y `fct_abordaje` conserva además `archivo`, `objeto_gcs`, `ingest_date`, `linea_num`, `kafka_offset`. El grafo de
  `dbt docs` muestra que todo nodo de Gold desciende solo de Silver, seeds u otro Gold.

## 10. No verificado en esta fase
- Conexión de Tableau a `gold` (F6) y rendimiento real de las consultas del tablero con partición/clustering.
- Ejecución de Gold desde el DAG de Airflow en la VM (F5): aquí se corrió desde la laptop con ADC.
- Rotación de la sal HMAC (cambiaría todos los seudónimos; exige reconstruir Gold).
