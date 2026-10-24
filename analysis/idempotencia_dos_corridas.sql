-- Idempotencia (rúbrica 1.5) · Vista para la consola de BigQuery: las dos últimas corridas COMPLETAS del DAG
-- `red_metropolitana`, lado a lado, con las filas de cada tabla por capa y una bandera igual/difiere.
-- Fuente: ops.run_metrics (la tarea final `registrar_metricas` guarda COUNT(*) de cada tabla). No requiere parámetros:
-- toma las dos corridas más recientes que llegaron al final, así sirve en vivo tras cualquier par de corridas.
-- Ejecutable tal cual: bq query --use_legacy_sql=false --location=us-central1 < analysis/idempotencia_dos_corridas.sql
-- Cifra esperada: 64 tablas con '✅ igual' y ninguna con '❌ difiere' (demo del 2026-10-23).
WITH corridas AS (
  SELECT run_id, MAX(ts) AS fin
  FROM `cienciadatos-509301.ops.run_metrics`
  WHERE etapa = 'registrar_metricas'
  GROUP BY run_id
  ORDER BY fin DESC
  LIMIT 2
),
filas AS (
  SELECT r.capa, r.fuente AS tabla, CAST(r.valor AS INT64) AS filas,
         DENSE_RANK() OVER (ORDER BY c.fin) AS n_corrida
  FROM `cienciadatos-509301.ops.run_metrics` AS r
  JOIN corridas AS c USING (run_id)
  WHERE r.etapa = 'registrar_metricas' AND r.metrica = 'filas' AND r.fuente IS NOT NULL
)
SELECT
  capa,
  tabla,
  MAX(IF(n_corrida = 1, filas, NULL)) AS corrida_anterior,
  MAX(IF(n_corrida = 2, filas, NULL)) AS corrida_ultima,
  IF(MAX(IF(n_corrida = 1, filas, NULL)) = MAX(IF(n_corrida = 2, filas, NULL)), '✅ igual', '❌ difiere') AS idempotente
FROM filas
GROUP BY capa, tabla
ORDER BY CASE capa WHEN 'bronze' THEN 1 WHEN 'staging' THEN 2 WHEN 'silver' THEN 3 WHEN 'quarantine' THEN 4 WHEN 'gold' THEN 5 ELSE 6 END, tabla;

-- Complemento · Bronze no vuelve a ingerir: el manifiesto de las últimas corridas marca todo como `omitido`
-- (sha256 ya conocido) y 0 archivos `completado`/`publicado`.
-- SELECT run_id, via, estado, COUNT(*) AS archivos
-- FROM `cienciadatos-509301.ops.ingest_manifest`
-- WHERE run_id LIKE 'demo-idempotencia-%'
-- GROUP BY 1, 2, 3 ORDER BY 1 DESC, 2;
