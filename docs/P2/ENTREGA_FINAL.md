# Entrega final · Proyecto 2: ¿Quién deja de usar la red?

Agencia Metropolitana de Transporte · Ciencia de Datos, Universidad Rafael Landívar, segundo semestre 2026 · Ing. Max Cerna.
Los datos son simulados. Este documento resume lo que se entrega para la defensa en video (`P2 Defensa en video.pdf`),
dónde está cada cosa y cómo se comprobó. Todas las cifras salen de este repositorio.

| Dato | Valor |
|---|---|
| Repositorio | https://github.com/Dsmp28/Proyecto1_CienciaDatos |
| Etiqueta congelada | `entrega-final` (contiene el CSV del corte C, `predecir.py`, el modelo guardado y la ficha) |
| Etiquetas anteriores | `fase-1`, `fase-2` |
| Video | enlace en el README, sección "Defensa en video" |
| Fecha límite | martes 17 de noviembre de 2026, 23:59 (Moodle) |

## 1. Qué pide la defensa en video y dónde está

| Requisito | Dónde está | Estado |
|---|---|---|
| Etiqueta `entrega-final` sobre el commit con el CSV de C, `predecir.py`, el modelo y la ficha | `predicciones/predicciones_corte_2026-08-30.csv`, `predecir.py`, `ml/modelos/churn_persona_v1.0.0.joblib`, `docs/P2/FICHA_MODELO.md` | Hecho |
| Bitácora con qué se decidió, quién y qué número lo respalda | `docs/P2/BITACORA.md`, sección "Decisiones importantes" (11 decisiones) | Hecho |
| Ensayo de la demostración y de la invariancia | `docs/evidence/p2/ensayo-invariancia/`, `docs/evidence/p2/defensa-120/`, `make demo-defensa` | Hecho |
| Parte 1 · presentación (8 a 10 min) | `docs/P2/entrega_final/Presentacion_Defensa_P2.pptx`; guion en `docs/P2/GUION_VIDEO.md` | Material listo; la graba el equipo |
| Parte 2 · demostración en una sola toma (3 a 5 min) | `make demo-defensa` (`scripts/demo_defensa.sh`) | Probada; la graba el equipo |
| Parte 3 · explicación cruzada (4 a 6 min) | `docs/P2/GUION_VIDEO.md` §Parte 3; `docs/P2/BITACORA.md` | Material listo; la graba el equipo |
| Enlace del video en el README con acceso para el catedrático | `README.md`, sección "Defensa en video" | Pendiente: se agrega al subir el video |

## 2. El problema, con sus números

- **Etiqueta.** Para una persona y una fecha de corte t (00:00 hora local): 1 si no tiene ningún abordaje válido en ningún
  operador en [t, t + 30 días); 0 si tiene al menos uno.
- **Unidad.** La persona (`usuario_unificado_sk`), que une las tarjetas de los cuatro operadores.
- **Población.** Al menos 2 abordajes válidos en los 28 días previos y ningún DELETE del padrón antes de t.

| Corte | Papel | Población | Positivos | Tasa positiva (cuenta completa) |
|---|---|---:|---:|---|
| A · 2026-07-01 | Entrenamiento | 51 955 | 5 869 | 5 869 / 51 955 = 0,113 |
| B · 2026-07-31 | Prueba, una vez | 50 483 | 5 159 | 5 159 / 50 483 = 0,102 |
| C · 2026-08-30 | Predicciones entregadas | 49 853 | — | etiqueta oculta |

- **Costo de la unidad.** Con la tarjeta como unidad, 7 038 de 15 808 supuestos abandonos (0,445) son personas que siguieron
  viajando con otra tarjeta. Con la persona, el costo es el enlace de identidad: 16 930 de 16 930 hashes de Aerómetro
  invertidos (100 %) y 0 tarjetas sin vínculo.

## 3. La fuga: qué falló y cómo se corrigió

Prueba de recorte: las features del corte A se calculan dos veces, con todos los datos y con los datos recortados al 30 de
junio. Deben ser idénticas.

| Feature del borrador ingenuo | Filas distintas (de 51 955) | Causa | Corrección |
|---|---:|---|---|
| `perfil_padron_final` | 14 467 | Perfil después de todo el log del CDC | Perfil del último evento con `vigente_desde < t` |
| `estado_padron_final` | 15 381 | Estado final del padrón | Se retira; se usa el padrón a la fecha de corte |
| `es_vigente_padron` | 13 990 | "No hay evento siguiente" depende del futuro | Se retira |
| `n_registros_operacion` | 46 715 | Conteo de todo el periodo | Conteo de eventos en la ventana de 28 días |

Versión corregida: 51 955 filas comparadas, **0 diferencias en 39 columnas** (`docs/evidence/p2/prueba_recorte.md`). Dos
diferencias menores (4 y 2 filas) no eran fuga sino orden de suma en coma flotante; se resolvieron con sumas exactas.

## 4. Los modelos

Métrica: Average Precision (AP). Con 11 % de positivos y una campaña que contacta a un subconjunto, importa la precisión en
la parte alta del ranking; la línea base constante vale exactamente la tasa positiva, así que toda mejora se lee directo.
Validación cruzada estratificada de 5 pliegues sobre A, los mismos pliegues para todos.

| Modelo | AP entrenamiento | AP validación (media ± sd) | ROC-AUC | Sesgo-varianza |
|---|---:|---:|---:|---|
| Constante (tasa de A) | 0,1130 | 0,1130 ± 0,0000 | 0,5000 | Sesgo máximo |
| Una feature (`dias_desde_ultimo`) | 0,4096 | 0,4101 ± 0,0186 | 0,8417 | Sesgo; sin varianza |
| Logística L2 / L1 / ElasticNet | 0,4506 | 0,4459 ± 0,0160 | 0,8501 | Equilibrado; límite lineal |
| **HistGradientBoosting v1.0.0** | 0,6096 | **0,4680 ± 0,0205** | 0,8613 | Menos sesgo, más varianza (brecha 0,14) |
| RandomForest | 0,8092 | 0,4527 ± 0,0227 | 0,8587 | Varianza alta (brecha 0,36) |

A producción va HistGradientBoosting: gana a la logística en los 5 pliegues (0,016 · 0,037 · 0,026 · 0,019 · 0,013) y da más
ganancia (Q12 200 contra Q11 465). Importancia por permutación en validación: `dias_desde_ultimo` 0,240; `zona_principal`
0,015; `dias_activos_7d` 0,015; `n_abordajes_7d` 0,014; `ratio_ult14_prev14` 0,013.

## 5. El umbral y la prueba en B

- Contactar cuesta Q5; si la persona iba a abandonar, la campaña la retiene en el 25 % de los casos y retenerla vale Q60.
- Ganancia: G(u) = 15·TP − 5·(TP + FP). Umbral teórico: contactar si 15·p > 5, es decir p > 1/3.
- Umbral elegido con las predicciones fuera de muestra de A: **0,340**. Contactados 5 102 (TP 2 514, FP 2 588);
  G = 15 × 2 514 − 5 × 5 102 = **Q12 200**. Contactar a todos: −Q171 740.
- **Evaluación única en B** (2026-11-12T04:36:54Z, commit `29e8b14`): AP **0,4214** (constante 0,1022), ROC-AUC 0,8591,
  precisión 0,4357, recall 0,4497. Matriz: TN 42 319 · FP 3 005 · FN 2 839 · TP 2 320.
  Ganancia = 15 × 2 320 − 5 × 5 325 = **Q8 175**.
- El resultado en B es menor que en validación (0,468). No se ajustó nada después de verlo.

## 6. Los segmentos

KMeans sobre las features escaladas de A; k = 2 por silueta (0,1766); PCA en dos componentes explica 37,9 %.

| Segmento | Personas | Tasa de abandono | Medianas (28 días) | Acción |
|---|---:|---:|---|---|
| Ocasionales de baja frecuencia | 36 454 (70,2 %) | 0,152 | 8 abordajes, 6 días activos, Q11 | Recarga de Q5 condicionada a dos viajes en 7 días |
| Habituales intensivos | 15 501 (29,8 %) | 0,021 | 32 abordajes, 16 días activos, Q51,9 | Aviso de servicio al séptimo día sin viajar, sin costo |

La tasa por segmento es descriptiva; no prueba causalidad.

## 7. MLOps y la prueba de invariancia

- `python predecir.py --datos <carpeta> --fecha-corte 2026-08-30` carga `ml/modelos/churn_persona_v1.0.0.joblib` sin
  reentrenar y escribe `unidad_id,tarjetas,puntaje,contactar`.
- CSV entregado: 49 853 personas, 6 052 a contactar. sha256
  `2f0a5f76fcd1a15e1eed2f7dc74b0eddf0a04a0b021caaf6abf9d6004480b562`.
- Entorno: versiones fijas en `requirements.txt`, semilla 2026, pliegues guardados.

**Invariancia comprobada con los datos de 120 días de la cátedra** (`P2_datos_red_defensa_120dias.zip`, hasta el 28 de
septiembre), el 16 de noviembre de 2026:

| Comprobación | Resultado |
|---|---|
| Los archivos de 90 días son un prefijo exacto de los de 120 | Sí, en los 9 archivos |
| Filas nuevas | 1 199 641 (Bronze pasa de 3 405 575 a 4 605 216) |
| Filas nuevas con fecha anterior al corte C | 0 en las cinco fuentes |
| Flujo completo desde un entorno vacío (corrida `desde-cero-20261116T214214`) | 20 tareas en éxito, 779 s |
| Registros en cuarentena por R03 (fecha posterior a `fecha_referencia`) | 257 420 Transmetro · 572 416 Transurbano · 137 807 Aerómetro · 208 530 MetroRiel. En Transurbano son las 570 771 filas nuevas más 1 645 fechas futuras que ya venían en los datos de 90 días |
| Último día con abordajes válidos en Silver | 2026-08-29 |
| CSV generado en la VM contra el entregado | 49 853 filas, **0 diferencias** en `tarjetas`, `contactar` y `puntaje` |
| `predecir.py --datos <carpeta de 120 días>` en la laptop | Mismo sha256 que el CSV entregado |

Después se restauraron los datos de 90 días con el mismo comando (corrida `desde-cero-20261116T220008`: 20 tareas en éxito,
749 s, Bronze = LEEME con diferencia 0 y CSV de C idéntico; `docs/evidence/p2/restauracion-v2/`).

Evidencia: `docs/evidence/p2/defensa-120/`. Antes se había ensayado con un conjunto fabricado
(`scripts/fabricar_datos_ensayo.py`, `docs/evidence/p2/ensayo-invariancia/`); ese ensayo encontró y permitió corregir un
defecto real: la carga desde un entorno vacío fallaba porque un modelo de auditoría entraba al flujo normal (commit `d71bfbf`).

Comando para repetirla (los datos nuevos reemplazan a los cargados; ADR-018):

```bash
make landing-subir VERSION=defensa-120 ORIGEN=<carpeta del zip>
make desde-cero CONFIRMAR=BORRAR-cienciadatos-509301 VERSION_DATOS=defensa-120 VERIFICAR_HASHES=false   # termina en IDÉNTICAS
```

## 8. Demostración del video (parte 2)

```bash
git checkout entrega-final
make demo-defensa            # git log -1, predecir.py con los datos de 90 días, sha256 y diff, ficha del modelo
make demo-defensa DEMO_ORIGEN=csv   # igual, sin GCP
```

## 9. Límites

- Datos simulados y un solo trimestre: sin evidencia de estabilidad estacional. El AP bajó de 0,468 a 0,421 entre A y B.
- El 25 % de retención y los Q60 son supuestos del enunciado; el modelo predice abandono, no respuesta al contacto.
- El ensamble tiene varianza apreciable (brecha entrenamiento-validación 0,14).
- `unidad_id` depende de la sal HMAC: no debe rotarse mientras el CSV entregado sea la referencia.

## 10. Lista de verificación antes de entregar

- [x] Existe la etiqueta `entrega-final` y contiene el CSV del corte C, `predecir.py`, el modelo y la ficha.
- [x] La bitácora dice quién tomó cada decisión.
- [ ] El video dura entre 15 y 20 minutos.
- [ ] Todos aparecen con cámara y hablan al menos 3 minutos.
- [ ] La demostración está en una sola toma y muestra `git log -1`.
- [ ] El enlace del video está en el README y el catedrático tiene acceso.
