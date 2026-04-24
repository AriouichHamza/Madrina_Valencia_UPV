#!/usr/bin/env bash
# Configuration file for DNI Recognition Test
# Modify the paths below according to your environment

# Path to the PDF exam file
PDF_PATH="/home/ariouich/Bureau/valencia/Madrina/OriginalVersion/P1_nov_para_jefferson/1.pdf"

# Path to the trained model
MODEL_PATH="/home/ariouich/Bureau/valencia/Madrina/AsistenteWebTFGBackend/CNN_HandWrittenRecognition/exammodel4.pt"

# Path to the reference file (ground truth CSV or students JSON)
REF_PATH="/home/ariouich/Bureau/valencia/Madrina/AsistenteWebTFGBackend/CNN_HandWrittenRecognition/test/students.json"

# Output directory for results
OUTPUT_DIR="./debug_test1_new_boxes_detection"

# Mode: "ground_truth" (default) or "--students" (for JSON students file)
MODE="--students"

# ============================================================
# Usage example:
# 1. Edit the paths above
# 2. Run: bash run_test_dni_recognition_exact_main.sh "$PDF_PATH" "$MODEL_PATH" "$REF_PATH" "$OUTPUT_DIR" "$MODE"
# ============================================================
