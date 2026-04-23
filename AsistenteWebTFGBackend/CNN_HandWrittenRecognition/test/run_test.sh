#!/usr/bin/env bash
# Wrapper script to run DNI recognition test using configuration file

set -euo pipefail



SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/test_config.sh"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "❌ Error: Configuration file not found: $CONFIG_FILE"
  echo "Please create test_config.sh first"
  exit 1
fi

# Source the configuration
source "$CONFIG_FILE"

echo "📋 Configuration loaded:"
echo "   PDF: $PDF_PATH"
echo "   Model: $MODEL_PATH"
echo "   Reference: $REF_PATH"
echo "   Output: $OUTPUT_DIR"
echo "   Mode: $MODE"
echo ""

# Run the test
bash "$SCRIPT_DIR/run_test_dni_zone_exact_main.sh" "$PDF_PATH" "$OUTPUT_DIR"
bash "$SCRIPT_DIR/run_test_dni_recognition_exact_main.sh" "$PDF_PATH" "$MODEL_PATH" "$REF_PATH" "$OUTPUT_DIR" "$MODE"
