"""Preprocesamiento y pipeline sklearn (serializable con joblib)."""
from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from ml import config as cfg


def _a_entero(X):
    """Booleanas a 0/1 (función de módulo, no lambda, para poder serializarla)."""
    return X.astype("int64")


def construir_preprocesador() -> ColumnTransformer:
    """Numéricas: mediana + indicador de nulos (ratio_ult14_prev14 y duracion_media_mr_min son NULL con significado
    propio) + estandarización. Categóricas: 'SIN_DATO' + one-hot (categorías nuevas se ignoran). Booleanas: 0/1."""
    num = Pipeline([
        ("imputar", SimpleImputer(strategy="median", add_indicator=True)),
        ("escalar", StandardScaler()),
    ])
    cat = Pipeline([
        ("imputar", SimpleImputer(strategy="constant", fill_value="SIN_DATO")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    boo = FunctionTransformer(_a_entero, feature_names_out="one-to-one", validate=False)
    return ColumnTransformer(
        [("num", num, cfg.FEATURES_NUM), ("cat", cat, cfg.FEATURES_CAT), ("bool", boo, cfg.FEATURES_BOOL)],
        remainder="drop", verbose_feature_names_out=False,
    )


def construir_pipeline(modelo) -> Pipeline:
    return Pipeline([("pre", construir_preprocesador()), ("modelo", modelo)])
