"""Evaluación ÚNICA del modelo en el corte B (la etiqueta de B se usa una sola vez).

    python -m ml.evaluar_b [--modelo ruta|ACTUAL] [--forzar "justificación"]

Guardas, en orden: (a) árbol git limpio; (b) no existe `ml/artefactos/evaluacion_b.json` ni el marcador
`<!-- EVALUACION_B -->` en `docs/P2/BITACORA.md`. Nunca reentrena: solo carga el modelo guardado. Escribe el JSON
con estado 'en_curso' ANTES de calcular cualquier métrica, así una corrida interrumpida también bloquea repeticiones.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sklearn.metrics import confusion_matrix

from ml import config as cfg
from ml.datos import TOKEN_B_INTERNO, cargar_dataset, preparar_xy
from ml.metricas import evaluar, tabla_markdown
from ml.persistencia import cargar_modelo
from ml.umbral import ganancia, ganancia_por_contactado

MARCADOR = "<!-- EVALUACION_B -->"
BITACORA = cfg.REPO / "docs" / "P2" / "BITACORA.md"


class EvaluacionBAbortada(RuntimeError):
    """Una guarda impidió la evaluación de B."""


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=cfg.REPO, capture_output=True, text=True, check=True,
                          timeout=30).stdout


def arbol_sucio() -> list[str]:
    """Líneas de `git status --porcelain` (vacía = árbol limpio)."""
    return [l for l in _git("status", "--porcelain").splitlines() if l.strip()]


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolver_modelo(modelo: str, modelos_dir: Path) -> Path:
    if modelo == "ACTUAL":
        marca = modelos_dir / "ACTUAL"
        if not marca.exists():
            raise EvaluacionBAbortada(f"no existe {marca}: no hay modelo guardado (corre make ml-entrenar FASE=2)")
        return modelos_dir / marca.read_text().strip()
    ruta = Path(modelo)
    if not ruta.exists():
        raise EvaluacionBAbortada(f"no existe el modelo {ruta}")
    return ruta


def _entrada_bitacora(r: dict, forzar: str | None) -> str:
    m, c = r["metricas"], r["confusion"]
    cm = [[c["tn"], c["fp"]], [c["fn"], c["tp"]]]
    titulo = "Evaluación en el corte B" + (" (REPETIDA, FORZADA)" if forzar else "")
    partes = [MARCADOR, f"## {titulo}\n",
              f"- Fecha: {r['fin_ts']}", f"- Commit: `{r['commit']}`",
              f"- Modelo: `{r['modelo']}` (sha256 `{r['sha256_modelo']}`)",
              f"- Umbral (metadatos del modelo): {r['umbral']:.4f}; unidades en B: {r['n']}; tasa de churn en B: "
              f"{r['tasa_positiva']:.4f}"]
    if forzar:
        partes.append(f"- **Justificación de la repetición:** {forzar}")
    partes += ["", f"AP {m['ap']:.4f} | ROC-AUC {m['roc_auc']:.4f} | Brier {m['brier']:.4f} | "
               f"precisión {r['precision']:.4f} | recall {r['recall']:.4f}", "",
               "Matriz de confusión (filas = real 0/1, columnas = predicho 0/1):", "",
               "| | pred 0 | pred 1 |", "|---|---|---|",
               f"| real 0 | {cm[0][0]} | {cm[0][1]} |", f"| real 1 | {cm[1][0]} | {cm[1][1]} |", "",
               f"Ganancia en Q (15·TP − 5·contactados): {r['ganancia_q']:.2f} en total; "
               f"{r['ganancia_q_por_1000']:.2f} por cada 1 000 personas.", ""]
    return "\n".join(partes) + "\n"


def evaluar_b(modelo: str = "ACTUAL", forzar: str | None = None, permitir_sucio: bool = False,
              origen: str = "bigquery", ruta_csv=None, salida_dir=None, artefactos_dir=None,
              bitacora=None, modelos_dir=None) -> dict:
    salida_dir = Path(salida_dir) if salida_dir else cfg.EVIDENCIA
    arte = Path(artefactos_dir) if artefactos_dir else cfg.ARTEFACTOS
    bitacora = Path(bitacora) if bitacora else BITACORA
    modelos_dir = Path(modelos_dir) if modelos_dir else cfg.MODELOS
    json_ruta = arte / "evaluacion_b.json"

    # (a) árbol limpio
    if not permitir_sucio:
        sucio = arbol_sucio()
        if sucio:
            raise EvaluacionBAbortada("el árbol git no está limpio (commitea antes de evaluar B):\n  "
                                      + "\n  ".join(sucio[:10]))
    # (b) una sola vez
    ya_json = json_ruta.exists()
    ya_marca = bitacora.exists() and MARCADOR in bitacora.read_text()
    if (ya_json or ya_marca) and not (forzar and forzar.strip()):
        donde = " y ".join(x for x, c in ((str(json_ruta), ya_json), (f"marcador en {bitacora}", ya_marca)) if c)
        raise EvaluacionBAbortada(f"B ya fue evaluado ({donde}). Repetirlo exige --forzar \"justificación\".")
    if forzar is not None and not forzar.strip():
        raise EvaluacionBAbortada("--forzar exige una justificación no vacía")

    ruta_modelo = _resolver_modelo(modelo, modelos_dir)
    pipeline, meta = cargar_modelo(ruta_modelo)
    umbral = meta.get("umbral")
    if umbral is None:
        raise EvaluacionBAbortada("el modelo no trae umbral en sus metadatos; entrena con la fase 2")
    if list(meta["features"]) != cfg.FEATURES:
        raise EvaluacionBAbortada("las features del modelo no coinciden con config.FEATURES")
    sha = _sha256(ruta_modelo)
    commit = _git("rev-parse", "HEAD").strip() if not permitir_sucio else _commit_seguro()

    if ya_json:  # forzado: conserva la evaluación previa en lugar de pisarla
        previa = arte / f"evaluacion_b_previa_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.json"
        json_ruta.rename(previa)

    # 1) escribir primero, 2) calcular
    arte.mkdir(parents=True, exist_ok=True)
    estado = {"inicio_ts": _ahora(), "commit": commit, "modelo": ruta_modelo.name, "sha256_modelo": sha,
              "estado": "en_curso"}
    json_ruta.write_text(json.dumps(estado, indent=2, ensure_ascii=False) + "\n")

    df = cargar_dataset(["B"], origen, ruta_csv, _token_b=TOKEN_B_INTERNO)
    X, y_s, _ = preparar_xy(df)
    y = y_s.to_numpy()
    p = pipeline.predict_proba(X)[:, 1]
    m = evaluar(y, p)
    pred = (p >= umbral).astype(int)
    tn, fp, fn, tp = (int(v) for v in confusion_matrix(y, pred, labels=[0, 1]).ravel())
    g = ganancia(y, p, umbral)
    resultado = {
        **estado, "estado": "completada", "fin_ts": _ahora(), "n": int(len(y)), "tasa_positiva": float(y.mean()),
        "umbral": float(umbral), "metricas": m, "confusion": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "precision": tp / (tp + fp) if (tp + fp) else 0.0, "recall": tp / (tp + fn) if (tp + fn) else 0.0,
        "contactados": tp + fp, "ganancia_q": g, "ganancia_q_por_1000": g / len(y) * 1000,
        "ganancia_por_contactado_tp": ganancia_por_contactado(),
        "version_modelo": meta.get("version"), "forzado": forzar or None,
    }
    json_ruta.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n")

    bitacora.parent.mkdir(parents=True, exist_ok=True)
    previo = bitacora.read_text() if bitacora.exists() else "# Bitácora del Proyecto 2\n\n"
    bitacora.write_text(previo.rstrip("\n") + "\n\n" + _entrada_bitacora(resultado, forzar))

    salida_dir.mkdir(parents=True, exist_ok=True)
    c = resultado["confusion"]
    (salida_dir / "test_b.md").write_text(
        "# Evaluación única en el corte B\n\n"
        f"Fecha {resultado['fin_ts']}; commit `{commit}`; modelo `{ruta_modelo.name}` (sha256 `{sha}`); "
        f"umbral {umbral:.4f} (fijado con A, antes de ver B).\n\n"
        + tabla_markdown([{"métrica": k, "valor": v} for k, v in
                          [("AP", m["ap"]), ("ROC-AUC", m["roc_auc"]), ("Brier", m["brier"]),
                           ("precisión", resultado["precision"]), ("recall", resultado["recall"])]],
                         ["métrica", "valor"])
        + f"\nTasa de churn en B: {resultado['tasa_positiva']:.4f} ({len(y)} unidades; AP del azar = esa tasa).\n\n"
        "Matriz de confusión (filas = real, columnas = predicho):\n\n"
        "| | pred 0 | pred 1 |\n|---|---|---|\n"
        f"| real 0 | {c['tn']} | {c['fp']} |\n| real 1 | {c['fn']} | {c['tp']} |\n\n"
        f"Ganancia en Q = 15·TP − 5·(TP+FP) = 15·{tp} − 5·{tp + fp} = {g:.2f}; "
        f"por cada 1 000 personas: {resultado['ganancia_q_por_1000']:.2f}.\n"
        + (f"\nEvaluación repetida y forzada. Justificación: {forzar}\n" if forzar else ""))
    return resultado


def _commit_seguro() -> str | None:
    try:
        return _git("rev-parse", "HEAD").strip()
    except Exception:
        return None


def main(argv=None) -> dict:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelo", default="ACTUAL", help="ruta al .joblib o ACTUAL")
    p.add_argument("--forzar", default=None, metavar="JUSTIFICACION", help="repite la evaluación dejando constancia")
    p.add_argument("--permitir-sucio", action="store_true", help="solo para pruebas: omite la guarda del árbol git")
    p.add_argument("--origen", choices=["bigquery", "csv"], default="bigquery")
    p.add_argument("--ruta-csv", default=None)
    p.add_argument("--salida-dir", default=None, help="por defecto docs/evidence/p2")
    p.add_argument("--artefactos-dir", default=None, help="por defecto ml/artefactos")
    p.add_argument("--bitacora", default=None, help="por defecto docs/P2/BITACORA.md")
    p.add_argument("--modelos-dir", default=None, help="por defecto ml/modelos")
    a = p.parse_args(argv)
    try:
        r = evaluar_b(a.modelo, a.forzar, a.permitir_sucio, a.origen, a.ruta_csv, a.salida_dir, a.artefactos_dir,
                      a.bitacora, a.modelos_dir)
    except EvaluacionBAbortada as e:
        print(f"ABORTADO: {e}", file=sys.stderr)
        raise SystemExit(2)
    m = r["metricas"]
    print(f"B: AP={m['ap']:.4f} AUC={m['roc_auc']:.4f} Brier={m['brier']:.4f} "
          f"ganancia={r['ganancia_q']:.2f} Q ({r['ganancia_q_por_1000']:.2f} por 1000)")
    return r


if __name__ == "__main__":
    main()
