#!/usr/bin/env python3
"""Exporta el diccionario de datos de la capa Gold desde las descripciones YAML de dbt.

Lee dbt/target/manifest.json (descripciones de modelos y columnas de dbt/models/gold/schema.yml) y, si existe,
dbt/target/catalog.json (tipos reales de BigQuery tras `dbt docs generate`) y escribe
docs/governance/diccionario_gold.md con una tabla por modelo: columna, tipo, descripción.
La descripción de cada columna en el YAML debe decir significado, fuente y transformación; este script solo la
exporta (única fuente de verdad: schema.yml, que también se persiste en BigQuery con persist_docs).

Uso:
    cd dbt && DBT_PROFILES_DIR=. ../.venv/bin/dbt docs generate && cd ..
    python3 scripts/exportar_diccionario.py [--manifest dbt/target/manifest.json] [--salida docs/governance/diccionario_gold.md]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ORDEN_GRUPOS = (("dim_", "Dimensiones"), ("fct_", "Hechos"), ("agg_", "Agregados para Tableau"))


def _capa(node: dict) -> str:
    partes = node.get("path", "").replace("\\", "/").split("/")
    return partes[0] if partes else ""


def _md(texto: str | None) -> str:
    """Una celda de tabla Markdown: sin saltos de línea ni barras verticales."""
    return " ".join((texto or "").split()).replace("|", "\\|")


def _pruebas_por_columna(manifest: dict, model_uid: str) -> dict[str, list[str]]:
    """Nombres cortos de las pruebas genéricas por columna del modelo (unique, not_null, relationships…)."""
    out: dict[str, list[str]] = {}
    for uid, node in manifest["nodes"].items():
        # solo las pruebas declaradas en este modelo (attached_node), no las relationships de otros hechos hacia él
        if node.get("resource_type") != "test" or node.get("attached_node") != model_uid:
            continue
        meta = node.get("test_metadata")
        if not meta:
            continue
        col = node.get("column_name")
        if not col:
            continue
        nombre = meta["name"]
        kw = meta.get("kwargs", {})
        if nombre == "relationships":
            to = kw.get("to", "")
            nombre = f"relationships→{to.replace('ref(', '').replace(')', '').strip(chr(39))}"
        out.setdefault(col, []).append(nombre)
    return out


def generar(manifest_path: Path, catalog_path: Path, salida: Path) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {"nodes": {}}

    modelos = {
        uid: node
        for uid, node in manifest["nodes"].items()
        if node.get("resource_type") == "model" and _capa(node) == "gold"
    }
    if not modelos:
        raise SystemExit("No hay modelos de gold en el manifest; ejecuta `dbt parse` o `dbt docs generate`.")

    lineas: list[str] = [
        "# Diccionario de datos · capa Gold",
        "",
        "Generado por `scripts/exportar_diccionario.py` desde `dbt/target/manifest.json` (descripciones de",
        "`dbt/models/gold/schema.yml`) y `dbt/target/catalog.json` (tipos reales de BigQuery). No editar a mano:",
        "la fuente de verdad es el YAML, que también se persiste en BigQuery (`persist_docs`).",
        "",
        "Convenciones: cada descripción indica significado, fuente y transformación. Las medidas están clasificadas",
        "como **ADITIVA**, **SEMI ADITIVA** o **NO ADITIVA** (matriz del bus §4). Llaves: `*_sk` sustitutas,",
        "`*_id` naturales conformadas. Ninguna tabla contiene la llave nativa del usuario (seguridad.md §2).",
        "",
        "## Índice",
        "",
    ]
    ordenados: list[tuple[str, dict]] = []
    for prefijo, _ in ORDEN_GRUPOS:
        ordenados += sorted(((u, n) for u, n in modelos.items() if n["name"].startswith(prefijo)), key=lambda x: x[1]["name"])
    ordenados += sorted(((u, n) for u, n in modelos.items() if not n["name"].startswith(tuple(p for p, _ in ORDEN_GRUPOS))), key=lambda x: x[1]["name"])

    for _, node in ordenados:
        lineas.append(f"- [`{node['name']}`](#{node['name']})")
    lineas.append("")

    grupo_actual = None
    n_columnas = 0
    for uid, node in ordenados:
        grupo = next((g for p, g in ORDEN_GRUPOS if node["name"].startswith(p)), "Otros")
        if grupo != grupo_actual:
            lineas += [f"## {grupo}", ""]
            grupo_actual = grupo
        cfg = node.get("config", {})
        particion = cfg.get("partition_by")
        cluster = cfg.get("cluster_by")
        fisico = []
        if particion:
            fisico.append(f"partición por `{particion.get('field')}`")
        if cluster:
            fisico.append("cluster por " + ", ".join(f"`{c}`" for c in (cluster if isinstance(cluster, list) else [cluster])))
        padres = sorted(
            manifest["nodes"].get(p, manifest.get("sources", {}).get(p, {})).get("name", p.split(".")[-1])
            for p in manifest["parent_map"].get(uid, [])
        )
        cat_cols = catalog["nodes"].get(uid, {}).get("columns", {})
        tipos = {k.lower(): v.get("type", "") for k, v in cat_cols.items()}
        pruebas = _pruebas_por_columna(manifest, uid)

        lineas += [
            f"### {node['name']}",
            "",
            _md(node.get("description")) or "_Sin descripción_",
            "",
            f"- **Tabla:** `{node['schema']}.{node['name']}` · materialización `{cfg.get('materialized')}`"
            + (" · " + " · ".join(fisico) if fisico else ""),
            f"- **Fuentes (`ref`):** " + ", ".join(f"`{p}`" for p in padres),
            "",
            "| Columna | Tipo | Descripción (significado · fuente · transformación) | Pruebas |",
            "|---|---|---|---|",
        ]
        columnas = node.get("columns", {})
        for nombre_col, col in columnas.items():
            tipo = tipos.get(nombre_col.lower(), "—")
            lineas.append(f"| `{nombre_col}` | {tipo} | {_md(col.get('description'))} | {', '.join(pruebas.get(nombre_col, []))} |")
            n_columnas += 1
        # columnas presentes en BigQuery pero sin descripción en YAML: se listan para que no queden invisibles
        faltantes = [c for c in cat_cols if c.lower() not in {k.lower() for k in columnas}]
        for c in faltantes:
            lineas.append(f"| `{c}` | {tipos.get(c.lower(), '—')} | _Sin descripción en schema.yml_ | |")
            n_columnas += 1
        lineas.append("")

    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return n_columnas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=REPO / "dbt" / "target" / "manifest.json")
    ap.add_argument("--catalog", type=Path, default=REPO / "dbt" / "target" / "catalog.json")
    ap.add_argument("--salida", type=Path, default=REPO / "docs" / "governance" / "diccionario_gold.md")
    args = ap.parse_args()
    n = generar(args.manifest, args.catalog, args.salida)
    print(f"Diccionario escrito en {args.salida} ({n} columnas)")


if __name__ == "__main__":
    main()
