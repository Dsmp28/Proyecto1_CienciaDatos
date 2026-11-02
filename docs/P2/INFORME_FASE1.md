# Informe de la Fase 1 · Proyecto 2: ¿Quién deja de usar la red?

Agencia Metropolitana de Transporte · URL, Ciencia de Datos, segundo semestre 2026. Datos simulados (v2 de la cátedra,
2026-06-01 a 2026-08-29). Secciones 1.1 a 1.4 del enunciado. Plan: `docs/PLAN_P2.md`; decisiones: ADR-012 a ADR-017;
bitácora: `docs/P2/BITACORA.md`; checklist: `docs/RUBRICA_CHECKLIST_P2.md`.

## 1.1 Datos nuevos desde cero

**Comando único** (README §Proyecto 2): `make desde-cero CONFIRMAR=BORRAR-cienciadatos-509301`. Vacía el lake (`bronze/`),
todas las tablas del warehouse (sin tocar los datasets ni la sal HMAC), los tópicos de Kafka y los datos de la VM; dispara
el DAG `red_metropolitana` con `origen_datos=landing` (los nueve archivos v2 publicados una vez con `make landing-subir`) y
`verificar_hashes=true`; y escribe las tablas de conteos y tiempos. Nada se mezcla con los datos del Proyecto 1
(evidencia del vaciado en `docs/evidence/p2/reset_*.md`).

Defectos reales de "desde cero" encontrados y corregidos en el camino (ninguno se veía con el warehouse ya poblado):
`dbt build` por capa ejecutaba pruebas de Silver en la etapa staging (selección indirecta eager) → `--indirect-selection
cautious`; las tres vías de ingesta creaban a la vez las tablas de `ops` recién borradas (409) → creación tolerante;
`fecha_referencia` y el tope de identidad del P1 no servían para v2 (ADR-012).

**Tabla de conteos** (corrida `desde-cero-20261101T212525`; `docs/evidence/p2/conteos_bronze.md`). Esperadas = LEEME de la
cátedra (= `ingest/expected_hashes.json`); cargadas = `COUNT(*)` de la tabla externa de Bronze; en streaming se cuenta
también `archivo:linea_num` distintos para descartar duplicados de Kafka:

| archivo | vía | filas esperadas (LEEME) | filas cargadas (Bronze) | diferencia | ok |
|---|---|---:|---:|---:|:---:|
| tm_estaciones.csv | batch | 104 | 104 | 0 | sí |
| tu_paradas.csv | batch | 328 | 328 | 0 | sí |
| mr_estaciones.csv | batch | 22 | 22 | 0 | sí |
| am_estaciones.csv | batch | 14 | 14 | 0 | sí |
| metroriel_viajes.jsonl | batch | 590,844 | 590,844 | 0 | sí |
| transurbano_transacciones.csv | batch | 1,635,788 | 1,635,788 | 0 | sí |
| transmetro_validaciones.csv | streaming | 713,786 | 713,786 (distintas: 713,786) | 0 | sí |
| aerometro_boardings.csv | streaming | 387,053 | 387,053 (distintas: 387,053) | 0 | sí |
| cdc_padron_usuarios.csv | cdc | 77,636 | 77,636 | 0 | sí |
| **Total** | | **3,405,575** | **3,405,575** | **0** | sí |

**Tabla de tiempos** (misma corrida; `ops.run_metrics`, métrica `duracion_s` por tarea; `docs/evidence/p2/tiempos.md`).
Las tareas de ingesta corren en paralelo, por lo que el reloj del DAG (≈ 24 min desde el disparo hasta `pruebas_python`)
es menor que la suma; `ml_*` se omiten hasta que exista el modelo (fase 2):

| etapa | segundos |
|---|---:|
| generar_o_verificar_datos | 6.3 |
| ingesta_bronze.ingesta_cdc | 11.2 |
| publicar_clave_hmac | 8.4 |
| ingesta_bronze.ingesta_batch | 22.9 |
| ingesta_bronze.ingesta_streaming.kafka_productor | 26.0 |
| ingesta_bronze.ingesta_streaming.kafka_consumidor | 107.5 |
| tablas_externas_bronze | 21.1 |
| conciliar_bronze | 17.6 |
| transformacion_dbt.dbt_deps | 5.5 |
| transformacion_dbt.dbt_seed | 21.5 |
| transformacion_dbt.dbt_staging | 66.4 |
| transformacion_dbt.dbt_silver | 122.1 |
| transformacion_dbt.dbt_gold | 120.0 |
| transformacion_dbt.dbt_features | 41.3 |
| transformacion_dbt.dbt_churn | 91.7 |
| transformacion_dbt.dbt_docs | 102.7 |
| pruebas_python | 64.6 |
| registrar_metricas | 16.7 |
| **TOTAL (suma de tareas)** | **877.3** |

El vaciado previo (`docs/evidence/p2/reset_20261101T212526.md`) tardó ≈ 3 min: 228 objetos de Bronze, 110 tablas y los
tópicos de Kafka. La carga desde cero completa, de un entorno vacío a Features, queda en ≈ 27 min de reloj.

## 1.2 Etiqueta, población y unidad

**Etiqueta (una frase).** Para una persona y una fecha de corte t (00:00 hora local), `etiqueta = 1` si la persona no tiene
ningún abordaje válido en ningún operador entre t y t + 30 días (exclusivo), y `0` si tiene al menos uno; es nula cuando el
horizonte no está observado (corte C). Se calcula solo con `silver.silver_abordajes` (registros válidos: la cuarentena no
entra) en `dbt/models/features/churn/churn_etiqueta.sql`.

**Unidad elegida: la persona** (`unidad_id = usuario_unificado_sk`, ADR-014). En el Proyecto 1 demostramos que las tarjetas
de los cuatro operadores comparten un identificador base (`TC-…`, 10 dígitos, `MR…`) y que el hash de Aerómetro se invierte
por diccionario (ADR-008); con esa identidad medimos que el 73 % de las personas usaba más de un sistema. La definición de
abandono del enunciado habla de "ningún operador", así que la unidad natural es la persona: una tarjeta que deja de usarse
porque su dueño cambió de operador no es un abandono de la red. El costo de esta elección es el vínculo entre tarjetas, que
medimos a continuación.

**Población** (≥ 2 abordajes válidos en los 28 días anteriores a t y ningún DELETE del CDC aplicado antes de t;
`churn_poblacion.sql`; `analysis/p2_poblacion.sql`):

| Corte | Fecha | Personas con ≥ 1 abordaje en 28 d | Con ≥ 2 | Excluidas por DELETE previo | Población | Positivos | Tasa positiva (cuenta) |
|---|---|---:|---:|---:|---:|---:|---|
| A | 2026-07-01 | 57 010 | 53 214 | 1 259 | **51 955** | **5 869** | 5,869 / 51,955 = **0.113** |
| B | 2026-07-31 | 54 727 | 51 565 | 1 082 | **50 483** | **5 159** | 5,159 / 50,483 = **0.102** |
| C | 2026-08-30 | 53 544 | 50 788 | 935 | **49 853** | — (etiqueta oculta) | — |

En v2 ninguna tarjeta dada de baja se reactiva (0 "DELETE reactivados" en los tres cortes), de modo que la lectura literal
del enunciado ("algún DELETE antes de t") y la alternativa ("estado de baja vigente en t") producen la misma población.

**Costo de la unidad persona** (`analysis/p2_costo_unidad.sql`, datos v2):
- Aerómetro: 16 930 hashes distintos observados, **16 930 invertidos (100 %)** con `max_usuario_base_id = 100000`;
  0 abordajes de Aerómetro sin persona.
- Tarjetas sin vínculo: **0 de 0** por modo (todas las llaves TM, TU, MR y AM resolvieron a un identificador base; 711 684 +
  1 549 718 + 583 745 + 387 053 abordajes válidos con persona).
- Tarjetas por persona en el corte A: 1 tarjeta 27 967 · 2 tarjetas 24 657 · 3 tarjetas 8 349 · 4 tarjetas 936.
- Contraste con la unidad tarjeta: de las 89 037 tarjetas activas en la ventana de A, 15 808 no tienen abordajes en el
  horizonte; **7 038 de esas 15 808 (0.445) pertenecen a personas que sí siguieron viajando con otra tarjeta**. Con la tarjeta
  como unidad, casi la mitad de los "abandonos" serían falsos; con la persona desaparecen.

## 1.3 Features a la fecha de corte y auditoría de fuga

[pendiente: diccionario, tabla de features (A, B, C), prueba de recorte con las features que fallaron antes de corregir]

## 1.4 Líneas base y regresión logística regularizada

[pendiente: métrica, tabla de modelos, gráfica AP vs λ, coeficientes]
