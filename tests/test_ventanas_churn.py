"""Proyecto 2 (ADR-015): las features de churn solo miran los 28 días anteriores al corte y no usan estado final.

Prueba estática sobre dbt/models/features/churn/*.sql (sin red):
- ninguna ventana literal `interval N day` con N > 28, salvo que la expresión use var('horizonte_dias');
- churn_features.sql no usa columnas de estado FINAL de silver_usuarios ni vigente_hasta/es_vigente del padrón.
"""
import re

INTERVALO = re.compile(r"interval\s+(\d+)\s+day", re.IGNORECASE)
HORIZONTE = re.compile(r"""var\(\s*['"]horizonte_dias['"]\s*\)""")
PROHIBIDAS_USUARIOS = ("estado_padron", "en_padron", "n_registros_operacion", "zona_residencia")
PROHIBIDAS_PADRON = ("vigente_hasta", "es_vigente")


def _sin_comentarios(texto: str) -> str:
    texto = re.sub(r"\{#.*?#\}", "", texto, flags=re.DOTALL)
    return "\n".join(linea.split("--", 1)[0] for linea in texto.splitlines())


def _modelos_churn(dbt_dir):
    archivos = sorted((dbt_dir / "models" / "features" / "churn").glob("*.sql"))
    assert archivos, "No hay modelos en dbt/models/features/churn"
    return archivos


def test_ventanas_literales_no_superan_28_dias(dbt_dir):
    hallazgos = []
    for path in _modelos_churn(dbt_dir):
        codigo = _sin_comentarios(path.read_text(encoding="utf-8"))
        for i, linea in enumerate(codigo.splitlines(), 1):
            for m in INTERVALO.finditer(linea):
                if int(m.group(1)) > 28 and not HORIZONTE.search(linea):
                    hallazgos.append(f"{path.name}:{i}: {linea.strip()}")
    assert not hallazgos, "Ventanas de más de 28 días en features de churn:\n" + "\n".join(hallazgos)


def test_churn_features_sin_estado_final(dbt_dir):
    codigo = _sin_comentarios((dbt_dir / "models" / "features" / "churn" / "churn_features.sql").read_text(encoding="utf-8"))
    hallazgos = []
    if "silver_usuarios" in codigo:
        hallazgos += [c for c in PROHIBIDAS_USUARIOS if re.search(rf"\b{c}\b", codigo)]
    hallazgos += [c for c in PROHIBIDAS_PADRON if re.search(rf"\b{c}\b", codigo)]
    assert not hallazgos, f"churn_features usa columnas de estado final o futuro: {hallazgos}"
