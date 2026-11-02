"""CLI de entrenamiento. Fase 1: líneas base + regresión logística (L2, L1, ElasticNet) con los mismos folds de A.

    python -m ml.entrenar --fase 1 --origen bigquery
    python -m ml.entrenar --fase 1 --origen csv --ruta-csv ml/artefactos/cache/churn_dataset.csv

Fase 2: ensambles (HistGradientBoosting, RandomForest opcional), sesgo-varianza, importancia por permutación,
umbral por ganancia y modelo final guardado.

    python -m ml.entrenar --fase 2 --origen bigquery [--modelo-final hgb] [--con-rf]

Solo usa el corte A (la evaluación única en B vive en `ml/evaluar_b.py`).
"""
from __future__ import annotations

import argparse
import json
import platform
import time
import warnings
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd
import sklearn

from ml import config as cfg
from ml.baselines import BaselineConstante, BaselineUnaFeature
from ml.datos import cargar_dataset, preparar_xy
from ml.ensamble import (GRILLA_HGB, entrenar_ensamble, entrenar_random_forest, importancia_permutacion,
                         tabla_sesgo_varianza, UMBRAL_BRECHA_ALTA, UMBRAL_BRECHA_PEQUENA, UMBRAL_MEJORA_BAJA)
from ml.figuras import figura_ap_vs_lambda
from ml.folds import obtener_folds
from ml.lineales import LAMBDAS, _logistica, coeficientes, entrenar_logisticas, top_coeficientes
from ml.metricas import evaluar, resumen_cv, tabla_markdown
from ml.persistencia import guardar_modelo
from ml.pipeline import construir_pipeline
from ml.umbral import (curva_ganancia, elegir_umbral, figura_curva_ganancia, ganancia_por_contactado, nota_calibracion,
                       umbral_teorico)

NOMBRES_OOF = {
    "baseline_constante": "Baseline constante (tasa de A)",
    "baseline_dias_desde_ultimo": "Baseline una feature (dias_desde_ultimo)",
    "logistica_l2": "Logística L2 (λ*)",
    "logistica_l1": "Logística L1 (λ*)",
    "logistica_elasticnet": "Logística ElasticNet 0.5 (λ*)",
    "hgb": "HistGradientBoosting (mejor de la grilla)",
    "rf": "RandomForest (400 árboles, min_samples_leaf=5)",
}
CLAVES_FASE1 = ["baseline_constante", "baseline_dias_desde_ultimo", "logistica_l2", "logistica_l1", "logistica_elasticnet"]
CASTIGO_DE = {"logistica_l2": "L2", "logistica_l1": "L1", "logistica_elasticnet": "ElasticNet"}
ALIAS_MODELO_FINAL = {"logistica_l2": "logistica_l2", "logistica_l1": "logistica_l1",
                      "logistica_en": "logistica_elasticnet", "hgb": "hgb", "rf": "rf"}
GRILLA_HGB_REDUCIDA = {"learning_rate": [0.1], "max_iter": [30, 60], "max_leaf_nodes": [15], "l2_regularization": [0.0, 1.0]}


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


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _fase1_reutilizable(arte: Path, ids, y) -> bool:
    if not (arte / "fase1_resultados.json").exists():
        return False
    for clave in CLAVES_FASE1:
        ruta = arte / f"oof_A_{clave}.csv"
        if not ruta.exists():
            return False
        d = pd.read_csv(ruta, dtype={"unidad_id": "object"})
        if len(d) != len(y) or list(d["unidad_id"]) != list(ids) or not (d["y"].to_numpy() == y).all():
            return False
    return True


def _ap_train_baseline(clave, X, y, folds):
    """AP medio sobre las filas de entrenamiento de cada fold (el baseline constante rinde la tasa de A)."""
    from sklearn.metrics import average_precision_score
    vals = []
    for k in sorted(set(folds.tolist())):
        tr = folds != k
        if clave == "baseline_constante":
            vals.append(average_precision_score(y[tr], np.full(tr.sum(), y[tr].mean())))
        else:
            vals.append(average_precision_score(y[tr], BaselineUnaFeature().puntaje(X[tr])))
    return float(np.mean(vals))


def _md_tabla_hgb(res: pd.DataFrame) -> str:
    cols = ["learning_rate", "max_iter", "max_leaf_nodes", "l2_regularization", "ap_val_media", "ap_val_sd",
            "ap_train_media"]
    filas = [{**r, "★": "★" if r["es_optimo"] else ""} for r in res.to_dict("records")]
    return tabla_markdown(filas, cols + ["★"], formato="{:.5g}")


def fase2(args) -> dict:
    salida = Path(args.salida_dir) if args.salida_dir else cfg.EVIDENCIA
    arte = Path(args.artefactos_dir) if args.artefactos_dir else cfg.ARTEFACTOS
    modelos_dir = Path(args.modelos_dir) if args.modelos_dir else (arte / "modelos" if args.artefactos_dir else cfg.MODELOS)
    salida.mkdir(parents=True, exist_ok=True)
    arte.mkdir(parents=True, exist_ok=True)
    tiempos = {}

    t = time.perf_counter()
    df = cargar_dataset(["A"], args.origen, args.ruta_csv)
    X, y_s, ids = preparar_xy(df)
    y = y_s.to_numpy()
    tiempos["carga_s"] = time.perf_counter() - t
    folds = obtener_folds(ids, y, arte / "folds_A.csv")
    tasa = float(y.mean())

    # Fase 1: se reutilizan folds y OOF si existen y corresponden a estos datos; si no, se recalculan.
    t = time.perf_counter()
    reutilizada = _fase1_reutilizable(arte, ids, y)
    if not reutilizada:
        fase1(args)
    f1 = json.loads((arte / "fase1_resultados.json").read_text())
    oof = {c: pd.read_csv(arte / f"oof_A_{c}.csv")["p"].to_numpy() for c in CLAVES_FASE1}
    tiempos["fase1_reutilizada_o_recalculada_s"] = time.perf_counter() - t
    grilla_f1 = pd.DataFrame(f1["grilla"])

    grilla = GRILLA_HGB_REDUCIDA if args.grilla_hgb == "reducida" else GRILLA_HGB
    res_hgb, modelo_hgb, oof["hgb"], pipes_hgb = entrenar_ensamble(X, y, folds, grilla=grilla, tiempos=tiempos)
    mejor_hgb = res_hgb[res_hgb["es_optimo"]].iloc[0]
    modelos_final = {"hgb": modelo_hgb}
    con_rf = args.con_rf or args.modelo_final == "rf"
    fila_rf = None
    if con_rf:
        fila_rf, modelos_final["rf"], oof["rf"] = entrenar_random_forest(X, y, folds, tiempos=tiempos)

    # Métricas por modelo (misma resumen_cv sobre las OOF por fold) y AP de entrenamiento
    metricas, ap_train = {}, {}
    for clave, p in oof.items():
        metricas[clave] = resumen_cv(_por_fold(y, p, folds))
        pd.DataFrame({"unidad_id": ids, "fold": folds, "y": y, "p": p}).to_csv(arte / f"oof_A_{clave}.csv", index=False)
    for clave in ("baseline_constante", "baseline_dias_desde_ultimo"):
        ap_train[clave] = _ap_train_baseline(clave, X, y, folds)
    for clave, castigo in CASTIGO_DE.items():
        opt = grilla_f1[(grilla_f1["castigo"] == castigo) & grilla_f1["es_optimo"]].iloc[0]
        ap_train[clave] = float(opt["ap_train_media"])
    ap_train["hgb"] = float(mejor_hgb["ap_train_media"])
    if fila_rf:
        ap_train["rf"] = float(fila_rf["ap_train_media"])

    filas = [{"modelo": NOMBRES_OOF[c], "AP train": ap_train[c], "AP val media": m["ap_media"], "AP val sd": m["ap_sd"],
              "ROC-AUC media": m["roc_auc_media"], "Brier media": m["brier_media"]} for c, m in metricas.items()]
    cabecera = (f"Corte A: {len(y)} unidades, tasa de churn {tasa:.4f}; CV estratificada {cfg.N_FOLDS} folds "
                f"(semilla {cfg.SEMILLA}, los mismos folds de la fase 1: `ml/artefactos/folds_A.csv`).\n\n")
    (salida / "fase2_modelos.md").write_text(
        "# Fase 2: comparación de modelos (tabla 1.4 más ensambles)\n\n" + cabecera
        + tabla_markdown(filas, ["modelo", "AP train", "AP val media", "AP val sd", "ROC-AUC media", "Brier media"])
        + f"\nAP del baseline constante = tasa positiva = {tasa:.4f}. AP train = media en las filas de entrenamiento "
          "de cada fold. Grilla de HistGradientBoosting (★ = elegida por AP de validación):\n\n" + _md_tabla_hgb(res_hgb)
        + ("\nRandomForest: n_estimators=400, min_samples_leaf=5, sin grilla.\n" if fila_rf else ""))

    # Sesgo-varianza
    sv = tabla_sesgo_varianza({NOMBRES_OOF[c]: {"ap_train": ap_train[c], "ap_val": metricas[c]["ap_media"], "tasa": tasa}
                               for c in metricas if c != "baseline_constante"}, tasa)
    (salida / "fase2_sesgo_varianza.md").write_text(
        "# Fase 2: sesgo y varianza (AP de entrenamiento contra validación)\n\n"
        + tabla_markdown(sv.to_dict("records"), ["modelo", "ap_train", "ap_val", "brecha", "diagnostico"])
        + "\nReglas automáticas (umbrales sobre AP en [0, 1]):\n\n"
          f"- **varianza alta**: brecha = AP train − AP val ≥ {UMBRAL_BRECHA_ALTA}.\n"
          f"- **sesgo alto**: brecha < {UMBRAL_BRECHA_PEQUENA} y AP val − tasa positiva ({tasa:.4f}) < {UMBRAL_MEJORA_BAJA} "
          "(rinde poco por encima del azar tanto en train como en val).\n- **equilibrado**: el resto.\n\n"
          "Las etiquetas son una guía automática; el informe debe interpretarlas.\n")

    # Importancia por permutación (HGB, en validación de cada fold)
    t = time.perf_counter()
    imp = importancia_permutacion(pipes_hgb, X, y, folds, n_repeats=args.n_repeats_perm)
    tiempos["importancia_permutacion_s"] = time.perf_counter() - t
    (salida / "fase2_importancias.md").write_text(
        "# Fase 2: importancia por permutación (HistGradientBoosting, top 10)\n\n"
        "Caída media de Average Precision al permutar cada feature en el fold de validación (10 repeticiones por "
        "fold, promedio entre los 5 folds); sd = desviación entre folds.\n\n"
        + tabla_markdown(imp.to_dict("records"), ["feature", "importancia_media", "sd"], formato="{:.5f}"))

    # Modelo final, umbral, ganancia, calibración
    candidatos = [c for c in ("logistica_l2", "logistica_l1", "logistica_elasticnet", "hgb", "rf") if c in metricas]
    final = (ALIAS_MODELO_FINAL[args.modelo_final] if args.modelo_final
             else max(candidatos, key=lambda c: metricas[c]["ap_media"]))
    if final in CASTIGO_DE:
        castigo = CASTIGO_DE[final]
        lam = float(f1["lambda_optimo"][castigo])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            modelo = construir_pipeline(_logistica(castigo, lam)).fit(X, y)
        params = {"castigo": castigo, "lambda": lam}
    elif final == "hgb":
        modelo = modelo_hgb
        params = {k: mejor_hgb[k].item() if hasattr(mejor_hgb[k], "item") else mejor_hgb[k] for k in grilla}
    else:
        modelo = modelos_final["rf"]
        params = {"n_estimators": 400, "min_samples_leaf": 5}

    curva = curva_ganancia(y, oof[final])
    u_est = elegir_umbral(curva)
    fila_u = curva[np.isclose(curva["umbral"], u_est)].iloc[0]
    curva.to_csv(arte / "curva_ganancia_oof_A.csv", index=False)
    figura_curva_ganancia(curva, u_est, salida / "figuras" / "ganancia_vs_umbral.png")
    cal = nota_calibracion(y, oof[final], u_est, salida / "calibracion.md")
    g_todos = ganancia_por_contactado() * y.sum() - cfg.COSTO_CONTACTO * len(y)
    g_u = float(fila_u["ganancia_q"])
    tp, fp = int(fila_u["tp"]), int(fila_u["fp"])
    (salida / "umbral.md").write_text(
        "# Umbral de decisión por ganancia económica\n\n"
        f"Escenario: contactar cuesta Q{cfg.COSTO_CONTACTO:g}; si la persona iba a abandonar (y=1), la campaña la retiene "
        f"con probabilidad {cfg.TASA_RETENCION:.0%} y retenerla vale Q{cfg.VALOR_RETENIDO:g}.\n\n"
        f"- Ganancia esperada por contactado: {cfg.TASA_RETENCION:g} × {cfg.VALOR_RETENIDO:g} × y − {cfg.COSTO_CONTACTO:g} "
        f"= {ganancia_por_contactado():g}·y − {cfg.COSTO_CONTACTO:g}.\n"
        "- G(u) = Σ_{p ≥ u} (0.25·60·y − 5) = 15·TP − 5·(TP + FP).\n"
        f"- Umbral teórico: contactar si 15·p > 5, es decir p > {cfg.COSTO_CONTACTO:g} / ({cfg.TASA_RETENCION:g}·"
        f"{cfg.VALOR_RETENIDO:g}) = **{umbral_teorico():.4f}** (válido si p está calibrada).\n"
        f"- Umbral empírico u* = argmax G(u) sobre las predicciones fuera de muestra (OOF) de A del modelo "
        f"`{final}`, malla de 201 umbrales en [0, 1] (empate: el mayor).\n\n"
        f"## Cuenta con u* = {u_est:.3f}\n\n"
        f"- Contactados = {int(fila_u['contactados'])} de {len(y)} (TP = {tp}, FP = {fp}).\n"
        f"- G = 15·{tp} − 5·({tp} + {fp}) = {15 * tp} − {5 * (tp + fp)} = **Q{g_u:.2f}** "
        f"(Q{g_u / len(y) * 1000:.2f} por cada 1 000 personas).\n"
        f"- Referencias: contactar a todos = Q{g_todos:.2f}; no contactar a nadie = Q0.00.\n"
        f"- Precisión = {fila_u['precision']:.4f}; recall = {fila_u['recall']:.4f}.\n\n"
        "![ganancia vs umbral](figuras/ganancia_vs_umbral.png)\n\n"
        + ("Nota: si u* = 1 no hay umbral rentable con este modelo (G máxima = 0 sin contactar a nadie).\n"
           if u_est >= 1.0 else "") 
        + f"\nCalibración: ver `calibracion.md` (Brier {cal['brier']:.4f}; |u* − 1/3| = {cal['desvio_umbral']:.3f}"
        + (", supera 0.1: se deja constancia, sin recalibrar" if cal["aviso_desvio"] else "") + ").\n")

    mejor_lineal = max((c for c in CASTIGO_DE), key=lambda c: metricas[c]["ap_media"])
    (salida / "fase2_decision.md").write_text(
        "# Fase 2: decisión del modelo (PLANTILLA: la redacta el informe)\n\n"
        f"- Modelo con mayor AP de validación: `{max(candidatos, key=lambda c: metricas[c]['ap_media'])}`; modelo final guardado: `{final}`.\n"
        f"- Mejor lineal: `{mejor_lineal}` AP val {metricas[mejor_lineal]['ap_media']:.4f} ± {metricas[mejor_lineal]['ap_sd']:.4f} "
        f"(train {ap_train[mejor_lineal]:.4f}).\n"
        f"- HistGradientBoosting: AP val {metricas['hgb']['ap_media']:.4f} ± {metricas['hgb']['ap_sd']:.4f} "
        f"(train {ap_train['hgb']:.4f}); parámetros {params if final == 'hgb' else dict(mejor_hgb[list(grilla)])}.\n"
        + (f"- RandomForest: AP val {metricas['rf']['ap_media']:.4f} ± {metricas['rf']['ap_sd']:.4f} (train {ap_train['rf']:.4f}).\n" if fila_rf else "")
        + f"- Baseline constante (tasa): {tasa:.4f}; baseline una feature: AP val {metricas['baseline_dias_desde_ultimo']['ap_media']:.4f}.\n"
        f"- Umbral u* = {u_est:.3f} (teórico {umbral_teorico():.3f}); ganancia OOF Q{g_u:.2f} (Q{g_u / len(y) * 1000:.2f} por 1 000).\n"
        f"- Top 3 por permutación: {', '.join(imp['feature'].head(3))}.\n\n"
        "## Decisión\n\n_Por redactar: modelo elegido, por qué (rendimiento, brecha train/val, interpretabilidad, costo), "
        "y qué se descartó._\n")

    meta_modelo = {"modelo": final, "parametros": params, "umbral": float(u_est), "umbral_teorico": umbral_teorico(),
                   "metricas_cv": metricas[final], "ap_train_cv": ap_train[final], "ganancia_oof_q": g_u,
                   "tasa_positiva_A": tasa, "n_unidades_A": int(len(y))}
    ruta_modelo = guardar_modelo(modelo, meta_modelo, directorio=modelos_dir, version=cfg.VERSION_MODELO)

    tiempos["total_s"] = sum(v for k, v in tiempos.items() if k != "total_s")
    (salida / "fase2_tiempos.md").write_text(
        "# Fase 2: tiempos de ejecución (segundos)\n\n"
        + tabla_markdown([{"etapa": k.removesuffix("_s"), "segundos": v} for k, v in tiempos.items()],
                         ["etapa", "segundos"], formato="{:.2f}"))
    resultados = {
        "fase": 2, "semilla": cfg.SEMILLA, "n_folds": cfg.N_FOLDS, "n_unidades_A": int(len(y)), "tasa_positiva_A": tasa,
        "versiones": _versiones(), "fase1_reutilizada": reutilizada, "grilla_hgb": res_hgb.to_dict("records"),
        "metricas_cv": metricas, "ap_train": ap_train, "sesgo_varianza": sv.to_dict("records"),
        "importancias": imp.to_dict("records"), "modelo_final": final, "parametros": params,
        "u_estrella": float(u_est), "u_teorico": umbral_teorico(), "ganancia_oof_q": g_u,
        "ganancia_oof_q_por_1000": g_u / len(y) * 1000, "ganancia_contactar_todos_q": float(g_todos),
        "calibracion": cal, "ruta_modelo": str(ruta_modelo), "tiempos_s": tiempos,
    }
    (arte / "fase2_resultados.json").write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False, default=_jsonable) + "\n")
    return resultados


def main(argv=None) -> dict:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fase", type=int, required=True, choices=[1, 2])
    p.add_argument("--origen", choices=["bigquery", "csv"], default="bigquery")
    p.add_argument("--ruta-csv", default=None)
    p.add_argument("--salida-dir", default=None, help="por defecto docs/evidence/p2")
    p.add_argument("--artefactos-dir", default=None, help="por defecto ml/artefactos")
    p.add_argument("--modelo-final", choices=sorted(ALIAS_MODELO_FINAL), default=None,
                   help="fase 2: modelo que se guarda y se usa para el umbral (por defecto el de mayor AP de validación)")
    p.add_argument("--con-rf", action="store_true", help="fase 2: entrena también el RandomForest")
    p.add_argument("--grilla-hgb", choices=["completa", "reducida"], default="completa",
                   help="fase 2: 'reducida' es solo para pruebas rápidas")
    p.add_argument("--modelos-dir", default=None, help="fase 2: por defecto ml/modelos (o <artefactos>/modelos si se da --artefactos-dir)")
    p.add_argument("--n-repeats-perm", type=int, default=10, help="fase 2: repeticiones de la permutación")
    p.add_argument("--n-lambdas", type=int, default=len(LAMBDAS), help="puntos de la grilla logspace(-4, 2); 13 por defecto")
    args = p.parse_args(argv)
    if args.fase == 2:
        r = fase2(args)
        print(f"modelo final: {r['modelo_final']}  u*={r['u_estrella']:.3f}  ganancia OOF={r['ganancia_oof_q']:.2f} Q")
        for k, v in r["metricas_cv"].items():
            print(f"{k:30s} AP={v['ap_media']:.4f}±{v['ap_sd']:.4f} AP_train={r['ap_train'][k]:.4f}")
        print("tiempos (s):", {k: round(v, 2) for k, v in r["tiempos_s"].items()})
        return r
    r = fase1(args)
    for k, v in r["metricas_cv"].items():
        print(f"{k:30s} AP={v['ap_media']:.4f}±{v['ap_sd']:.4f} AUC={v['roc_auc_media']:.4f} Brier={v['brier_media']:.4f}")
    print("tiempos (s):", {k: round(v, 2) for k, v in r["tiempos_s"].items()})
    return r


if __name__ == "__main__":
    main()
