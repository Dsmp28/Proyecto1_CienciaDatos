#!/usr/bin/env bash
# Escanea el historial completo de git en busca de secretos con gitleaks.
# Instala gitleaks si falta (brew en macOS). Falla si hay hallazgos.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v gitleaks >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "Instalando gitleaks con Homebrew..."
    brew install gitleaks
  else
    echo "gitleaks no está instalado. Ver https://github.com/gitleaks/gitleaks#installing" >&2
    exit 2
  fi
fi
mkdir -p docs/evidence
gitleaks git --redact --report-format json --report-path docs/evidence/gitleaks_report.json .
echo "Sin secretos en el historial. Reporte en docs/evidence/gitleaks_report.json"
