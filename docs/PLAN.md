# Plan aprobado (2026-09-20)

Plan por fases con compuerta. Cada fase cierra con: pruebas en verde, métricas registradas en `docs/METRICAS.md`,
documentación actualizada y commits. No se avanza con la fase anterior en rojo.
Detalle de diseño (grano, matriz del bus, identidad, costos): `docs/modelo/`, `docs/DECISIONS.md`.

## Parámetros confirmados
- GCP `cienciadatos-509301`, región `us-central1`, facturación `XXXXXX-XXXXXX-XXXXXX` (vincular con OK).
- Git local: David Monje `<<correo-del-propietario>>`. Sin push.
- `ESCALA` por defecto 0.08 (~137 MB), `fecha_referencia = 2026-07-16`. HTTPS con `airflow.<IP>.sslip.io` + Caddy. TZ `America/Guatemala`.
- Generador real pendiente: en F1 se lee **antes** de escribir modelos y se corrige lo marcado *[verificar en generador]*.

## F0 — Bootstrap
- [x] `git init`, identidad local, `.gitignore`, `.claude/settings.json` sin atribución, `.env.example`
- [x] `CLAUDE.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`
- [x] `docs/modelo/matriz_bus.md` (grano + matriz + clasificación de medidas)
- [x] `.venv` con dbt-bigquery 1.12 (Python 3.12), `Makefile`
- [x] `infra/bootstrap` (bucket de estado versionado, APIs) — aplicado 2026-09-20
- [x] `infra/main` (VPC, firewall 443 + IAP-22, SA mínimo privilegio, bucket lake, datasets BQ + IAM, secretos, presupuesto, VM e2-standard-2 30 GB)
- [x] `vm/` Docker Compose: Kafka 4.3 KRaft, Airflow 3.3 LocalExecutor, Postgres, Caddy HTTPS; usuarios `admin` y `catedratico` (viewer)
- [ ] Compuerta: `terraform apply` limpio, Airflow accesible por HTTPS, Kafka no expuesto, presupuesto creado

## F1 — Datos e ingesta a Bronze (1.1)
- [x] Leer generador real; corregir plan, esquemas, identidad y `fecha_referencia` (ADR-008, 009, 010)
- [ ] `ingest/generar_o_verificar.py` (sha256 por archivo, manifiesto)
- [ ] Batch → GCS: 4 catálogos, `metroriel_viajes.jsonl`, `transurbano_transacciones.csv`
- [ ] Streaming: productor Kafka + consumidor a GCS con nombres deterministas (Transmetro, Aerómetro)
- [ ] CDC: `cdc_padron_usuarios.csv` a Bronze
- [ ] Tablas externas Hive en BigQuery (`bronze` sources de dbt)
- [ ] `ops.ingest_manifest` + tabla de conteos archivo vs Bronze en METRICAS
- [ ] Prueba: republicar/recargar no cambia Bronze

## F2 — Staging y CDC (1.2)
- [ ] `stg_*` con tipos y linaje (`fuente`, `archivo`, `fecha_ingesta`, `offset`)
- [ ] CDC aplicado en orden (INSERT/UPDATE/DELETE; DELETE = inactiva con atributos)
- [ ] Catálogos mínimos de llaves (TU, MR, AM) con conteo de llaves distintas
- [ ] Métricas CDC: altas, cambios, bajas, activas antes/después

## F3 — Silver, calidad y cuarentena (1.3)
- [ ] `docs/governance/reglas_calidad.md` antes del código
- [ ] Seeds: zonas conformadas, mapeo de zona, franjas horarias, feriados
- [ ] Modelos Silver + `quarantine.registros_rechazados`
- [ ] Pruebas: unicidad, not null, relaciones, accepted_values, zona sin mapear, conciliación
- [ ] SCD2 del padrón con ventanas; conteo por regla en METRICAS

## F4 — Gold (1.4)
- [ ] Dimensiones conformadas + 5 hechos; `dim_usuario` con HMAC
- [ ] Particionado/clustering; `tests/test_gold_lineage.py`
- [ ] Diagrama Mermaid, DDL, diccionario YAML, `dbt docs`

## F5 — Orquestación e idempotencia (1.5)
- [ ] DAG completo con reintentos y bitácora; `ops.run_metrics`
- [ ] `make demo-idempotencia` + evidencia en `docs/evidence/`

## F6 — Features, Tableau, recomendación (2.3, 2.1, 2.2)
- [ ] `features.usuario_features` desde Silver, `fecha_corte`, prueba anti-fuga, diccionario
- [ ] Vistas agregadas Gold, `.tds`, `docs/tableau/GUIA_TABLERO.md`, `analysis/*.sql` con tiempos
- [ ] Borrador de recomendación (≤ 2 páginas) con cifra y consulta por afirmación

## F7 — Gobernanza, documentación, seguridad, cierre (3.1–3.3)
- [ ] Diccionario de Gold exportado, definiciones oficiales con dueños, prueba de fuego "viajes del mes"
- [ ] README, página de seguridad, `gitleaks`, `RUBRICA_CHECKLIST.md`, `GUIA_DEFENSA.md`
- [ ] Reporte de costo acumulado y recursos encendidos

## Extras (solo tras F7 y con autorización)
GitHub Actions `dbt test` → modelos incrementales → `dbt source freshness` → transbordo por cercanía.
