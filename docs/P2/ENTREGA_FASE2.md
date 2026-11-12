# Guía de entrega · Fase 2 del Proyecto 2

Qué se entrega, dónde está en el repositorio, cómo reproducirlo y qué no debe volver a ejecutarse.

## Qué pide el enunciado para la Fase 2
"Repositorio con la etiqueta `fase-2`, informe de la Fase 2 (secciones 2.1 a 2.4), presentación y las predicciones del
corte C". Las secciones son: 2.1 ensemble y sesgo-varianza, 2.2 umbral por costo y test único en B, 2.3 segmentos y
acciones, 2.4 predicción reproducible, modelo versionado e invariancia.

## Qué entregar (copiar en la plataforma del curso)
1. **Repositorio público:** `https://github.com/Dsmp28/Proyecto1_CienciaDatos` (rama `main`).
2. **Etiqueta de la entrega:** `fase-2` (apunta al commit de cierre; `git show fase-2` lo muestra).
3. **Informe de la Fase 2:** `docs/P2/INFORME_FASE2.md` (secciones 2.1 a 2.4). Para subirlo como documento, abrir el
   `.md` en VS Code o en GitHub y exportar a PDF, o `pandoc docs/P2/INFORME_FASE2.md -o INFORME_FASE2.pdf`. Las figuras
   están en `docs/evidence/p2/figuras/`.
4. **Ficha del modelo:** `docs/P2/FICHA_MODELO.md`.
5. **Presentación de 15 minutos:** `docs/P2/PRESENTACION.md` (12 láminas con notas del orador).
6. **Predicciones del corte C:** `predicciones/predicciones_corte_2026-08-30.csv` (49 853 personas, 6 052 a contactar).
7. Mapa de entregables y rúbrica: `docs/RUBRICA_CHECKLIST_P2.md`; guion de defensa: `docs/GUIA_DEFENSA.md`.

## Dónde está cada entregable
| Sección | Entregable | Ruta |
|---|---|---|
| 2.1 | Comparación de modelos y grilla | `docs/evidence/p2/fase2_modelos.md` |
| 2.1 | Sesgo y varianza | `docs/evidence/p2/fase2_sesgo_varianza.md` |
| 2.1 | Importancia por permutación | `docs/evidence/p2/fase2_importancias.md` |
| 2.1 | Decisión del modelo | `docs/evidence/p2/fase2_decision.md` |
| 2.2 | Umbral por costo y figura | `docs/evidence/p2/umbral.md`; `docs/evidence/p2/figuras/ganancia_vs_umbral.png` |
| 2.2 | Calibración | `docs/evidence/p2/calibracion.md` |
| 2.2 | Evaluación única en B | `docs/evidence/p2/test_b.md`; `ml/artefactos/evaluacion_b.json`; `docs/P2/BITACORA.md` |
| 2.3 | Segmentos, k y acciones | `docs/evidence/p2/segmentos.md`, `segmentos_k.md`, `acciones.md` |
| 2.3 | Figuras | `docs/evidence/p2/figuras/codo.png`, `silueta.png`, `pca_segmentos.png` |
| 2.4 | Script de predicción | `predecir.py` |
| 2.4 | Modelo versionado | `ml/modelos/churn_persona_v1.0.0.joblib` y `.json` |
| 2.4 | CSV del corte C | `predicciones/predicciones_corte_2026-08-30.csv` |
| 2.4 | Invariancia (ensayo en B) | `docs/evidence/p2/invariancia_B.md` |
| 2.1 a 2.4 | Informe y ficha | `docs/P2/INFORME_FASE2.md`; `docs/P2/FICHA_MODELO.md` |
| — | Presentación | `docs/P2/PRESENTACION.md` |
| — | Defensa | `docs/GUIA_DEFENSA.md` §Proyecto 2 |
| — | Decisiones | `docs/DECISIONS.md` ADR-012 en adelante |
| — | Métricas | `docs/METRICAS.md` §Proyecto 2 |

## Cómo reproducir las cifras (con `.venv` y ADC del propietario)
```bash
make ml-entrenar FASE=2          # 2.1-2.2: ensemble, sesgo-varianza, importancias, umbral y modelo v1.0.0
make ml-segmentos                # 2.3: KMeans y PCA sobre A
make ml-exportar-features        # respaldo CSV de las features de C (para correr sin GCP)
python predecir.py --datos docs/P2_datos_red/datos_red --fecha-corte 2026-08-30   # 2.4: CSV del corte C
make ensayo-invariancia          # 2.4: corte B con datos truncados al 30-jul contra completos
```
La evaluación en B (`make ml-test-b`) ya se ejecutó y no debe repetirse (ver la sección siguiente).

## Qué NO se debe volver a ejecutar
- **`make ml-test-b`.** El corte B se evaluó una sola vez (AP 0,4214, ganancia Q8 175). El registro está en
  `docs/P2/BITACORA.md` y en `ml/artefactos/evaluacion_b.json`; la guardia del comando lo bloquea. Repetirlo con otro
  modelo o umbral convertiría B en un conjunto de validación.
- **Regenerar `predicciones/predicciones_corte_2026-08-30.csv` sin una nueva versión del modelo.** El archivo entregado
  es el oficial; solo se rehace si cambia `churn_persona_v<versión>.joblib`.
- **Cargar el zip de la defensa encima de v2 sin vaciar.** Duplicaría registros y cambiaría las predicciones; la prueba
  de invariancia se corre con `make desde-cero … VERSION_DATOS=invariancia VERIFICAR_HASHES=false` (ADR-018).
- **Rotar la sal HMAC.** Cambiaría todos los `unidad_id` y rompería la invariancia que se demuestra en la defensa.
- **`make desde-cero` o `make reset` sin confirmación.** Son destructivos: solo con la frase
  `CONFIRMAR=BORRAR-cienciadatos-509301` y el visto bueno del propietario. `make reset-dry-run` muestra qué se borraría.

## Cómo actualizar la entrega si cambia algo
1. Hacer los cambios y correr `make test` (pytest).
2. Commit en español con Conventional Commits, autor David Monje, sin menciones a IA.
3. Si cambia una cifra, actualizar `docs/P2/INFORME_FASE2.md`, `docs/P2/FICHA_MODELO.md`, `docs/METRICAS.md` y
   `docs/RUBRICA_CHECKLIST_P2.md`, y anotar la corrida en `docs/P2/BITACORA.md`.
4. Mover la etiqueta y publicar:
   ```bash
   git push origin main
   git tag -f -a fase-2 -m "Fase 2 del Proyecto 2: ensemble, umbral por costo, test único en B, segmentos y predicciones del corte C"
   git push -f origin fase-2
   ```
5. Verificar que GitHub Actions quede en verde en `main`.

## Qué NO se versiona (y por qué)
- `docs/P2_datos_red/datos_red/` (525 MB): viven en `gs://cienciadatos-509301-lake/landing/datos_red/v2/`.
- `ml/artefactos/cache/`, `airflow/salidas/`, `tmp/`: salidas intermedias.
- Secretos: nunca; la sal HMAC está en Secret Manager.
