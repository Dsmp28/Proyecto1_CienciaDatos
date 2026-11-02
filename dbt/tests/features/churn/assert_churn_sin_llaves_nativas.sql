-- La salida del dataset de churn no expone llaves nativas ni el identificador base (restricción dura 7, como
-- assert_gold_sin_llaves_nativas). Consulta el INFORMATION_SCHEMA del dataset de churn_dataset tras construirlo.
-- Si devuelve filas, la prueba falla.
{% set d = ref('churn_dataset') %}
select table_name, column_name
from `{{ d.database }}`.`{{ d.schema }}`.INFORMATION_SCHEMA.COLUMNS
where table_name like 'churn_%'  -- todas las tablas de churn del dataset features, no solo churn_dataset
  and (lower(column_name) in ('llave_nativa', 'tarjeta', 'tarjetas', 'num_tarjeta', 'card', 'user_hash', 'usuario_base_id')
       or lower(column_name) like '%llave%')
