from __future__ import annotations

import sys
from datetime import datetime
import os
import json

CANONICAL_LABELS = (
    [str(i) for i in range(10)]
    + [chr(ord("a") + i) for i in range(26)]
    + [chr(ord("A") + i) for i in range(26)]
)
def safe_class_folder(idx: int, label: str) -> str:
    return f"{idx:03d}_{label}"

FALLBACK_CLASSES = [safe_class_folder(i, lab) for i, lab in enumerate(CANONICAL_LABELS)]

LABEL_TO_ID = {label: idx for idx, label in enumerate(CANONICAL_LABELS)}



num_classes = 33




# Flush each line immediately so the caller receives progress updates in real time.
sys.stdout.reconfigure(line_buffering=True)
initial_time = datetime.now()
current_folder = os.path.abspath(os.path.dirname(__file__))
root_folder = os.path.dirname(current_folder)

# Runtime arguments received from the parent application.
index = sys.argv[1]
examen_nombre = sys.argv[2]
alumnos = json.loads(sys.argv[3])


# The composite index encodes the user, subject, and exam identifiers.
aux = index.split('-')
usuario = aux[0]
asignatura_ID = aux[1]
examen_ID = aux[2]

# Build the main input/output paths used during the OCR pipeline.
# The backend stores uploaded PDFs in its own user_data folder; when this module
# is launched from the backend it passes that location through the environment.
user_data_root = os.environ.get("AI_MODULE_USER_DATA_ROOT", os.path.join(root_folder, "user_data"))
examImgsPath = os.path.join(user_data_root, index)
inputPDF = os.path.join(examImgsPath, examen_nombre + ".pdf")

output_folder = current_folder + "/.img-dumps/"+ index + "/" # we use the current folder to stock the images
trained_model_name = 'best_model.pt'
trained_model_path = os.path.join(root_folder, "core", "checkpoints", trained_model_name)
exam_model_name = 'exammodel4_new.pt'
exam_model_path = os.path.join(root_folder, "core", "checkpoints", exam_model_name)
device = "auto"
PAGE_NUM_WIDTH = 1
DNI_CHAIN_CACHE = {}
