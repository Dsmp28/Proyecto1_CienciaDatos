# `vm/` — pila de servicios de la VM

Una sola VM `e2-standard-2` (2 vCPU, 8 GB RAM, Debian 12) corre toda la parte "en línea" del
pipeline con Docker Compose. Ningún servicio se expone salvo Caddy en el puerto 443.

| Servicio (compose) | Imagen | Función | Límite RAM |
|---|---|---|---|
| `kafka` | `apache/kafka:4.3.1` | Kafka KRaft de un nodo (broker+controller). Solo `PLAINTEXT://kafka:9092` en la red interna | 1 GiB (`-Xmx512m`) |
| `postgres` | `postgres:16` | Base de metadata de Airflow | 512 MiB |
| `airflow-init` | `Dockerfile.airflow` | Migra la BD y crea los usuarios `admin` (Admin) y `catedratico` (Viewer). Termina y no se reinicia | 1 GiB (transitorio) |
| `airflow-api-server` | `Dockerfile.airflow` | UI + API REST + Execution API (`api-server --proxy-headers`) | 1.5 GiB |
| `airflow-scheduler` | `Dockerfile.airflow` | Scheduler; con `LocalExecutor` también ejecuta las tareas | 1.5 GiB |
| `airflow-dag-processor` | `Dockerfile.airflow` | Parseo de DAGs (obligatorio en Airflow 3) | 1 GiB |
| `airflow-triggerer` | `Dockerfile.airflow` | Operadores diferibles | 512 MiB |
| `caddy` | `caddy:2` | Proxy inverso HTTPS con certificado automático para `https://airflow.<IP>.sslip.io` | 128 MiB |

**Memoria comprometida en régimen: 6 272 MiB** (6.125 GiB) de los ~7.7 GiB utilizables, más
2 GiB de swap que crea `startup.sh`. `airflow-init` (1 GiB) solo vive unos segundos al arrancar.
Los límites son `deploy.resources.limits.memory` y Docker los aplica como cgroups duros: si un
contenedor los supera lo mata y `restart: unless-stopped` lo vuelve a levantar.

Archivos:

```
vm/
  README.md           este documento
  docker-compose.yml  definición de la pila (derivada del compose oficial de Airflow 3.3.2)
  Dockerfile.airflow  apache/airflow:3.3.2-python3.12 + dbt-core 1.12.5, dbt-bigquery 1.12.1,
                      confluent-kafka, google-cloud-{storage,bigquery,secret-manager}, pyyaml, git, make
  Caddyfile           virtual host {$AIRFLOW_HOST} -> airflow-api-server:8080
  startup.sh          script de arranque de la VM (metadata_startup_script de Terraform)
  .env.template       plantilla que startup.sh convierte en vm/.env (nunca se sube)
```

## Cómo arranca (`startup.sh`)

Terraform pasa `vm/startup.sh` como `metadata_startup_script`; GCE lo ejecuta como root en **cada**
arranque y es idempotente. Pasos:

1. Instala Docker Engine + plugin Compose desde el repositorio oficial de Docker (formato
   `docker.sources`) si faltan, más `git make python3 jq curl rsync`.
2. Lee la metadata de la instancia (`curl -H "Metadata-Flavor: Google"
   http://metadata.google.internal/computeMetadata/v1/instance/attributes/<clave>`):
   `project-id`, `region`, `lake-bucket`, `airflow-host` y, opcional, `acme-email`.
3. Lee los secretos `airflow-admin-password`, `airflow-viewer-password` y `airflow-fernet-key` con
   `gcloud secrets versions access latest --secret=<nombre>` usando la cuenta de servicio adjunta
   (ADC; sin llaves JSON). Si `gcloud` no estuviera, usa la API REST de Secret Manager con el token
   del servidor de metadata. **`hmac-salt` no se lee ni se escribe en disco**: el DAG la obtiene de
   Secret Manager en tiempo de ejecución.
4. Genera una sola vez `AIRFLOW_JWT_SECRET` y `AIRFLOW_API_SECRET_KEY` (`openssl rand`) y los persiste
   en `/etc/red-metropolitana/` (600, root) para que sobrevivan reinicios.
5. Si no existe `/opt/red-metropolitana/vm/docker-compose.yml`, deja un aviso en el log y termina:
   el código llega por `make vm-sync` (ver abajo).
6. Escribe `/opt/red-metropolitana/vm/.env` a partir de `.env.template` (permisos 600). Los valores
   van entre comillas simples porque Compose interpola `$VAR` y corta en ` #` en valores sin
   comillas; una contraseña con barra invertida se rechaza (rota el secreto sin `\`).
7. Crea y activa un swapfile de 2 GB (`/swapfile`, `vm.swappiness=10`).
8. `docker compose up -d --build` en `/opt/red-metropolitana/vm` con `TZ=America/Guatemala`.

Todo queda en `/var/log/startup-red-metropolitana.log`.

### Primera vez: el código llega con `make vm-sync`

El repo todavía no tiene remoto, así que la VM no clona nada. Desde la laptop:

```bash
make vm-sync      # gcloud compute scp --tunnel-through-iap --recurse  ->  /opt/red-metropolitana
```

Después, en la VM, vuelve a ejecutar el arranque (cualquiera de las dos formas):

```bash
sudo google_metadata_script_runner startup     # re-ejecuta el metadata_startup_script
sudo bash /opt/red-metropolitana/vm/startup.sh # equivalente
```

Cada `make vm-sync` posterior seguido de `sudo bash /opt/red-metropolitana/vm/startup.sh` (o de
`docker compose up -d --build` en `vm/`) aplica los cambios. Los DAGs, `dbt/`, `ingest/`, `scripts/`
y `tests/` están montados como volúmenes, por lo que un cambio en ellos no requiere reconstruir.
`vm/.env` no está en el repo: `vm-sync` no debería sobrescribirlo, y en todo caso `startup.sh` lo
regenera en cada arranque.

## Operación diaria

```bash
cd /opt/red-metropolitana/vm
sudo docker compose ps                                # estado y salud
sudo docker compose logs -f --tail=200 airflow-scheduler
sudo docker compose logs -f kafka
sudo docker compose logs caddy                        # emisión del certificado
sudo docker compose restart airflow-api-server
sudo docker compose up -d --build                     # tras cambiar Dockerfile.airflow / compose
sudo docker compose down                              # detiene; los volúmenes persisten
sudo docker compose exec airflow-scheduler airflow dags list
sudo docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
sudo tail -f /var/log/startup-red-metropolitana.log   # bitácora del arranque
free -h && sudo docker stats --no-stream              # memoria por contenedor
```

`make vm-stop` / `make vm-start` apagan y encienden la VM; `restart: unless-stopped` y el
`startup.sh` de cada arranque devuelven la pila al mismo estado. Los datos de Kafka
(`kafka-data`), Postgres (`postgres-db-volume`) y los certificados de Caddy (`caddy-data`,
`caddy-config`) son volúmenes nombrados de Docker y sobreviven a `down` y a reinicios;
`docker compose down -v` los borra.

## Autenticación en Airflow: FAB auth manager

Airflow 3 trae dos gestores de autenticación:

- **Simple Auth Manager** (`airflow.api_fastapi.auth.managers.simple.simple_auth_manager.SimpleAuthManager`,
  el valor por defecto de `AIRFLOW__CORE__AUTH_MANAGER`): usuarios y roles en
  `AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS="admin:admin,catedratico:viewer"`; las contraseñas se
  **autogeneran** y se guardan en texto plano en el JSON de
  `AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE`. La documentación lo marca "para desarrollo y
  pruebas" y no acepta la contraseña por variable de entorno.
- **FAB auth manager** (`airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager`, el que
  usa el `docker-compose.yaml` oficial de 3.3.2): usuarios, roles y contraseñas (hash) en la BD de
  Airflow; roles predefinidos `Admin`, `User`, `Op`, `Viewer`, `Public`. El provider `fab` viene
  preinstalado en la imagen `apache/airflow:3.3.2` (extra `fab` en `AIRFLOW_EXTRAS`).

**Elegido: FAB**, porque permite fijar las contraseñas desde variables de entorno (Secret Manager) y
tiene rol `Viewer` de solo lectura. Configuración exacta:

| Dónde | Variable | Valor |
|---|---|---|
| `x-airflow-common` | `AIRFLOW__CORE__AUTH_MANAGER` | `airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager` |
| `airflow-init` | `_AIRFLOW_DB_MIGRATE` | `true` (el entrypoint corre `airflow db migrate`) |
| `airflow-init` | `_AIRFLOW_WWW_USER_CREATE` / `_USERNAME` / `_PASSWORD` / `_ROLE` | `true` / `admin` / `${AIRFLOW_ADMIN_PASSWORD}` / `Admin` (el entrypoint corre `airflow users create`) |
| `airflow-init` (comando) | `airflow users create -u catedratico -p ${AIRFLOW_VIEWER_PASSWORD} -r Viewer ...` | idempotente: si existe imprime `already exists in the db` y sale con 0 |

Para cambiar una contraseña después de creado el usuario (p. ej. tras rotar el secreto):

```bash
sudo docker compose exec airflow-api-server airflow users reset-password -u catedratico -p 'nueva'
```

Otras variables verificadas para Airflow 3 detrás del proxy HTTPS:

- `AIRFLOW__API__BASE_URL=https://${AIRFLOW_HOST}`: Airflow no puede adivinar el dominio público.
- `AIRFLOW__API__SECRET_KEY` y `AIRFLOW__API_AUTH__JWT_SECRET`: el JWT debe ser el mismo en todos los
  componentes; se generan una vez en `startup.sh`.
- `api-server --proxy-headers` + `FORWARDED_ALLOW_IPS=*`: uvicorn respeta `X-Forwarded-Proto`/`For`
  que envía Caddy (Caddy los añade por defecto en `reverse_proxy`). `*` es seguro porque el api-server
  no publica ningún puerto: solo Caddy lo alcanza por la red interna.
- `AIRFLOW__CORE__EXECUTION_API_SERVER_URL=http://airflow-api-server:8080/execution/`: las tareas
  hablan con la Execution API por la red interna y no a través de Caddy.

## HTTPS con Caddy: solo el puerto 443

El firewall de GCP solo abre 443, así que el desafío ACME HTTP-01 (puerto 80) no puede funcionar.
El `Caddyfile` deshabilita HTTP-01 en cada emisor (`disable_http_challenge`) y queda **TLS-ALPN-01**,
que se resuelve por 443. Al declarar `issuer` explícitamente Caddy descarta los emisores por defecto,
por eso se listan dos: Let's Encrypt y el endpoint ACME de ZeroSSL como respaldo (Caddy obtiene
las credenciales EAB de ZeroSSL automáticamente con el `email`). No se publica el 80: la
redirección http→https sería inalcanzable de todos modos. `caddy-data` guarda la cuenta ACME y los
certificados; no lo borres o consumirás los límites de emisión de Let's Encrypt
(sslip.io es un dominio compartido y sus cuotas se agotan; de ahí el respaldo ZeroSSL).

Sin `basic_auth` en Caddy: la autenticación la hace Airflow.

## Kafka

- Un solo nodo KRaft en modo combinado; `CLUSTER_ID` fijo en el compose para que el volumen
  `kafka-data` (`/var/lib/kafka/data`, directorio que la imagen crea con dueño `appuser`) siga
  siendo válido entre reinicios.
- Sin puertos publicados: los clientes de la VM usan `KAFKA_BOOTSTRAP=kafka:9092` desde los
  contenedores de Airflow. Desde el host no se puede conectar (a propósito).
- Tópicos: `KAFKA_AUTO_CREATE_TOPICS_ENABLE=true` (valor por defecto de Kafka, dejado explícito),
  3 particiones por defecto, factor de replicación 1. El productor de `ingest/` puede además
  crearlos con `AdminClient` para fijar particiones antes del primer mensaje.
- Retención 72 h: el consumidor escribe a GCS (Bronze) y confirma offsets después; no hace falta
  conservar más.
- JVM: `KAFKA_HEAP_OPTS=-Xmx512m -Xms256m` (el script de arranque de Kafka pone `-Xmx1G` si no se fija).

## Secretos y datos sensibles

| Dato | Origen | Dónde vive en la VM |
|---|---|---|
| `airflow-admin-password`, `airflow-viewer-password`, `airflow-fernet-key` | Secret Manager (SA de la VM) | `vm/.env` (600 root), regenerado en cada arranque |
| `hmac-salt` | Secret Manager | **nunca en disco**: el DAG lo lee en tiempo de ejecución |
| JWT secret / api secret_key | generados por `startup.sh` | `/etc/red-metropolitana/*` (600 root) y `vm/.env` |
| Credenciales de GCP | ADC del servidor de metadata | ninguna llave; las librerías de Google las descubren solas desde los contenedores |

Rotar un secreto en Secret Manager y reiniciar la VM (o re-ejecutar `startup.sh`) basta para la
fernet key y las contraseñas de usuarios nuevos; para usuarios ya creados usa `airflow users
reset-password` (ver arriba).

## Solución de problemas

- **Airflow no responde / 502 en Caddy**: `docker compose ps`; el api-server tarda ~1 min en
  arrancar (`start_period: 60s`). `docker compose logs airflow-api-server`.
- **Sin certificado**: `docker compose logs caddy`. Verifica que `airflow-host` en metadata resuelve
  a la IP pública (sslip.io) y que el firewall abre 443 a `0.0.0.0/0`.
- **OOM**: `dmesg -T | grep -i kill` y `docker stats`. Baja `AIRFLOW__CORE__PARALLELISM` o
  `KAFKA_HEAP_OPTS` en el compose; el swap de 2 GB amortigua picos de dbt.
- **`airflow-init` falla**: casi siempre secretos vacíos (revisa el log del arranque) o Postgres aún
  levantando. `docker compose up -d` lo reintenta.
- **Volumen de Kafka corrupto / cambio de `CLUSTER_ID`**: `docker compose down` y
  `docker volume rm vm_kafka-data`; los datos ya están en GCS (Bronze).
