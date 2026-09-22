# Estado del proyecto

**Fase actual:** F7 cerrada (2026-09-21). Proyecto completo: F0–F7 con evidencia. Pendiente solo lo que hace el equipo a mano: construir el tablero en Tableau Desktop con `docs/tableau/GUIA_TABLERO.md` y anotar el costo de la consola.
**Último paso completado:** `make demo-idempotencia` en verde en la nube (corridas `demo-idempotencia-20260921T001141-1/-2`, 64 tablas y 121 objetos idénticos, 17/17 tareas en success); métricas de Rendimiento e Idempotencia registradas; checklist de rúbrica completo.
**Siguiente paso:** el equipo construye el tablero en Tableau (guía hoja por hoja) y ensaya con `docs/GUIA_DEFENSA.md`; apagar la VM con `make vm-stop` cuando no se use; extras opcionales (sección 12 del plan) solo con autorización.

## Bloqueos
Ninguno. (Facturación vinculada el 2026-09-20; generador disponible en `docs/generar_red_metropolitana.py`; datos en `datos_red/`, ignorados por git.)

## Recursos de nube activos (proyecto cienciadatos-509301, us-central1)
- VM `vm-pipeline` (e2-standard-2, 30 GB) con IP estática <IP_VM>, Airflow en https://airflow.<IP_VM>.sslip.io. **Apagar con `make vm-stop` cuando no se use.**
- Credenciales de Airflow: `gcloud secrets versions access latest --secret=airflow-admin-password` (y `airflow-viewer-password` para `catedratico`).
- Bucket `cienciadatos-509301-lake` (Bronze: 121 objetos, ~346 MB) y `cienciadatos-509301-tfstate` (estado de Terraform).
- Datasets BigQuery: bronze (externas), staging, silver, quarantine, gold, features, ops, ops_secrets.
- Secret Manager: airflow-admin-password, airflow-viewer-password, airflow-fernet-key, hmac-salt.
- Presupuesto 60 USD/mes con alertas a <correo-del-propietario>.

## Costo acumulado en GCP
Medición propia al 2026-09-21 06:40 UTC (la consola de facturación publica el costo real con ~24 h de retraso; anotar aquí la cifra de
**Facturación → Informes → proyecto cienciadatos-509301** cuando aparezca):

| Recurso | Uso medido | Precio de lista | Costo estimado |
|---|---|---|---:|
| VM e2-standard-2 `vm-pipeline` | encendida desde 2026-09-21 04:00 UTC: 2,7 h | 0,067 USD/h | 0,18 USD |
| Disco pd-balanced 30 GB | 2,7 h | 3,00 USD/mes | 0,01 USD |
| IP externa estática | 2,7 h en uso | 0,005 USD/h | 0,01 USD |
| BigQuery consultas | ≈ 6 builds completos × ~5 GB + análisis ≈ 40 GB escaneados | 1 TiB/mes gratis | 0 USD |
| BigQuery almacenamiento | ≈ 5 GB (staging + silver + gold + features) | 10 GiB/mes gratis | 0 USD |
| GCS | 0,31 GB en Bronze + estado de Terraform | 5 GB/mes gratis | 0 USD |
| Secret Manager, Logging, egreso | 4 secretos, < 1 GB | nivel gratuito | 0 USD |
| **Total estimado de la sesión** | | | **≈ 0,20 USD** |

Proyección: ~57 USD/mes con la VM 24×7 o ~25 USD/mes apagándola fuera de uso (`make vm-stop`); todo se descuenta de los 300 USD de crédito de la prueba gratuita.

## Recursos activos (2026-09-21 06:45 UTC)
- VM `vm-pipeline` **APAGADA** desde 2026-09-21 06:45 UTC (`make vm-stop`). Encender con `make vm-start`; la IP <IP_VM> y el dominio se conservan, y la pila de Docker arranca sola (`restart: unless-stopped`).
- Bucket lake, bucket de estado, 8 datasets de BigQuery, 4 secretos, presupuesto de 60 USD/mes con alertas: sin costo apreciable mientras la VM está apagada.
- Para eliminar todo: `make destroy` (conserva el bucket de estado por `prevent_destroy`).
