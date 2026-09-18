{#-
  Seudonimización con HMAC-SHA256 y sal secreta (ADR-007, restricción dura 7).
  HMAC(K, m) = SHA256((K'⊕opad) || SHA256((K'⊕ipad) || m)).
  Los bloques (K'⊕ipad) y (K'⊕opad) viven en ops_secrets.hmac_key (dataset restringido),
  publicados por ingest/hmac_key_to_bq.py desde Secret Manager. La sal nunca aparece en el SQL.
  Uso: {{ hmac_sha256("CONCAT(modo, '|', llave_nativa)") }}  → STRING hex de 64 caracteres.
-#}
{% macro hmac_sha256(expr) -%}
TO_HEX(SHA256(CONCAT(
    (SELECT k_opad FROM `{{ target.project }}.ops_secrets.hmac_key` WHERE key_id = 'hmac-salt'),
    SHA256(CONCAT(
        (SELECT k_ipad FROM `{{ target.project }}.ops_secrets.hmac_key` WHERE key_id = 'hmac-salt'),
        CAST({{ expr }} AS BYTES)
    ))
)))
{%- endmacro %}
