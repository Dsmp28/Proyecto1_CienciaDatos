-- Auditoría de recorte · Proyecto 2 (entregable 1.3). BORRADOR DELIBERADAMENTE INGENUO, NO es parte del pipeline ni del DAG
-- (solo lleva el tag auditoria_recorte). Reproduce las features "antes de corregir" para demostrar que la prueba de recorte
-- (ml/prueba_recorte.py) detecta las fugas del futuro. Una fila por (unidad_id, fecha_corte) de la población en_poblacion.
-- Features con fuga:
--   perfil_padron_final        silver_usuarios.perfil es el estado FINAL del padrón (después de todo el log CDC): un cambio
--                              de perfil posterior a t se filtra al corte t.
--   estado_padron_final        silver_usuarios.estado_padron es el estado final (ACTIVA/INACTIVA/SIN_PADRON): una baja
--                              posterior a t, o un alta posterior, ya está reflejada.
--   es_vigente_padron          silver_padron_scd2.es_vigente del último evento de la tarjeta sin filtrar vigente_desde < t:
--                              "no hay evento siguiente" depende de eventos que ocurren después de t.
--   duracion_media_mr_min_sin_filtro  viajes de MetroRiel con entrada en [t-28, t) pero sin exigir salida < t: la salida de
--                              un viaje abierto en t es información del futuro (con recorte la duración desaparece). Fuga latente: en el corte A
--                              ningún viaje cruza t, así que la prueba no la detecta (0 filas); se conserva por rigor.
--   n_registros_operacion      silver_usuarios.n_registros_operacion cuenta las filas del catálogo del operador en TODO el
--                              periodo, incluidas las posteriores a t.
-- Controles (correctas, NO deben fallar): n_abordajes_28d y dias_desde_ultimo, tomadas de churn_features.
{{ config(materialized='table', cluster_by=['corte']) }}

with poblacion as (
    select corte, fecha_corte, unidad_id
    from {{ ref('churn_poblacion') }}
    where en_poblacion
),
usuarios as (
    select modo_id, llave_nativa, usuario_unificado_sk as unidad_id, perfil, estado_padron, n_registros_operacion
    from {{ ref('silver_usuarios') }}
    where usuario_unificado_sk is not null
),
final_usuario as (
    select
        unidad_id,
        min(perfil) as perfil_padron_final,
        min(estado_padron) as estado_padron_final,
        sum(n_registros_operacion) as n_registros_operacion
    from usuarios
    group by unidad_id
),
vigente as (
    select u.unidad_id,
        array_agg(p.es_vigente order by p.seq desc, p.tarjeta limit 1)[offset(0)] as es_vigente_padron
    from {{ ref('silver_padron_scd2') }} as p
    inner join usuarios as u on u.modo_id = p.modo_id and u.llave_nativa = p.tarjeta
    group by u.unidad_id
),
mr as (
    select po.corte, po.unidad_id, round(safe_divide(sum(v.duracion_s), count(v.duracion_s) * 60), 6) as duracion_media_mr_min_sin_filtro
    from {{ ref('silver_metroriel_viajes') }} as v
    inner join usuarios as u on u.modo_id = v.modo_id and u.llave_nativa = v.llave_nativa
    inner join poblacion as po on po.unidad_id = u.unidad_id
       and v.fecha >= date_sub(po.fecha_corte, interval {{ var('ventana_max_dias') }} day)
       and v.fecha < po.fecha_corte
    group by po.corte, po.unidad_id
)
select
    p.unidad_id,
    p.fecha_corte,
    p.corte,
    f.perfil_padron_final,
    f.estado_padron_final,
    vg.es_vigente_padron,
    mr.duracion_media_mr_min_sin_filtro,
    f.n_registros_operacion,
    cf.n_abordajes_28d,
    cf.dias_desde_ultimo
from poblacion as p
left join final_usuario as f on f.unidad_id = p.unidad_id
left join vigente as vg on vg.unidad_id = p.unidad_id
left join mr on mr.corte = p.corte and mr.unidad_id = p.unidad_id
left join {{ ref('churn_features') }} as cf on cf.corte = p.corte and cf.unidad_id = p.unidad_id
