# Ficha del modelo · `churn_persona` v1.0.0

| Campo | Valor |
|---|---|
| Archivo | `ml/modelos/churn_persona_v1.0.0.joblib` (metadatos en `churn_persona_v1.0.0.json`; `ml/modelos/ACTUAL` lo señala) |
| sha256 | `350b8fcadae48144571b18ade1a6b8e8cd25b10ab7b0a2e6ab704602bd68770b` |
| Entrenado | 2026-11-12T04:35:47Z, commit `f38cc5f`; evaluado en B en el commit `29e8b14` |
| Autores | Equipo del Proyecto (URL, Ciencia de Datos, 2026) |
| Datos | Simulados (v2 de la cátedra, 2026-06-01 a 2026-08-29). No corresponden a ningún operador ni usuario real |

## Para qué sirve

Ordenar a las personas usuarias de la red metropolitana por su probabilidad de **no registrar ningún abordaje válido en
los 30 días siguientes a una fecha de corte**, y decidir a quién contactar en una campaña de retención bajo el escenario
del enunciado (contacto Q5, retención 25 %, valor Q60).

**Usos no previstos:** decisiones individuales con consecuencias para la persona (bloqueos, tarifas, sanciones); estimar
el efecto causal de la campaña; aplicarlo a poblaciones fuera de la definición (menos de 2 abordajes en 28 días, o con baja
del padrón antes del corte); usarlo con datos reales sin revalidar.

## Unidad, población y etiqueta

- **Unidad:** persona (`unidad_id = usuario_unificado_sk`, seudónimo HMAC-SHA256 que une sus tarjetas de los cuatro
  operadores; ADR-014).
- **Población:** al menos 2 abordajes válidos en los 28 días previos al corte y ningún DELETE del padrón antes del corte.
- **Etiqueta:** 1 si no hay ningún abordaje válido en ningún operador en [t, t+30); 0 si hay al menos uno.

## Datos de entrenamiento y evaluación

| Corte | Uso | Personas | Positivos | Tasa |
|---|---|---:|---:|---:|
| A · 2026-07-01 | Entrenamiento, validación cruzada estratificada de 5 pliegues (semilla 2026) | 51 955 | 5 869 | 0,1130 |
| B · 2026-07-31 | Prueba, una sola evaluación | 50 483 | 5 159 | 0,1022 |
| C · 2026-08-30 | Predicciones entregadas (etiqueta oculta) | 49 853 | — | — |

## Modelo

`HistGradientBoostingClassifier` de scikit-learn 1.9.1 dentro de un `Pipeline` con el preprocesamiento (numéricas
escaladas, categóricas codificadas). Hiperparámetros elegidos por AP de validación en una grilla de 16 combinaciones:
`learning_rate` 0,05 · `max_iter` 400 · `max_leaf_nodes` 15 · `l2_regularization` 0. Semilla 2026.

**Features (33, todas calculadas con registros anteriores al corte y ventanas ≤ 28 días, solo desde Silver):** actividad
(`n_abordajes_28d/14d/7d`, `dias_activos_28d/7d`, `dias_desde_ultimo`, `dias_desde_primero_28d`, `semanas_activas_4`,
`ratio_ult14_prev14`, `cv_semanal`), modos (`n_modos_28d`, `share_tm/tu/mr/am`, `modo_principal`), horario
(`pct_hora_pico`, `pct_fin_semana`, `pct_feriado`, `hora_media`, `hora_sd`), gasto (`gasto_q_28d`, `gasto_medio_q`),
geografía (`n_estaciones_28d`, `n_zonas_28d`, `zona_principal`, `pct_transbordo_interno`), tarjetas
(`n_tarjetas_activas_28d`), MetroRiel con salida anterior al corte (`viajes_mr_completos_28d`, `duracion_media_mr_min`) y
padrón a la fecha de corte (`perfil_padron_a_t`, `tiene_padron_a_t`, `n_eventos_padron_28d`). Diccionario:
`docs/P2/diccionario_churn.md`.

## Desempeño

| Conjunto | AP | ROC-AUC | Brier | Referencia (AP de la constante) |
|---|---:|---:|---:|---:|
| Entrenamiento (media de pliegues) | 0,6096 | — | — | 0,1130 |
| Validación cruzada en A | 0,4680 ± 0,0205 | 0,8613 | 0,0768 | 0,1130 |
| **Prueba en B (una vez)** | **0,4214** | 0,8591 | 0,0731 | 0,1022 |

Otras referencias en validación: una sola feature (`dias_desde_ultimo`) 0,4101; logística regularizada 0,4459.
El desempeño esperado en producción es el de B. La brecha entrenamiento-validación (0,14) indica varianza apreciable.

## Decisión de contacto

- **Umbral: 0,340** (contactar si `puntaje ≥ 0,340`), elegido maximizando G(u) = 15·TP − 5·(TP + FP) sobre las
  predicciones fuera de muestra de A; el teórico con probabilidades calibradas es 1/3.
- En A (fuera de muestra): 5 102 contactados, precisión 0,493, recall 0,428, ganancia Q12 200 (Q235 por 1 000 personas).
- En B: 5 325 contactados (TP 2 320, FP 3 005, FN 2 839, TN 42 319), precisión 0,436, recall 0,450, ganancia **Q8 175**
  (Q162 por 1 000).
- En C: 6 052 de 49 853 personas a contactar (`predicciones/predicciones_corte_2026-08-30.csv`).

## Qué pesa en la predicción

Importancia por permutación en validación (caída de AP): `dias_desde_ultimo` 0,240; `zona_principal` 0,015;
`dias_activos_7d` 0,015; `n_abordajes_7d` 0,014; `ratio_ult14_prev14` 0,013. El modelo es, sobre todo, un modelo de
recencia afinado con tendencia reciente, zona y perfil.

## Fugas revisadas

| Riesgo | Cómo se revisó | Resultado |
|---|---|---|
| Features que miran después del corte | Prueba de recorte: features de A con datos completos contra datos recortados al 30 de junio (`make prueba-recorte`) | 51 955 filas, 0 diferencias en 39 columnas |
| Estado final del padrón (`perfil`, `estado`, `es_vigente`, `n_registros_operacion`) | Borrador ingenuo sometido a la misma prueba | 4 fugas detectadas (14 467 · 15 381 · 13 990 · 46 715 filas distintas) y retiradas; se usa el padrón a la fecha de corte |
| Viajes de MetroRiel con salida posterior al corte | Filtro de salida anterior a t en las features de duración | Sin diferencias en el recorte |
| Tarjetas de la persona conocidas después del corte | `tarjetas` solo incluye llaves observadas antes de t | 0 diferencias en `tarjetas` en el ensayo de invariancia |
| Ventanas distintas entre cortes | Prueba automática: ninguna ventana supera 28 días | Pasa (`tests/test_ventanas_churn.py`) |
| Preprocesamiento ajustado con filas de validación | Escalado y codificación dentro del `Pipeline`, ajustados solo con las filas de entrenamiento de cada pliegue | Por construcción |
| Uso de B para ajustar | Guardia de evaluación única; ningún cambio posterior al modelo, al umbral ni a las features | Una evaluación registrada (commit `29e8b14`) |
| Predicciones que cambian con más datos | Ensayo con B y 30 días menos de datos; CSV de la VM contra el oficial | 0 diferencias en 50 483 y 49 853 filas |

## Límites y riesgos

- Datos simulados y un solo trimestre: sin evidencia de estabilidad estacional. El AP bajó de 0,468 a 0,421 entre A y B.
- Predice abandono, no respuesta al contacto: la ganancia depende de que el 25 % de retención sea cierto.
- `zona_principal` y `perfil_padron_a_t` pueden correlacionarse con condiciones socioeconómicas. La acción es un beneficio
  (recarga o aviso), pero conviene revisar la tasa de contacto por zona y perfil antes de operar.
- Quien deja de viajar por una baja del padrón queda fuera de la población y no se puntúa.
- `unidad_id` depende de la sal HMAC: si la sal rota, los seudónimos cambian y las predicciones dejan de ser comparables.

## Uso y mantenimiento

```bash
python predecir.py --datos <carpeta con los 9 archivos> --fecha-corte 2026-08-30            # warehouse (BigQuery)
python predecir.py --datos <carpeta> --fecha-corte 2026-08-30 --origen csv                  # respaldo sin GCP
```

- Entorno: `requirements.txt` (scikit-learn 1.9.1, numpy 2.5.3, pandas 3.0.5), iguales en `vm/Dockerfile.airflow`.
  La carga falla con otra versión de scikit-learn, y las columnas se toman en el orden guardado en los metadatos.
- Invariancia: el DAG regenera las predicciones de C en cada corrida y las compara con el CSV oficial
  (`ml.ml_invariancia`); ensayo con B: 0 diferencias en 50 483 filas (`docs/evidence/p2/invariancia_B.md`).
- Cambios: cualquier reentrenamiento es una versión nueva (`v1.1.0`, …) con su propio archivo, ficha y CSV; el CSV de la
  v1.0.0 no se regenera. Reentrenar si el AP medido sobre un corte ya vencido cae por debajo de la línea base de una
  feature, o si la tasa de contactados se aleja de la esperada (≈ 10–12 %).
