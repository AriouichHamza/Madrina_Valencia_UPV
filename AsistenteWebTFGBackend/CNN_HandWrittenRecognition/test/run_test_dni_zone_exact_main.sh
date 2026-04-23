#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: bash run_test_dni_zone_exact_main.sh /chemin/vers/examen.pdf /chemin/output"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PDF_PATH="$1"
OUTPUT_DIR="$2"

python "$SCRIPT_DIR/test_dni_zone_exact_main.py" --pdf "$PDF_PATH" --output "$OUTPUT_DIR"
