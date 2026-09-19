# Features de usuario (entregable 2.3)

Tabla lista para entrenar: `features.usuario_features` (BigQuery, proyecto `cienciadatos-509301`), construida por
`dbt/models/features/usuario_features.sql` **solo desde Silver y seeds** (restricción dura 5; prueba
`tests/test_gold_lineage.py::test_features_solo_referencia_silver` sobre `manifest.json`). No es el modelo: es la
matriz de entrada con una fila por entidad y columnas derivadas de su historial.

## Fecha de corte declarada
`fecha_corte = 2026-07-16` (`var('fecha_corte')`, por defecto `var('fecha_referencia')`, ADR-010). Toda fuente se filtra
con `fecha < fecha_corte` (exclusivo): ninguna feature usa datos del día de corte ni posteriores. Nunca `CURRENT_DATE`.
Historial observado: 2026-06-01 a 2026-07-15 (45 días).

| Ventana | Rango real | Estado |
|---|---|---|
| `viajes_7d` | 2026-07-09 a 2026-07-15 | completa |
| `viajes_30d` | 2026-06-16 a 2026-07-15 | completa |
| `viajes_30d_previos` | 2026-05-17 a 2026-06-15 → datos solo desde 2026-06-01 | **truncada (15 de 30 días)** |
| `viajes_90d` | 2026-04-17 a 2026-07-15 → datos solo desde 2026-06-01 | **truncada: igual a `viajes_total`** |

## Grano
**Una fila por persona** = `usuario_unificado_sk`, la identidad unificada de ADR-008 (HMAC-SHA256 con sal secreta
de `BASE|usuario_base_id`). Une las tarjetas de Transmetro, Transurbano, MetroRiel y Aerómetro de la misma persona;
la tabla no lleva ninguna llave nativa. 56 848 filas = todas las personas con al menos un abordaje válido antes del corte.

## Qué se podría predecir y por qué le sirve a la Agencia
**Con esta tabla se podría predecir el abandono (churn) de cada usuario —que no vuelva a viajar en los 30 días
siguientes a la fecha de corte— porque a la Agencia le sirve para dirigir campañas de retención y tarifas integradas a
los usuarios en riesgo antes de que dejen la red, en lugar de descubrir la pérdida de demanda cuando ya ocurrió.**
Se eligió churn sobre demanda por usuario porque la recencia (`dias_desde_ultimo_viaje`), la tendencia
(`tendencia_30_vs_anterior`) y la multimodalidad ya están en la tabla y son las señales clásicas de abandono; la
demanda por usuario (viajes esperados en los próximos 7 días) es la alternativa natural con las mismas features.

### Cómo se construiría la etiqueta (no incluida)
`abandono_30d = (viajes de la persona en [fecha_corte, fecha_corte + 30) = 0)`. Requiere abordajes **posteriores**
al corte, que este lote no contiene (termina el 2026-07-15). Para entrenar con estos mismos datos se mueve el corte
hacia atrás, p. ej. `--vars '{"fecha_corte": "2026-06-16"}'`: las features usan 2026-06-01 a 2026-06-15 y la etiqueta
se calcula con 2026-06-16 a 2026-07-15 desde `silver.silver_abordajes`. Nunca se calcula la etiqueta dentro del modelo
de features para que la tabla no pueda mezclar pasado y futuro.

## Cómo entrenar sin fuga
1. **Split temporal, no aleatorio**: `fecha_corte` de entrenamiento < `fecha_corte` de validación (p. ej. features al
   2026-06-16 y etiqueta hasta 2026-07-15 para entrenar; features al 2026-07-16 para puntuar). Un split aleatorio por
   persona con el mismo corte no filtra el futuro, pero no mide la deriva temporal.
2. Regenerar la tabla por corte con `dbt build --select tag:features --vars '{"fecha_corte": "AAAA-MM-DD"}'`; la
   columna `fecha_corte` queda grabada en cada fila y la prueba `assert_features_sin_fuga` valida que coincide.
3. Codificar `modo_mas_usado`, `franja_mas_frecuente`, `zona_origen_mas_frecuente`, `perfil_padron`,
   `zona_residencia_id`, `estado_padron` como categóricas; `duracion_promedio_metroriel_min`, `perfil_padron` y
   `zona_residencia_id` tienen NULL con significado (no usa MetroRiel / no está en el padrón).

## Pruebas
- `dbt/models/features/schema.yml`: `unique` + `not_null` de la llave, `not_null` de `fecha_corte`, `accepted_values`
  de modo/franja/estado, rangos 0–1 de las proporciones (`dbt_utils.accepted_range`), `relationships` a `zonas`.
- `dbt/tests/features/assert_features_sin_fuga.sql`: recencia ≥ 1 día, `fecha_corte` igual a la declarada, cobertura
  (filas = personas con abordajes antes del corte) y volumen (`SUM(viajes_total)` = abordajes antes del corte).
- `dbt/tests/features/assert_features_ventanas_monotonas.sql`: `viajes_7d ≤ viajes_30d ≤ viajes_90d ≤ viajes_total`.
- `dbt/tests/features/assert_diccionario_cubre_columnas.sql`: el diccionario en el warehouse cubre todas las columnas.
- `tests/test_gold_lineage.py::test_features_solo_referencia_silver` y `tests/test_no_current_date.py`.

## Límites declarados
- **Ventana de 45 días**: `viajes_90d` y `viajes_30d_previos` están truncadas; `tendencia_30_vs_anterior` queda
  sesgada al alza (mediana +9) porque compara 30 días completos contra 15 observados. `dias_desde_primer_viaje` ≤ 45
  mide antigüedad observable, no antigüedad real.
- **Generador sintético** (ADR-010): los hábitos son los que simula `docs/generar_red_metropolitana.py`; las
  distribuciones no representan la demanda real de Guatemala.
- **Identidad por ADR-008**: el vínculo entre modos depende del identificador base compartido del generador
  (inversión del MD5 sin sal de Aerómetro). Sin ese vínculo el grano tendría que ser tarjeta-por-modo (`usuario_sk`).
- **Padrón "as of"**: perfil, zona de residencia y estado se toman de la última versión de `silver_padron_scd2` con
  `vigente_desde < fecha_corte`, ordenando por `seq` (no por `vigente_hasta`) porque 103 operaciones tienen
  `commit_ts_fuera_de_orden`. Con el corte por defecto coincide con la versión vigente.
- `es_usuario_activo_30d` aplica la definición oficial 2 (`docs/governance/definiciones_oficiales.md`): ≥ 1 viaje en
  los 30 días anteriores y no dado de baja en el padrón; como el padrón es el registro central de personas (ADR-009),
  la cláusula de baja se aplica a la persona en cualquier modo, no solo a Transmetro.

## Diccionario
`docs/features/diccionario_features.md` (Markdown) y `features.diccionario_features` (tabla, 34 filas).
