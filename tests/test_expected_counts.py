"""Las filas de ingest/expected_hashes.json coinciden con el LEEME.txt de la entrega v2."""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PATRON = re.compile(r"^\s+(\S+\.(?:csv|jsonl))\s+([\d,]+)", re.M)


def test_filas_esperadas_coinciden_con_leeme():
    texto = (REPO / "docs" / "P2_datos_red" / "LEEME.txt").read_text(encoding="utf-8")
    leeme = {n: int(c.replace(",", "")) for n, c in PATRON.findall(texto)}
    huellas = json.loads((REPO / "ingest" / "expected_hashes.json").read_text())["archivos"]
    assert len(leeme) == 9
    assert {n: h["filas_datos"] for n, h in huellas.items()} == leeme
