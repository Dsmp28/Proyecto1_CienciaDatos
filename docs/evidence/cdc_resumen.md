# Resumen del CDC del padrón (rúbrica 1.2) y catálogos mínimos de usuarios

Fuente: `SELECT * FROM staging.stg_padron_cdc_resumen` (dbt build de `tag:staging`, 2026-09-21 04:29 UTC, 94/94 PASS).
Modelos: `dbt/models/staging/stg_cdc_padron_usuarios.sql` (log tipado, ADR-008), `stg_padron_cdc_aplicado.sql`
(padrón vigente por tarjeta, ADR-009) y `stg_padron_cdc_resumen.sql` (esta tabla). Los números se verificaron con una
consulta ad hoc independiente sobre `stg_cdc_padron_usuarios` (ARRAY_AGG de operaciones por tarjeta ordenadas por `seq`)
y coinciden uno a uno.

## Tabla del resumen

| métrica | valor | qué mide |
|---|---:|---|
| `ops_total` | 31 050 | Operaciones en el log (= filas en Bronze `cdc_padron_usuarios`). |
| `inserts` | 10 800 | Operaciones `INSERT`. |
| `updates` | 16 200 | Operaciones `UPDATE`. |
| `deletes` | 4 050 | Operaciones `DELETE` (llegan sin cuerpo). |
| `filas_sin_tarjeta` | 2 206 | Operaciones con `tarjeta = 'SIN-TARJETA'`: no tienen llave, se excluyen del padrón aplicado e irán a cuarentena en Silver (R07). |
| `inserts_sin_tarjeta` | 797 | De las 2 206, las que son `INSERT`. |
| `updates_sin_tarjeta` | 1 131 | De las 2 206, las que son `UPDATE`. |
| `deletes_sin_tarjeta` | 278 | De las 2 206, las que son `DELETE`. |
| `tarjetas_distintas` | 22 462 | Tarjetas distintas con llave (filas de `stg_padron_cdc_aplicado`). |
| `altas_aplicadas` | 7 845 | Tarjetas cuya **primera** operación en `seq` es `INSERT` (alta "limpia"). |
| `altas_implicitas` | 14 617 | Tarjetas cuya primera operación **no** es `INSERT` (`UPDATE` o `DELETE` sobre llave inexistente); se crean igual (ADR-009). |
| `altas_repetidas` | 2 158 | `INSERT` que llegaron cuando la llave ya existía (no son la primera operación de su tarjeta); se aplican como `UPDATE`. En número de operaciones. |
| `tarjetas_con_insert_repetido` | 827 | Tarjetas con más de un `INSERT` (828 en ADR-009: aquel conteo incluía `SIN-TARJETA` como una "tarjeta" más). |
| `cambios_aplicados` | 15 069 | `UPDATE` sobre tarjetas con llave, en número de operaciones. |
| `bajas_aplicadas` | 2 993 | Tarjetas cuya **última** operación es `DELETE` → `estado_actual = 'INACTIVA'`. |
| `bajas_sin_alta_previa` | 3 301 | Tarjetas con al menos un `DELETE` sin ningún `INSERT` antes en la secuencia (coincide con ADR-009). |
| `deletes_sin_alta_previa` | 3 430 | Lo mismo en número de operaciones. |
| `tarjetas_solo_delete` | 2 314 | Tarjetas que solo tienen `DELETE`: nunca estuvieron activas y no tienen `perfil` ni `zona_residencia` (fila inactiva sin atributos, ADR-009). |
| `activas_antes_de_borrados` | 20 148 | Tarjetas con al menos un `INSERT` o `UPDATE`: las que quedarían activas si se ignoraran los `DELETE`. |
| `activas_despues_de_borrados` | 19 469 | Tarjetas con `estado_actual = 'ACTIVA'` tras aplicar los `DELETE` en orden de `seq`. |

Cifras auxiliares (consulta ad hoc sobre `stg_padron_cdc_aplicado`): `DELETE` con llave = 3 772; tarjetas con algún
`DELETE` = 3 628; de ellas 635 quedan `ACTIVA` porque después del `DELETE` llegó un `INSERT`/`UPDATE` con `seq` mayor
(reactivación: la última operación manda); bajas de tarjetas que sí tenían alta = 679.

## Cómo cuadran las cifras

1. Operaciones: `ops_total = inserts + updates + deletes` → 10 800 + 16 200 + 4 050 = **31 050**.
2. Sin tarjeta: `filas_sin_tarjeta = inserts_sin_tarjeta + updates_sin_tarjeta + deletes_sin_tarjeta` → 797 + 1 131 + 278 = **2 206**.
3. INSERT: `inserts = altas_aplicadas + altas_repetidas + inserts_sin_tarjeta` → 7 845 + 2 158 + 797 = **10 800**.
   Cada `INSERT` es o la primera operación de su tarjeta (alta aplicada), o llega sobre llave existente (alta repetida), o no tiene llave.
4. UPDATE: `updates = cambios_aplicados + updates_sin_tarjeta` → 15 069 + 1 131 = **16 200**.
5. DELETE: `deletes = deletes_con_llave + deletes_sin_tarjeta` → 3 772 + 278 = **4 050**.
6. Tarjetas: `tarjetas_distintas = altas_aplicadas + altas_implicitas` → 7 845 + 14 617 = **22 462**
   y también `= activas_despues_de_borrados + bajas_aplicadas` → 19 469 + 2 993 = **22 462** (toda tarjeta es ACTIVA o INACTIVA).
7. Antes de borrados: `activas_antes_de_borrados = tarjetas_distintas − tarjetas_solo_delete` → 22 462 − 2 314 = **20 148**.
8. Después de borrados: `activas_despues = activas_antes − (bajas_aplicadas − tarjetas_solo_delete)` → 20 148 − (2 993 − 2 314) = 20 148 − 679 = **19 469**.
   Es decir, los `DELETE` solo "quitan" 679 tarjetas del conjunto que estaba activo; las otras 2 314 bajas son tombstones de
   llaves que nunca tuvieron alta (se crean inactivas y sin atributos, y se cuentan como anomalía, no como rechazo).
9. Anomalías del log: `bajas_sin_alta_previa` (3 301) ≥ `tarjetas_solo_delete` (2 314): la diferencia (987) son tarjetas cuyo
   `DELETE` llegó antes de un `INSERT` pero que tuvieron algún `INSERT`/`UPDATE` (antes o después). Y `altas_implicitas`
   (14 617) = tarjetas que empiezan por `UPDATE` o `DELETE`; incluye a las 2 314 de solo `DELETE`.

Contraste con ADR-009: 10 800 / 16 200 / 4 050 operaciones, 2 206 `SIN-TARJETA`, 14 617 altas implícitas y 3 301 bajas sin
alta previa coinciden exactamente; 827 tarjetas con `INSERT` repetido frente a 828 del ADR (ver nota en la tabla).
Formatos de la llave (ADR-008): TM 22 326, TU 5 223, MR 1 295, SIN 2 206 (DESCONOCIDO: 0); `usuario_base_id` se extrajo
para el 100 % de las filas con formato TM/TU/MR.

## Catálogos mínimos de usuarios (llaves distintas en los archivos de operación)

Solo `llave`, `operador` y `n_registros` (conteo de filas de operación con esa llave; ningún atributo inventado,
restricción dura 8). `SUM(n_registros)` reproduce el total de filas de cada fuente de operación.

| modelo | operador | llave nativa | llaves distintas | filas de operación (`SUM(n_registros)`) |
|---|---|---|---:|---:|
| `stg_catalogo_usuarios_tm` | TM | `tarjeta` (transmetro_validaciones) | 43 255 | 363 221 |
| `stg_catalogo_usuarios_tu` | TU | `num_tarjeta` (transurbano_transacciones) | 36 567 | 832 791 |
| `stg_catalogo_usuarios_mr` | MR | `card` (metroriel_viajes) | 22 885 | 299 100 |
| `stg_catalogo_usuarios_am` | AM | `user_hash` (aerometro_boardings) | 14 496 | 203 554 |

Los 14 496 `user_hash` de Aerómetro coinciden con la cifra verificada en ADR-008 (14 496 de 14 496 hashes invertibles).

## Comprobaciones de sanidad de Staging (no filtra ni deduplica)

Prueba singular `dbt/tests/staging/assert_staging_igual_bronze.sql`: PASS (las 9 fuentes tienen el mismo `COUNT(*)` en
Bronze y en Staging). Las anomalías inyectadas por el generador se conservan en Staging con el valor esperado en
`docs/governance/reglas_calidad.md`, listas para que Silver las envíe a cuarentena:

| comprobación | valor | esperado |
|---|---:|---:|
| Transurbano `cod_parada` NULL (R02) | 4 189 | 4 189 |
| Transurbano fecha ≥ 2026-07-16 (R03) | 817 | 817 |
| Transurbano cobros no exitosos (estado 7 y 9; se conservan) | 41 649 | 41 649 |
| MetroRiel `tiene_salida = FALSE` (R04) | 3 589 | 3 589 |
| Transmetro `validacion_id` repetidos (R01) | 1 115 | 1 115 |
| Aerómetro `fecha_hora_local − timestamp_utc` | −6 h | −6 h |
| Fechas no parseables (`fecha_hora`/`entry_ts`/`timestamp_utc`/`commit_ts` NULL) | 0 | 0 |
