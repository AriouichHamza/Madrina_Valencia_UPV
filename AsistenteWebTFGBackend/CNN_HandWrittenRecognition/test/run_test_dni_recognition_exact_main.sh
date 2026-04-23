#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 4 ]; then
  echo "Usage: bash run_test_dni_recognition_exact_main.sh /chemin/vers/examen.pdf /chemin/vers/exammodel4.pt /chemin/vers/ground_truth.csv /chemin/output"
  echo "   ou: bash run_test_dni_recognition_exact_main.sh /chemin/vers/examen.pdf /chemin/vers/exammodel4.pt /chemin/vers/students.json /chemin/output --students"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PDF_PATH="$1"
MODEL_PATH="$2"
REF_PATH="$3"
OUTPUT_DIR="$4"
MODE="${5:-ground_truth}"

if [ "$MODE" = "--students" ]; then
  python "$SCRIPT_DIR/test_dni_recognition_exact_main.py" --pdf "$PDF_PATH" --model "$MODEL_PATH" --students "$REF_PATH" --output "$OUTPUT_DIR"
else
  python "$SCRIPT_DIR/test_dni_recognition_exact_main.py" --pdf "$PDF_PATH" --model "$MODEL_PATH" --ground-truth "$REF_PATH" --output "$OUTPUT_DIR"
fi
