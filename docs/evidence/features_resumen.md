# Evidencia F6 · Features de usuario (entregable 2.3)

Corrida: `dbt build --select tag:features` (dbt-core 1.12.5, BigQuery `cienciadatos-509301`, `us-central1`),
2026-09-20, `fecha_corte = fecha_referencia = 2026-07-16`. Cifras por consultas directas a `features.usuario_features`
tras la corrida 1; la corrida 2 produjo conteos idénticos (§5).

## 1. Resultado del build (dos corridas)

| Corrida | Modelos | Pruebas | Resultado | Tiempo |
|---|---|---|---|---|
| 1 | 2 tablas (`usuario_features`, `diccionario_features`) | 58 (55 genéricas + 3 singulares) | PASS=59 ERROR=1 (error de sintaxis Jinja en `assert_diccionario_cubre_columnas`; corregido y reejecutado: PASS) | 46,0 s |
| 2 | 2 tablas | 58 | PASS=60 WARN=0 ERROR=0 SKIP=0 | 53,5 s |

`dbt parse` sin errores. `dbt docs generate` → `target/catalog.json`.
`pytest -q tests/test_no_current_date.py tests/test_gold_lineage.py`: **4 passed** (incluye
`test_features_solo_referencia_silver`: `usuario_features` depende solo de `silver_abordajes`, `silver_usuarios`,
`silver_metroriel_viajes`, `silver_padron_scd2` y los seeds `franjas_horarias`, `feriados_gt`).

## 2. Conteos

| Métrica | Valor |
|---|---:|
| Filas (`usuario_unificado_sk` únicos) | 56 848 |
| Personas con abordajes antes del corte en `silver_abordajes` | 56 848 |
| `SUM(viajes_total)` = abordajes antes del corte | 1 647 569 |
| Filas del diccionario (`features.diccionario_features`) = columnas de la tabla | 34 |
| `fecha_corte` | 2026-07-16 (todas las filas) |
| Ventana observada | 2026-06-01 a 2026-07-15 (45 días) |

## 3. Estadísticas descriptivas

| Feature | Mín | Mediana | Máx |
|---|---:|---:|---:|
| `viajes_7d` | 0 | 4 | 21 |
| `viajes_30d` | 0 | 19 (p90 = 32) | 60 |
| `viajes_total` (= `viajes_90d`, ventana truncada, 56 848 de 56 848) | 1 | 29 | 85 |
| `dias_desde_ultimo_viaje` | 1 | 2 | 45 |
| `dias_activos` | — | 21 | 42 |
| `gasto_acumulado_q` | 0 | 41,00 | 199,30 |
| `gasto_promedio_viaje_q` | 0,00 | 1,43 | 3,50 |
| `prop_hora_pico` | 0 | 0,552 | 1 |
| `prop_dia_habil` | — | 0,815 | — |
| `prop_transbordo_interno` | — | 0,045 | 1 |
| `hora_promedio` | — | 12,95 | — |
| `tendencia_30_vs_anterior` | −11 | +9 | +46 |

`dias_desde_ultimo_viaje` mínimo = 1 confirma que ningún abordaje del día de corte entró en la tabla.
La mediana de `tendencia_30_vs_anterior` (+9) es el sesgo esperado de comparar 30 días contra una ventana previa de 15.

## 4. Distribuciones

| `modo_mas_usado` | Personas | % |
|---|---:|---:|
| TU | 34 394 | 60,50 |
| TM | 8 940 | 15,73 |
| MR | 7 955 | 13,99 |
| AM | 5 559 | 9,78 |

| `n_modos_distintos` | Personas | % |
|---|---:|---:|
| 1 | 15 363 | 27,02 |
| 2 | 25 048 | 44,06 |
| 3 | 14 004 | 24,63 |
| 4 | 2 433 | 4,28 |

`es_multimodal` = 41 485 (72,98 %), idéntico al resultado medido en ADR-008 (41 485 personas con más de un sistema).

| `franja_mas_frecuente` | Personas |
|---|---:|
| pico_manana | 23 893 |
| pico_tarde | 17 884 |
| valle | 11 689 |
| noche | 3 156 |
| madrugada | 226 |

`zona_origen_mas_frecuente` (top 5): GT-MIXCO 9 507, GT-Z06 6 584, GT-Z08 6 558, GT-Z01 5 879, GT-Z12 4 539.

| `estado_padron` (as of 2026-07-16) | Personas |
|---|---:|
| SIN_PADRON | 34 386 |
| ACTIVA | 19 469 |
| INACTIVA | 2 993 |

**Usuarios activos 30d** (`es_usuario_activo_30d`): **53 820 (94,67 %)**. Personas con ≥ 1 viaje en 30 días: 56 810;
la diferencia (2 990) son personas dadas de baja en el padrón (INACTIVA) que siguen viajando: por la definición
oficial 2 conservan su historial pero no cuentan como activas.

MetroRiel: 22 885 personas con viajes cerrados antes del corte; duración promedio 21,42 min.

## 5. Idempotencia (corrida 1 vs corrida 2)

| Conteo | Corrida 1 | Corrida 2 |
|---|---:|---:|
| `COUNT(*)` usuario_features | 56 848 | 56 848 |
| `SUM(viajes_total)` | 1 647 569 | 1 647 569 |
| `COUNTIF(es_usuario_activo_30d)` | 53 820 | 53 820 |
| `COUNT(*)` diccionario_features | 34 | 34 |

## 6. Corte alternativo (prueba anti-fuga con otra fecha)
`dbt build --select tag:features --vars '{"fecha_corte": "2026-06-16"}'` → PASS=60 WARN=0 ERROR=0.

| Conteo | Corte 2026-06-16 | Corte 2026-07-16 |
|---|---:|---:|
| Filas | 56 368 | 56 848 |
| `SUM(viajes_total)` | 542 830 | 1 647 569 |
| `MIN(dias_desde_ultimo_viaje)` | 1 | 1 |
| `MAX(dias_desde_primer_viaje)` | 15 | 45 |

Con el corte retrocedido la tabla solo ve 2026-06-01 a 2026-06-15 (15 días) y las pruebas de cobertura y volumen
siguen cuadrando contra `silver_abordajes` filtrado por ese corte. Después se reconstruyó con el corte por defecto
(PASS=60; 56 848 filas, 1 647 569 viajes, 53 820 activos: idéntico a §5).

## 7. No verificado
- La etiqueta de abandono no se puede calcular con este lote (no hay datos posteriores al corte por defecto); solo se
  documenta cómo construirla retrocediendo `fecha_corte` (README).
- No se entrenó ningún modelo: el entregable es la tabla, el diccionario y la fecha de corte.
