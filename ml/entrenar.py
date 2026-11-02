"""CLI de entrenamiento. Fase 1: líneas base + regresión logística (L2, L1, ElasticNet) con los mismos folds de A.

    python -m ml.entrenar --fase 1 --origen bigquery
    python -m ml.entrenar --fase 1 --origen csv --ruta-csv ml/artefactos/cache/churn_dataset.csv

Solo usa el corte A. La fase 2 (ensamble, umbral, evaluación única en B) la agrega otro módulo.
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd
import sklearn

from ml import config as cfg
from ml.baselines import BaselineConstante, BaselineUnaFeature
from ml.datos import cargar_dataset, preparar_xy
from ml.figuras import figura_ap_vs_lambda
from ml.folds import obtener_folds
from ml.lineales import LAMBDAS, coeficientes, entrenar_logisticas, top_coeficientes
from ml.metricas import evaluar, resumen_cv, tabla_markdown

NOMBRES_OOF = {
    "baseline_constante": "Baseline constante (tasa de A)",
    "baseline_dias_desde_ultimo": "Baseline una feature (dias_desde_ultimo)",
    "logistica_l2": "Logística L2 (λ*)",
    "logistica_l1": "Logística L1 (λ*)",
    "logistica_elasticnet": "Logística ElasticNet 0.5 (λ*)",
}


def _por_fold(y, p, folds):
    return [evaluar(y[folds == k], p[folds == k]) for k in sorted(set(folds.tolist()))]


def _oof_baseline(modelo, X, y, folds):
    p = np.zeros(len(y))
    for k in sorted(set(folds.tolist())):
        tr, va = folds != k, folds == k
        p[va] = modelo.fit(X[tr], y[tr]).predict_proba(X[va])[:, 1]
    return p


def _versiones():
    return {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "numpy": np.__version__,
            "pandas": pd.__version__, "matplotlib": matplotlib.__version__, "joblib": joblib.__version__}


def fase1(args) -> dict:
    salida = Path(args.salida_dir) if args.salida_dir else cfg.EVIDENCIA
    arte = Path(args.artefactos_dir) if args.artefactos_dir else cfg.ARTEFACTOS
    salida.mkdir(parents=True, exist_ok=True)
    arte.mkdir(parents=True, exist_ok=True)
    lambdas = LAMBDAS if args.n_lambdas == len(LAMBDAS) else np.logspace(-4, 2, args.n_lambdas)
    tiempos = {}

    t = time.perf_counter()
    df = cargar_dataset(["A"], args.origen, args.ruta_csv)
    X, y_s, ids = preparar_xy(df)
    y = y_s.to_numpy()
    tiempos["carga_s"] = time.perf_counter() - t

    folds = obtener_folds(ids, y, arte / "folds_A.csv")

    t = time.perf_counter()
    oof = {
        "baseline_constante": _oof_baseline(BaselineConstante(), X, y, folds),
        "baseline_dias_desde_ultimo": _oof_baseline(BaselineUnaFeature(), X, y, folds),
    }
    res, modelos, oof_log = entrenar_logisticas(X, y, folds, lambdas=lambdas, tiempos=tiempos)
    tiempos["cv_s"] += time.perf_counter() - t - tiempos["cv_s"] - tiempos["ajuste_final_s"]  # suma las líneas base
    oof["logistica_l2"], oof["logistica_l1"], oof["logistica_elasticnet"] = (
        oof_log["L2"], oof_log["L1"], oof_log["ElasticNet"])

    filas, metricas = [], {}
    for clave, p in oof.items():
        r = resumen_cv(_por_fold(y, p, folds))
        metricas[clave] = r
        pd.DataFrame({"unidad_id": ids, "fold": folds, "y": y, "p": p}).to_csv(arte / f"oof_A_{clave}.csv", index=False)
        filas.append({"modelo": NOMBRES_OOF[clave], "AP media": r["ap_media"], "AP sd": r["ap_sd"],
                      "ROC-AUC media": r["roc_auc_media"], "Brier media": r["brier_media"]})
    tasa = float(y.mean())

    # Coeficientes del mejor castigo (por AP de validación media en λ*)
    optimos = res[res["es_optimo"]].set_index("castigo")
    mejor_castigo = optimos["ap_val_media"].idxmax()
    coef = coeficientes(modelos[mejor_castigo])
    hacia, protec = top_coeficientes(coef, 5)

    cabecera = (f"Corte A: {len(y)} unidades, tasa de churn {tasa:.4f}; CV estratificada {cfg.N_FOLDS} folds "
                f"(semilla {cfg.SEMILLA}, folds persistidos en `ml/artefactos/folds_A.csv`).\n\n")
    (salida / "fase1_modelos.md").write_text(
        "# Fase 1: comparación de modelos (validación cruzada en A)\n\n" + cabecera
        + tabla_markdown(filas, ["modelo", "AP media", "AP sd", "ROC-AUC media", "Brier media"])
        + f"\nMétrica principal: Average Precision. AP del baseline constante = tasa positiva = {tasa:.4f}. "
          "El Brier del baseline por ranking no es una probabilidad calibrada.\n")
    lam_filas = [{"castigo": r.castigo, "λ": r._2, "C": r.C, "AP val media": r.ap_val_media, "AP val sd": r.ap_val_sd,
                  "AP train media": r.ap_train_media, "λ*": "★" if r.es_optimo else ""}
                 for r in res.itertuples()]
    (salida / "fase1_lambda.md").write_text(
        "# Fase 1: AP por castigo y λ (media y sd en validación; media en entrenamiento)\n\n"
        + cabecera + tabla_markdown(lam_filas, ["castigo", "λ", "C", "AP val media", "AP val sd", "AP train media", "λ*"],
                                    formato="{:.5g}")
        + f"\nLínea base (tasa positiva): {tasa:.4f}. λ* = AP de validación media máxima (empate: mayor λ).\n")
    (salida / "fase1_coeficientes.md").write_text(
        f"# Fase 1: coeficientes de la logística {mejor_castigo} (λ* = {optimos.loc[mejor_castigo, 'lambda']:.4g})\n\n"
        "Coeficientes sobre features estandarizadas (z) e indicadores one-hot; positivo = empuja hacia churn.\n\n"
        "## Top 5 hacia churn\n\n" + tabla_markdown(hacia.to_dict("records"),
                                                    ["feature", "coeficiente"])
        + "\n## Top 5 protectores\n\n" + tabla_markdown(protec.to_dict("records"), ["feature", "coeficiente"]))
    figura = figura_ap_vs_lambda(res, salida / "figuras" / "ap_vs_lambda.png", linea_base=tasa)

    tiempos["total_s"] = sum(tiempos.values())
    (salida / "fase1_tiempos.md").write_text(
        "# Fase 1: tiempos de ejecución (segundos)\n\n"
        + tabla_markdown([{"etapa": k.removesuffix("_s"), "segundos": v} for k, v in tiempos.items()],
                         ["etapa", "segundos"], formato="{:.2f}"))

    resultados = {
        "fase": 1, "semilla": cfg.SEMILLA, "n_folds": cfg.N_FOLDS, "n_unidades_A": int(len(y)), "tasa_positiva_A": tasa,
        "versiones": _versiones(), "lambdas": [float(x) for x in lambdas],
        "metricas_cv": metricas, "mejor_castigo": mejor_castigo,
        "lambda_optimo": {c: float(optimos.loc[c, "lambda"]) for c in optimos.index},
        "grilla": res.to_dict("records"),
        "coeficientes_mejor": coef.to_dict("records"),
        "tiempos_s": tiempos, "figura": str(figura),
    }
    (arte / "fase1_resultados.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False) + "\n")
    return resultados


def main(argv=None) -> dict:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fase", type=int, required=True, choices=[1, 2])
    p.add_argument("--origen", choices=["bigquery", "csv"], default="bigquery")
    p.add_argument("--ruta-csv", default=None)
    p.add_argument("--salida-dir", default=None, help="por defecto docs/evidence/p2")
    p.add_argument("--artefactos-dir", default=None, help="por defecto ml/artefactos")
    p.add_argument("--n-lambdas", type=int, default=len(LAMBDAS), help="puntos de la grilla logspace(-4, 2); 13 por defecto")
    args = p.parse_args(argv)
    if args.fase == 2:
        raise SystemExit("La fase 2 aún no está implementada en ml.entrenar.")
    r = fase1(args)
    for k, v in r["metricas_cv"].items():
        print(f"{k:30s} AP={v['ap_media']:.4f}±{v['ap_sd']:.4f} AUC={v['roc_auc_media']:.4f} Brier={v['brier_media']:.4f}")
    print("tiempos (s):", {k: round(v, 2) for k, v in r["tiempos_s"].items()})
    return r


if __name__ == "__main__":
    main()
