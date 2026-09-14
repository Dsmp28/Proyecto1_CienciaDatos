# Proyecto 1 — Agencia Metropolitana de Transporte (URL, Ciencia de Datos)

Pipeline de datos de punta a punta para integrar cuatro operadores de transporte de Guatemala
(Transmetro, Transurbano, MetroRiel, Aerómetro). Se califica con rúbrica de 100 pts y defensa oral.
Enunciado: `docs/Proyecto 1 Red Metropolitana.pdf`. Plan aprobado: `docs/PLAN.md`.

## Al retomar una sesión
Leer en este orden: `CLAUDE.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`.
Si el generador `docs/generar_red_metropolitana.py` ya existe, leerlo completo antes de tocar modelos.

## Stack (decidido)
| Pieza | Herramienta |
|---|---|
| Nube / IaC | GCP `cienciadatos-509301`, región `us-central1`, Terraform (`infra/`) |
| Bronze | GCS `gs://<proyecto>-lake/bronze/<fuente>/ingest_date=YYYY-MM-DD/`, tablas externas Hive en BigQuery |
| Staging / Silver / Cuarentena / Gold / Features / Ops | BigQuery, datasets `staging`, `silver`, `quarantine`, `gold`, `features`, `ops`, `ops_secrets` |
| Streaming | Kafka 4.x KRaft (Docker Compose en la VM), productor y consumidor en `ingest/` |
| Transformación | dbt Core 1.12 + dbt-bigquery (`dbt/`), Python 3.12 en `.venv` |
| Orquestación | Airflow 3.3 (Docker Compose en la VM, LocalExecutor), DAG en `airflow/dags/` |
| Visualización | Tableau Desktop → BigQuery `gold` únicamente |

## Comandos clave
```
make venv                 # crea .venv con dbt-bigquery
make plan / make apply    # terraform en infra/main (apply solo con OK del usuario)
make vm-start / vm-stop   # encender/apagar la VM (ahorra ~33 USD/mes)
make destroy              # destruye toda la infraestructura
make demo-idempotencia    # corre el flujo dos veces y compara conteos
make dbt-build            # dbt build por capas con pruebas
```

## Convenciones
- Commits: Conventional Commits en español (`feat:`, `fix:`, `docs:`, `infra:`, `test:`, `chore:`), pequeños y frecuentes.
  Único autor: David Monje. **Sin** `Co-Authored-By`, sin menciones a IA. Sin `push` ni remotos salvo petición.
- Toda decisión no trivial va a `docs/DECISIONS.md` (ADR corto). Cada fase cierra con pruebas verdes, métricas en `docs/METRICAS.md`, docs y commit.
- Nunca `CURRENT_DATE` en modelos: usar `var('fecha_referencia')`.
- Secretos solo en Secret Manager; el repo solo lleva `.env.example`. Nunca llaves JSON de cuentas de servicio.
- Si una prueba falla se corrige la causa raíz; no se modifica la prueba ni se fijan valores.

## Restricciones duras (penalizaciones de la rúbrica)
1. Gold solo hace `ref()` a Silver u otro Gold. Nunca a Bronze ni Staging. Prueba: `tests/test_gold_lineage.py`.
2. Ningún registro se descarta: todo rechazo va a `quarantine.registros_rechazados` con registro original, fuente, motivo y timestamp. Prueba de conciliación: staging = silver + cuarentena (duplicados cuentan como cuarentena).
3. Flujo idempotente: dos corridas → conteos idénticos en todas las capas.
4. Cada métrica del tablero rastreable al archivo crudo (columnas de linaje `fuente`, `archivo`, `fecha_ingesta` en Silver y Gold; grafo de dbt docs).
5. Features de ML salen de Silver, nunca de Gold.
6. Staging se vacía en cada corrida; Bronze se acumula sin duplicarse.
7. Llave de usuario seudonimizada (HMAC-SHA256 con sal secreta) antes de Gold.
8. Catálogos de usuarios de Transurbano, MetroRiel y Aerómetro: solo la llave, sin atributos inventados.

## Grano y modelo
- Hecho principal `fct_abordaje`: "una validación de una tarjeta de un usuario en un modo, en una estación o parada, en un instante".
- MetroRiel aporta su entrada como abordaje y conserva el viaje completo en `fct_viaje_metroriel`.
- Matriz del bus: `docs/modelo/matriz_bus.md`.
