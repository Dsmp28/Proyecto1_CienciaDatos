"""Constantes del Proyecto 2: semilla, rutas, esquema del dataset y parámetros económicos."""
from pathlib import Path

SEMILLA = 2026
N_FOLDS = 5

REPO = Path(__file__).resolve().parents[1]
ARTEFACTOS = REPO / "ml" / "artefactos"
MODELOS = REPO / "ml" / "modelos"
CACHE = ARTEFACTOS / "cache"
EVIDENCIA = REPO / "docs" / "evidence" / "p2"
FIGURAS = EVIDENCIA / "figuras"

PROYECTO = "cienciadatos-509301"
TABLA_DATASET = "features.churn_dataset"
TABLA_TARJETAS = "silver.silver_unidad_tarjetas_corte"

COLUMNA_ID = "unidad_id"
COLUMNA_CORTE = "corte"
COLUMNA_FECHA = "fecha_corte"
COLUMNA_ETIQUETA = "etiqueta"

FEATURES_NUM = [
    "n_abordajes_28d", "n_abordajes_14d", "n_abordajes_7d",
    "dias_activos_28d", "dias_activos_7d", "dias_desde_ultimo", "dias_desde_primero_28d",
    "semanas_activas_4", "ratio_ult14_prev14", "cv_semanal", "n_modos_28d",
    "share_tm", "share_tu", "share_mr", "share_am",
    "pct_hora_pico", "pct_fin_semana", "pct_feriado",
    "gasto_q_28d", "gasto_medio_q", "n_estaciones_28d", "n_zonas_28d", "pct_transbordo_interno",
    "n_tarjetas_activas_28d", "hora_media", "hora_sd",
    "viajes_mr_completos_28d", "duracion_media_mr_min", "n_eventos_padron_28d",
]
FEATURES_CAT = ["modo_principal", "zona_principal", "perfil_padron_a_t"]
FEATURES_BOOL = ["tiene_padron_a_t"]
FEATURES = FEATURES_NUM + FEATURES_CAT + FEATURES_BOOL

# Economía de la campaña de retención (ver docs/PLAN_P2.md, umbral): ganancia = 0.25 * 60 * TP - 5 * contactados.
COSTO_CONTACTO = 5.0
TASA_RETENCION = 0.25
VALOR_RETENIDO = 60.0

VERSION_MODELO = "1.0.0"
