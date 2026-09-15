"""Restricción dura 1: ningún modelo de Gold lee de Bronze ni de Staging.

Recorre manifest.json y falla si un modelo de gold depende de algo que no sea
un modelo de silver, otro modelo de gold o un seed (catálogos conformados).
También verifica que features solo dependa de silver/seeds (restricción 5).
"""

ALLOWED_PARENTS = {
    "gold": {"silver", "gold"},
    "features": {"silver", "features"},
}


def _layer(node):
    """Capa de un nodo según la carpeta de models/<capa>/..."""
    parts = node.get("path", "").replace("\\", "/").split("/")
    return parts[0] if parts else None


def _violations(manifest, layer):
    nodes = manifest["nodes"]
    bad = []
    for uid, node in nodes.items():
        if node.get("resource_type") != "model" or _layer(node) != layer:
            continue
        for parent in manifest["parent_map"].get(uid, []):
            if parent.startswith("source."):
                bad.append((uid, parent, "source (bronze)"))
                continue
            if parent.startswith("seed."):
                continue
            pnode = nodes.get(parent)
            if pnode is None:
                bad.append((uid, parent, "desconocido"))
                continue
            player = _layer(pnode) if pnode.get("resource_type") == "model" else pnode.get("resource_type")
            if player not in ALLOWED_PARENTS[layer]:
                bad.append((uid, parent, player))
    return bad


def test_gold_solo_referencia_silver_o_gold(manifest):
    bad = _violations(manifest, "gold")
    assert not bad, "Modelos de Gold con dependencias prohibidas:\n" + "\n".join(
        f"  {m} -> {p} ({capa})" for m, p, capa in bad
    )


def test_features_solo_referencia_silver(manifest):
    bad = _violations(manifest, "features")
    assert not bad, "Modelos de features con dependencias prohibidas:\n" + "\n".join(
        f"  {m} -> {p} ({capa})" for m, p, capa in bad
    )


def test_gold_existe(manifest):
    gold = [u for u, n in manifest["nodes"].items() if n.get("resource_type") == "model" and _layer(n) == "gold"]
    assert gold, "No hay modelos en models/gold; la prueba de linaje no tiene nada que validar"
