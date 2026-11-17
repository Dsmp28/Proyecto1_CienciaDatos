# Guion del video de defensa · Proyecto 2

Guía de puntos para hablar, no un texto para leer: el enunciado pide no leer un guion completo. Cada bloque trae la idea
que hay que transmitir, los números que deben verse en pantalla y qué mostrar. Todas las cifras salen del repositorio
(`docs/P2/ENTREGA_FINAL.md` las reúne).

## Reglas del formato (4 puntos)

- Duración total entre 15 y 20 minutos. Este guion suma **19:05**.
- Cada integrante aparece con cámara encendida cuando habla y habla **al menos 3 minutos** (aquí: 3:13 como mínimo).
- Sin voces generadas ni avatares.
- Los números se muestran en pantalla con letra legible: diapositivas con tablas y consola con fuente grande (18 pt o más).
- Entrega en Moodle antes del martes 17 de noviembre a las 23:59; el enlace va también en el README.

## Reparto

"Integrante 1 a 5" son marcadores; la correspondencia con quien registró cada decisión en el repositorio es la de
`docs/P2/BITACORA.md`.

| Integrante | Usuario en el repositorio | Parte 1 | Parte 2 | Parte 3 (explica la decisión de…) | Tiempo total |
|---|---|---|---|---|---:|
| Integrante 1 | Dsmp28 | El problema (1:48) | — | Integrante 2: los datos se reemplazan (1:25) | 3:13 |
| Integrante 2 | ChrisYuman | Los modelos (1:48) | — | Integrante 3: CDC en orden y regla R03 (1:25) | 3:13 |
| Integrante 3 | erickkrv | Los segmentos (1:48) | — | Integrante 4: features a la fecha de corte (1:25) | 3:13 |
| Integrante 4 | jralbizures | La fuga (1:48) | — | Integrante 5: un solo comando y el DAG (1:25) | 3:13 |
| Integrante 5 | Smorareq1 | El umbral y el test B (1:48) | Narra la demostración (3:00) | Integrante 1: umbral por costo y B una vez (1:25) | 6:13 |

| Parte | Duración | Acumulado |
|---|---:|---:|
| 1 · Presentación (5 bloques de 1:48) | 9:00 | 9:00 |
| 2 · Demostración en una sola toma | 3:00 | 12:00 |
| 3 · Explicación cruzada (5 bloques de 1:25) | 7:05 | 19:05 |

Con cinco integrantes la parte 3 pasa de los 4 a 6 minutos que sugiere el enunciado; se prefirió cumplir los 90 segundos
por persona y el mínimo de 3 minutos de cada quien, sin exceder los 20 minutos totales.

---

## Parte 1 · Presentación (9:00)

### 1.1 El problema · Integrante 1 · 1:48 · diapositivas 2 y 3

Idea: qué predecimos, para quién y cuánto cuesta haber elegido a la persona como unidad.

- La pregunta: con lo que sabemos de una persona hasta la fecha de corte, ¿dejará de usar la red en los 30 días siguientes?
- Etiqueta en una frase: 1 si no tiene ningún abordaje válido en ningún operador en los 30 días que empiezan en el corte.
- Población: al menos 2 abordajes válidos en los 28 días previos y ningún DELETE del padrón antes del corte.
- Tasas con la cuenta completa (señalar la tabla):
  - Corte A: 5 869 / 51 955 = 0,113.
  - Corte B: 5 159 / 50 483 = 0,102.
  - Corte C: 49 853 personas, etiqueta oculta.
- Unidad: la persona, porque la definición dice "ningún operador".
- Lo que cuesta: con la tarjeta, 7 038 de 15 808 supuestos abandonos (0,445) eran personas que siguieron viajando con otra
  tarjeta. Con la persona el costo es enlazar identidades: 16 930 de 16 930 hashes de Aerómetro invertidos.

### 1.2 La fuga · Integrante 4 · 1:48 · diapositiva 4

Idea: la prueba de recorte encontró fugas reales y hoy da cero diferencias.

- Qué es: calcular las features del corte A con todos los datos y con los datos recortados al 30 de junio; deben coincidir.
- El borrador ingenuo falló en cuatro features (señalar la tabla): `perfil_padron_final` 14 467 filas distintas,
  `estado_padron_final` 15 381, `es_vigente_padron` 13 990, `n_registros_operacion` 46 715.
- La causa común: usar el estado final del padrón, que ya incluye lo que pasó después del corte.
- La corrección: padrón a la fecha de corte (eventos con `vigente_desde < t`) y conteos solo en la ventana de 28 días.
- Resultado: 51 955 filas, 0 diferencias en 39 columnas.
- Dos diferencias pequeñas (4 y 2 filas) no eran fuga: orden de suma en coma flotante; se corrigió con sumas exactas.

### 1.3 Los modelos · Integrante 2 · 1:48 · diapositivas 5 y 6

Idea: tabla de la sección 2.1, por qué Average Precision y por qué el ensamble va a producción.

- Métrica: Average Precision. Hay 11 % de positivos y se contacta a un subconjunto; la constante vale la tasa positiva.
- Mismos 5 pliegues para todos (señalar la tabla):
  - Constante 0,113.
  - Una sola feature, días desde el último viaje: 0,410.
  - Logística regularizada: 0,446 ± 0,016, entrenamiento 0,451.
  - HistGradientBoosting: 0,468 ± 0,021, entrenamiento 0,610.
  - RandomForest: 0,453, entrenamiento 0,809.
- Sesgo y varianza: la logística no sobreajusta (brecha 0,005), su límite es la forma lineal; el ensamble baja el sesgo y
  paga con varianza (brecha 0,14); RandomForest memoriza (0,36).
- Decisión: HistGradientBoosting. La mejora media (0,022) es del tamaño de una desviación, pero gana en los 5 pliegues y da
  Q12 200 contra Q11 465.
- Lo que más pesa, por permutación en validación: días desde el último viaje (0,240); la siguiente pesa 0,015.

### 1.4 El umbral y el test B · Integrante 5 · 1:48 · diapositivas 7 y 8

Idea: el umbral sale del costo, y B se abrió una sola vez.

- Escenario: contactar cuesta Q5; se retiene al 25 % de quienes iban a irse; retener vale Q60.
- Ganancia: 15 por cada acierto menos 5 por cada contactado. Conviene contactar si la probabilidad supera 1/3.
- Umbral elegido con las predicciones fuera de muestra de A: 0,340 (señalar la curva).
- La cuenta: 15 × 2 514 − 5 × 5 102 = Q12 200. Contactar a todos: −Q171 740.
- Test B, una sola vez, commit `29e8b14`: AP 0,421 contra 0,102 de la constante.
- Matriz: 2 320 aciertos, 3 005 falsos positivos, 2 839 no detectados, 42 319 negativos correctos.
- Ganancia en B: 15 × 2 320 − 5 × 5 325 = Q8 175.
- Decirlo de frente: es menos que en validación (0,468). B tiene menos positivos y el ensamble tiene varianza. No se ajustó
  nada después de ver B.

### 1.5 Los segmentos · Integrante 3 · 1:48 · diapositiva 9

Idea: dos segmentos con riesgo muy distinto y una acción diferente para cada uno.

- KMeans sobre las features escaladas de A; k = 2 por silueta (0,177). El codo sugiere 5; decide la silueta.
- PCA en dos componentes explica 37,9 % (señalar la figura).
- Ocasionales de baja frecuencia: 36 454 personas (70,2 %), abandono 0,152; mediana de 8 abordajes en 28 días.
- Habituales intensivos: 15 501 personas (29,8 %), abandono 0,021; mediana de 32 abordajes.
- Acciones: recarga de Q5 condicionada a dos viajes en 7 días para los ocasionales; aviso de servicio al séptimo día sin
  viajar, sin costo, para los habituales.
- Aclarar: la tasa por segmento es descriptiva, no prueba causa; y la silueta es baja, es un continuo cortado en dos.

---

## Parte 2 · Demostración de MLOps (3:00) · una sola toma, sin cortes · narra Integrante 5

Preparación antes de grabar (no se graba): terminal con fuente grande, `git checkout entrega-final`, `git status` limpio,
entorno activado, credenciales de GCP vigentes (`gcloud auth application-default print-access-token` responde). Si no hay
red, usar la variante sin GCP.

Un solo comando hace los cuatro pasos y muestra cada instrucción antes de ejecutarla:

```bash
make demo-defensa                    # con BigQuery
make demo-defensa DEMO_ORIGEN=csv    # sin GCP
```

| Paso | Qué se ve en pantalla | Qué decir |
|---|---|---|
| 1 | `git log -1 --decorate`: el commit y la etiqueta `entrega-final`; `git status` vacío | "Este es el commit congelado; no hay cambios locales." |
| 2 | `python predecir.py --datos docs/P2_datos_red/datos_red --fecha-corte 2026-08-30`: "Huellas verificadas", 49 853 filas, 6 052 a contactar | "Carga el modelo guardado v1.0.0, no entrena; verifica que los nueve archivos son los ingeridos." |
| 3 | `shasum -a 256` de la salida y del CSV entregado (mismo hash, termina en `…4480b562`), `diff` sin salida, `IDÉNTICOS` | "El archivo nuevo y el entregado son iguales byte a byte." |
| 4 | `docs/P2/FICHA_MODELO.md`: secciones "Fugas revisadas" y "Límites y riesgos" | "Aquí están las ocho fugas revisadas y los límites: datos simulados, un trimestre, retención supuesta." |

Si algo falla durante la toma, se repite la toma completa: no se corta.

---

## Parte 3 · Explicación cruzada (7:05) · 1:25 por persona

Cada quien explica una decisión que registró otra persona: qué se decidió, qué alternativas había, por qué se descartaron
y qué número la respalda.

### 3.1 Integrante 1 explica la decisión de Integrante 2 · los datos nuevos reemplazan, no se acumulan

- Qué se decidió: Bronze es idempotente por archivo y sha256, y una versión nueva de los datos reemplaza a la anterior
  (vaciar y cargar con un solo comando).
- Alternativas: cargar el archivo nuevo encima; deduplicar por contenido de línea en staging.
- Por qué se descartaron: encima, cada registro de junio a agosto quedaría dos veces en Transurbano, Aerómetro y MetroRiel,
  que no tienen llave de negocio entre archivos, y las predicciones cambiarían; deduplicar por línea cambia la regla de
  calidad del Proyecto 1.
- Número: Bronze igual al LEEME, 3 405 575 filas, diferencia 0; con 120 días, 4 605 216 filas y predicciones idénticas.

### 3.2 Integrante 2 explica la decisión de Integrante 3 · CDC en orden de secuencia y regla R03

- Qué se decidió: el padrón se reconstruye aplicando el CDC en orden de `seq`; un DELETE anterior al corte saca a la
  persona de la población; lo posterior a la fecha de referencia va a cuarentena (R03).
- Alternativas: ordenar por la hora del evento; usar el estado final del padrón; descartar los registros futuros.
- Por qué se descartaron: hay operaciones con la hora invertida dentro del mismo día; el estado final es información del
  futuro; el proyecto no descarta nada, todo rechazo queda en cuarentena con su motivo.
- Número: excluidas por DELETE previo 1 259 en A, 1 082 en B y 935 en C; con 120 días, R03 retuvo 257 420 validaciones de
  Transmetro, 572 416 de Transurbano, 137 807 de Aerómetro y 208 530 de MetroRiel.

### 3.3 Integrante 3 explica la decisión de Integrante 4 · features a la fecha de corte desde Silver

- Qué se decidió: las features se calculan desde Silver, con la fecha de corte como parámetro y ventanas de 28 días como
  máximo, iguales en los tres cortes.
- Alternativas: ventanas de 90 días; calcular desde Gold; recortar solo en la tabla de features.
- Por qué se descartaron: el corte A solo tiene 30 días de historia; Gold ya está agregado y seudonimizado para el tablero;
  recortar solo al final no prueba que la deduplicación y el padrón no filtren el futuro.
- Número: prueba de recorte, 51 955 filas y 0 diferencias en 39 columnas; el borrador ingenuo falló en 4 features.

### 3.4 Integrante 4 explica la decisión de Integrante 5 · un solo comando y las tareas en el DAG

- Qué se decidió: un comando vacía, carga, transforma, predice y compara; las tareas de churn, predicción e invariancia
  son parte del mismo DAG de Airflow.
- Alternativas: scripts sueltos corridos a mano; un DAG aparte para el modelo.
- Por qué se descartaron: los pasos manuales son justo lo que la sección 1.1 penaliza; dos DAG pueden desincronizarse y
  predecir sobre datos viejos.
- Número: 20 tareas en éxito; 779 segundos desde un entorno vacío con 120 días; la corrida termina en "IDÉNTICAS".

### 3.5 Integrante 5 explica la decisión de Integrante 1 · umbral por costo y B una sola vez

- Qué se decidió: el umbral se elige maximizando la ganancia en quetzales sobre las predicciones fuera de muestra de A, y
  B se evalúa una única vez con el modelo ya congelado.
- Alternativas: umbral 0,5; elegir el umbral mirando B; reentrenar con A y B antes de predecir C.
- Por qué se descartaron: 0,5 ignora el escenario de costos; mirar B lo convierte en datos de ajuste; reentrenar con B
  deja sin prueba al modelo entregado.
- Número: umbral 0,340 contra 1/3 teórico; Q12 200 en A; en B, AP 0,421 y Q8 175, registrados con el commit `29e8b14`.

---

## Preguntas probables (por si el catedrático pide la llamada de 10 minutos)

- **¿Dónde pudo haber fuga y cómo lo saben?** En el estado final del padrón; la prueba de recorte lo detectó (4 features) y
  la versión corregida da 0 diferencias; con 120 días de datos las predicciones de C no cambiaron.
- **¿Por qué Average Precision?** Clases desbalanceadas y decisión sobre la parte alta del ranking; la constante vale la
  tasa positiva.
- **¿De dónde sale el umbral?** De 15·p − 5 > 0, es decir p > 1/3; el empírico 0,340 queda a 0,007.
- **¿Por qué bajó en B?** Menor tasa base (0,102 contra 0,113) y varianza del ensamble; el ROC-AUC casi no cambió
  (0,861 a 0,859).
- **¿Qué pasa si rotan la sal HMAC?** Cambian todos los `unidad_id` y el CSV deja de ser comparable.
