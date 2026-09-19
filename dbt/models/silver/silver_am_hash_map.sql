-- Silver · tabla de correspondencia usuario_base_id -> user_hash de Aerómetro (ADR-008).
-- El generador emite user_hash = md5('am' || i)[:12] sin sal; se invierte por diccionario calculando el hash para
-- i en 1..max_usuario_base_id. Es la lección de seguridad del proyecto: por eso la Agencia seudonimiza con
-- HMAC y sal secreta (ADR-007). Determinista: idéntica en cada corrida.
select
    i as usuario_base_id,
    left(to_hex(md5(concat('am', cast(i as string)))), 12) as user_hash
from unnest(generate_array(1, {{ var('max_usuario_base_id') }})) as i
