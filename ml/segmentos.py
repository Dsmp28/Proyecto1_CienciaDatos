"""Segmentación de personas por comportamiento (2.3): KMeans sobre las features numéricas de A, sin etiqueta.

    python -m ml.segmentos --origen bigquery
    python -m ml.segmentos --origen csv --ruta-csv ml/artefactos/cache/churn_dataset.csv

La etiqueta de A solo se usa DESCRIPTIVAMENTE (tasa de abandono por segmento) y para estratificar la muestra de la
silueta; nunca para agrupar. No toca B.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.base import clone  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.metrics import silhouette_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

from ml import config as cfg  # noqa: E402
from ml.datos import cargar_dataset, preparar_xy  # noqa: E402
from ml.metricas import tabla_markdown  # noqa: E402
from ml.pipeline import construir_preprocesador  # noqa: E402

N_DISCRIMINANTES = 8


def _preprocesador_numerico():
    """El mismo pipeline numérico del preprocesador común (mediana + estandarización), sin indicadores de nulos
    (columnas binarias que distorsionarían las distancias euclídeas)."""
    num = clone(dict((n, t) for n, t, _ in construir_preprocesador().transformers)["num"])
    num.set_params(imputar__add_indicator=False)
    return num


def escalar_numericas(X: pd.DataFrame):
    pre = _preprocesador_numerico()
    return pre.fit_transform(X[cfg.FEATURES_NUM]), pre


def _codo(ks, inercias) -> int:
    """k del codo: punto más alejado de la recta que une (k_min, inercia_max) con (k_max, inercia_min),
    con ambos ejes normalizados a [0, 1] (heurística tipo 'kneedle')."""
    x = (np.asarray(ks, float) - min(ks)) / (max(ks) - min(ks))
    yv = np.asarray(inercias, float)
    yv = (yv - yv.min()) / (yv.max() - yv.min()) if yv.max() > yv.min() else np.zeros_like(yv)
    dist = np.abs(x + yv - 1) / np.sqrt(2)  # recta de (0,1) a (1,0)
    return int(ks[int(np.argmax(dist))])


def _nombre_segmento(z: pd.Series) -> str:
    """Nombre sugerido a partir de los centroides estandarizados (z) de unas pocas features interpretables."""
    ab, dias, modos, ratio = (z.get(c, 0.0) for c in
                              ("n_abordajes_28d", "dias_desde_ultimo", "n_modos_28d", "ratio_ult14_prev14"))
    freq = "frecuentes" if ab > 0.5 else "ocasionales" if ab < -0.5 else "regulares"
    extra = []
    if modos > 0.5:
        extra.append("multimodales")
    if ratio < -0.5 or dias > 0.5:
        extra.append("en declive")
    elif ratio > 0.5 and dias <= 0:
        extra.append("en ascenso")
    return " ".join([freq, *extra])


def segmentar(X: pd.DataFrame, y=None, ks=range(2, 11), n_init: int = 10, max_muestra: int = 10_000,
              semilla: int = cfg.SEMILLA, tiempos: dict | None = None) -> dict:
    """Segmenta con las FEATURES_NUM de `X`. `y` (opcional) solo se usa para la tasa de abandono descriptiva y para
    estratificar la muestra de la silueta. Devuelve un dict con:
    - tabla_k: DataFrame (k, inercia, silueta); k_elegido (silueta máxima) y k_codo.
    - etiquetas, tabla_segmentos (segmento, nombre, tamaño, %, tasa de abandono, medianas de las 8 features más
      discriminantes, en unidades originales), discriminantes, pca (coordenadas 2D) y varianza_pca.
    """
    t0 = time.perf_counter()
    X = X.reset_index(drop=True)
    ks = list(ks)
    Z, _ = escalar_numericas(X)
    n = len(Z)
    idx = np.arange(n)
    if n > max_muestra:
        estrato = None if y is None else np.asarray(y)
        idx, _ = train_test_split(idx, train_size=max_muestra, random_state=semilla, stratify=estrato)
    filas, modelos = [], {}
    for k in ks:
        km = KMeans(n_clusters=k, n_init=n_init, random_state=semilla).fit(Z)
        modelos[k] = km
        sil = float(silhouette_score(Z[idx], km.labels_[idx])) if len(set(km.labels_[idx])) > 1 else float("nan")
        filas.append({"k": k, "inercia": float(km.inertia_), "silueta": sil})
    tabla_k = pd.DataFrame(filas)
    k_elegido = int(tabla_k.loc[tabla_k["silueta"].idxmax(), "k"])
    k_codo = _codo(ks, tabla_k["inercia"]) if len(ks) > 2 else k_elegido
    km = modelos[k_elegido]
    etiquetas = km.labels_

    centros = pd.DataFrame(km.cluster_centers_, columns=cfg.FEATURES_NUM)
    discr = centros.var(axis=0, ddof=0).sort_values(ascending=False).head(N_DISCRIMINANTES).index.tolist()
    y_arr = None if y is None else np.asarray(y)
    filas_seg = []
    for s in range(k_elegido):
        m = etiquetas == s
        fila = {"segmento": s, "nombre_sugerido": _nombre_segmento(centros.loc[s]), "tamano": int(m.sum()),
                "pct": float(m.mean())}
        if y_arr is not None:
            fila["tasa_abandono"] = float(y_arr[m].mean())
        for c in discr:
            fila[c] = float(X.loc[m, c].median())
        filas_seg.append(fila)
    seg = pd.DataFrame(filas_seg)
    dup = seg["nombre_sugerido"].duplicated(keep=False)
    seg.loc[dup, "nombre_sugerido"] = [f"{nm} ({s})" for nm, s in zip(seg.loc[dup, "nombre_sugerido"],
                                                                      seg.loc[dup, "segmento"])]
    pca = PCA(n_components=2, random_state=semilla)
    coords = pca.fit_transform(Z)
    if tiempos is not None:
        tiempos["segmentacion_s"] = time.perf_counter() - t0
    return {"tabla_k": tabla_k, "k_elegido": k_elegido, "k_codo": k_codo, "etiquetas": etiquetas,
            "tabla_segmentos": seg, "discriminantes": discr, "pca": coords,
            "varianza_pca": [float(v) for v in pca.explained_variance_ratio_],
            "n_muestra_silueta": int(len(idx))}


def _figuras(r: dict, figuras_dir: Path) -> None:
    figuras_dir.mkdir(parents=True, exist_ok=True)
    t = r["tabla_k"]
    for nombre, col, etiqueta, marca in (("codo.png", "inercia", "inercia (suma de cuadrados intra-cluster)", r["k_codo"]),
                                         ("silueta.png", "silueta", "silueta media (muestra)", r["k_elegido"])):
        fig, ax = plt.subplots(figsize=(6.5, 4.2), dpi=130)
        ax.plot(t["k"], t[col], marker="o", color="#1f77b4")
        ax.axvline(marca, color="#d95f02", ls="--", lw=1.2, label=f"k = {marca}")
        ax.set_xlabel("k")
        ax.set_ylabel(etiqueta)
        ax.set_title("Método del codo" if col == "inercia" else "Silueta por k")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(figuras_dir / nombre)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 5), dpi=130)
    rng = np.random.default_rng(cfg.SEMILLA)
    n = len(r["etiquetas"])
    idx = rng.choice(n, size=min(n, 15_000), replace=False)
    sc = ax.scatter(r["pca"][idx, 0], r["pca"][idx, 1], c=r["etiquetas"][idx], cmap="tab10", s=4, alpha=0.5, lw=0)
    ax.legend(*sc.legend_elements(), title="segmento", frameon=False, loc="best")
    v = r["varianza_pca"]
    ax.set_xlabel(f"PC1 ({v[0]:.1%} de la varianza)")
    ax.set_ylabel(f"PC2 ({v[1]:.1%} de la varianza)")
    ax.set_title(f"Segmentos de A en el plano PCA (k = {r['k_elegido']})")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(figuras_dir / "pca_segmentos.png")
    plt.close(fig)


def escribir_informe(r: dict, salida: Path, tasa_global: float | None = None) -> None:
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    _figuras(r, salida / "figuras")
    t = r["tabla_k"]
    (salida / "segmentos_k.md").write_text(
        "# Segmentación: inercia y silueta por k\n\n"
        "KMeans (n_init=10, semilla 2026) sobre las features numéricas de comportamiento de A, imputadas con la "
        "mediana y estandarizadas (mismo pipeline numérico del modelo); sin la etiqueta.\n\n"
        + tabla_markdown(t.to_dict("records"), ["k", "inercia", "silueta"], formato="{:.4f}")
        + f"\nSilueta calculada sobre una muestra de {r['n_muestra_silueta']} filas (estratificada por etiqueta, con semilla).\n"
        f"- k elegido por silueta máxima: **{r['k_elegido']}**.\n"
        f"- Nota del codo (distancia máxima a la recta entre los extremos de la curva de inercia): k = {r['k_codo']}"
        + (" (coincide con la silueta)." if r["k_codo"] == r["k_elegido"] else
           " (difiere de la silueta: la inercia siempre baja con k; el codo es orientativo y la silueta decide).")
        + "\n\nFiguras: `figuras/codo.png`, `figuras/silueta.png`, `figuras/pca_segmentos.png` "
          f"(PCA 2D explica {sum(r['varianza_pca']):.1%} de la varianza: {r['varianza_pca'][0]:.1%} + {r['varianza_pca'][1]:.1%}).\n")
    seg = r["tabla_segmentos"]
    cols = ["segmento", "nombre_sugerido", "tamano", "pct"] + (["tasa_abandono"] if "tasa_abandono" in seg else []) \
        + r["discriminantes"]
    (salida / "segmentos.md").write_text(
        f"# Segmentos de comportamiento (k = {r['k_elegido']})\n\n"
        f"Medianas (unidades originales) de las {N_DISCRIMINANTES} features más discriminantes (mayor varianza entre "
        "centroides estandarizados). La tasa de abandono es descriptiva (etiqueta de A, no se usó para agrupar)"
        + (f"; tasa global de A = {tasa_global:.4f}" if tasa_global is not None else "") + ".\n"
        "`nombre_sugerido` es automático (reglas sobre frecuencia, modos y tendencia) y el informe puede reescribirlo.\n\n"
        + tabla_markdown(seg.to_dict("records"), cols, formato="{:.3f}"))
    bloques = ["# Acciones por segmento (PROPUESTA: texto provisional para que el informe lo redacte)\n"]
    for f in seg.itertuples():
        bloques.append(f"## Segmento {f.segmento}: {f.nombre_sugerido} ({f.tamano} personas)\n\n"
                       "- Acción 1 (propuesta): _por redactar_ - qué hacer, con qué canal y en qué momento.\n"
                       "- Acción 2 (propuesta): _por redactar_ - segunda acción distinta de la anterior.\n"
                       "- Indicador de éxito (propuesta): _por definir_.\n")
    (salida / "acciones.md").write_text("\n".join(bloques))


def main(argv=None) -> dict:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--origen", choices=["bigquery", "csv"], default="bigquery")
    p.add_argument("--ruta-csv", default=None)
    p.add_argument("--salida-dir", default=None, help="por defecto docs/evidence/p2")
    p.add_argument("--artefactos-dir", default=None, help="por defecto ml/artefactos")
    p.add_argument("--k-max", type=int, default=10)
    a = p.parse_args(argv)
    salida = Path(a.salida_dir) if a.salida_dir else cfg.EVIDENCIA
    arte = Path(a.artefactos_dir) if a.artefactos_dir else cfg.ARTEFACTOS
    X, y_s, ids = preparar_xy(cargar_dataset(["A"], a.origen, a.ruta_csv))
    r = segmentar(X, y_s.to_numpy(), ks=range(2, a.k_max + 1))
    escribir_informe(r, salida, float(y_s.mean()))
    arte.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"unidad_id": ids, "segmento": r["etiquetas"]}).to_csv(arte / "segmentos_A.csv", index=False)
    print(f"k elegido (silueta) = {r['k_elegido']}; codo = {r['k_codo']}")
    print(r["tabla_segmentos"][["segmento", "nombre_sugerido", "tamano"]].to_string(index=False))
    return r


if __name__ == "__main__":
    main()
