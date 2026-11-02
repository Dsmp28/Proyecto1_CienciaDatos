# Guía de entrega · Fase 1 del Proyecto 2

Qué se entrega, dónde está en el repositorio y cómo actualizar la entrega si algo cambia.

## Qué pide el enunciado para la Fase 1
"Repositorio con la etiqueta `fase-1` e informe de la Fase 1 (secciones 1.1 a 1.4)".

## Qué entregar (copiar en la plataforma del curso)
1. **Repositorio público:** `https://github.com/Dsmp28/Proyecto1_CienciaDatos` (rama `main`).
2. **Etiqueta de la entrega:** `fase-1` (apunta al commit de cierre; `git show fase-1` lo muestra).
3. **Informe de la Fase 1:** `docs/P2/INFORME_FASE1.md` (secciones 1.1, 1.2, 1.3 y 1.4 con todas las tablas y cifras).
   Para subirlo como documento: abrir el `.md` en VS Code o en GitHub y exportar/imprimir a PDF, o `pandoc
   docs/P2/INFORME_FASE1.md -o INFORME_FASE1.pdf` si se instala pandoc. Las figuras referenciadas están en
   `docs/evidence/p2/figuras/`.
4. Mapa de entregables → rutas: `docs/RUBRICA_CHECKLIST_P2.md` (una fila por ítem de la rúbrica con su estado y prueba).

## Dónde está cada entregable
| Sección | Entregable | Ruta |
|---|---|---|
| 1.1 | Comando único | `README.md` §Proyecto 2 (`make desde-cero CONFIRMAR=BORRAR-cienciadatos-509301`) |
| 1.1 | Tabla de conteos | `docs/evidence/p2/conteos_bronze.md` |
| 1.1 | Tabla de tiempos | `docs/evidence/p2/tiempos.md` |
| 1.2 | Etiqueta, unidad, población, costo | `docs/P2/INFORME_FASE1.md` §1.2; `analysis/p2_poblacion.sql`, `analysis/p2_costo_unidad.sql`; ADR-014 |
| 1.3 | Tabla de features (A, B, C) | BigQuery `features.churn_dataset` (`dbt/models/features/churn/`); muestra `docs/evidence/p2/churn_dataset_muestra.csv` |
| 1.3 | Diccionario | `docs/P2/diccionario_churn.md` |
| 1.3 | Prueba de recorte | `docs/evidence/p2/prueba_recorte.md`, `prueba_recorte_ingenuo.md`, `prueba_recorte_fallos.json` |
| 1.4 | Métrica, tabla de modelos, gráfica, coeficientes | `docs/P2/INFORME_FASE1.md` §1.4; `docs/evidence/p2/fase1_*.md`; `docs/evidence/p2/figuras/ap_vs_lambda.png` |
| — | Decisiones | `docs/DECISIONS.md` ADR-012 a ADR-017 |
| — | Bitácora | `docs/P2/BITACORA.md` |
| — | Métricas obligatorias | `docs/METRICAS.md` §Proyecto 2 |

## Cómo reproducir las cifras (con `.venv` y ADC del propietario; VM encendida para el DAG)
```bash
make desde-cero CONFIRMAR=BORRAR-cienciadatos-509301   # 1.1 (≈ 27 min; destructivo: vacía y recarga v2)
make prueba-recorte                                     # 1.3 (≈ 6 min)
make ml-entrenar FASE=1                                 # 1.4 (≈ 10 min)
bq query --use_legacy_sql=false --location=us-central1 < analysis/p2_poblacion.sql      # 1.2
bq query --use_legacy_sql=false --location=us-central1 < analysis/p2_costo_unidad.sql   # 1.2
```

## Cómo actualizar la entrega si cambia algo
1. Hacer los cambios y correr `make test` (pytest) y, si tocan dbt, `cd dbt && ../.venv/bin/dbt parse`.
2. Commit en español con Conventional Commits (`feat:`, `fix:`, `docs:`...), autor David Monje, sin menciones a IA.
3. Si cambia una cifra, actualizar `docs/P2/INFORME_FASE1.md`, `docs/METRICAS.md` y `docs/RUBRICA_CHECKLIST_P2.md`, y
   anotar la corrida en `docs/P2/BITACORA.md` (fecha, commit, comando).
4. Mover la etiqueta y publicar:
   ```bash
   git push origin main
   git tag -f -a fase-1 -m "Fase 1 del Proyecto 2: datos desde cero, etiqueta y población, features y recorte, líneas base y logística"
   git push -f origin fase-1
   ```
5. Verificar que GitHub Actions (`dbt test`) quede en verde en `main`.

## Qué NO se versiona (y por qué)
- `docs/P2_datos_red/datos_red/` (525 MB de datos v2): viven en `gs://cienciadatos-509301-lake/landing/datos_red/v2/`.
- `ml/artefactos/cache/`, `airflow/salidas/`, `tmp/`: salidas intermedias.
- Secretos: nunca; la sal HMAC y las contraseñas están en Secret Manager.

## Pendiente para la Fase 2 (entrega del 9 de noviembre, etiqueta `fase-2`)
Ensemble y sesgo-varianza (2.1), umbral por costo y test único en B (2.2), KMeans y PCA (2.3), `predecir.py`, modelo
versionado, ficha e invariancia (2.4), informe de la fase 2 y presentación. El código de todo ello ya está en el repo
(`ml/`, `predecir.py`, tareas `ml` del DAG) pendiente de ejecutarse con los datos v2.
