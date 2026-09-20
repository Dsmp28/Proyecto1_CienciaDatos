{{ config(cluster_by=['usuario_sk']) }}
-- Gold · dim_padron_historia. SCD Tipo 2 del padrón de Transmetro seudonimizado (una fila por versión de cada tarjeta),
-- desde silver_padron_scd2 (ADR-009) unido a silver_usuarios por (modo, tarjeta) para sustituir la llave nativa por
-- usuario_sk. Conserva las tarjetas dadas de baja (estado INACTIVA, es_vigente) como exige el enunciado: historizar,
-- no borrar. vigente_desde/vigente_hasta siguen el orden del log (seq); es_vigente marca la versión actual.
select
    u.usuario_sk,
    u.usuario_unificado_sk,
    p.modo_id,
    p.version,
    p.seq,
    p.op as operacion,
    p.vigente_desde,
    p.vigente_hasta,
    p.es_vigente,
    p.estado,
    p.perfil,
    p.zona_residencia_id,
    p.alta_implicita,
    p.alta_repetida,
    p.baja_sin_alta_previa,
    p.commit_ts_fuera_de_orden,
    to_hex(sha256(concat(p.fuente, '|', p.archivo, '|', coalesce(p.objeto_gcs, ''), '|', cast(p.ingest_date as string)))) as fuente_sk
from {{ ref('silver_padron_scd2') }} as p
join {{ ref('silver_usuarios') }} as u
    on u.modo_id = p.modo_id and u.llave_nativa = p.tarjeta
