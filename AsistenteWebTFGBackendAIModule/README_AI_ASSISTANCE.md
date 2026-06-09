# AI Assistance Module

## Overview

`AsistenteWebTFGBackendAIModule` is the OCR component used by the backend to process a PDF containing several student exam copies.

Its runtime entry point is `main.py`. The module:

1. converts selected areas of the PDF pages to images;
2. detects the first page of each exam copy;
3. reads the handwritten DNI/NIF identifier;
4. matches the OCR result against the known student roster;
5. reads the handwritten grade;
6. sends progress updates and student results to the parent backend process.

The module is designed to run as a child process of the Node.js backend. It can also be launched manually for debugging.

## Directory Structure

```text
AsistenteWebTFGBackendAIModule/
├── main.py                              # Runtime OCR pipeline entry point
├── example.py                           # Single-image character prediction helper
├── README_AI_ASSISTANCE.md              # This documentation
│
├── Modules/
│   ├── emitter.py                       # Stdout protocol used by the backend
│   ├── student.py                       # Student result object and JSON serialization
│   ├── knowledgebase.py                 # Reserved placeholder
│   ├── train/
│   │   └── train.py                     # Handwriting CNN training script
│   └── test/
│       └── test.py                      # Evaluation and metrics generation script
│
├── core/
│   ├── service.py                       # Reserved placeholder
│   └── checkpoints/
│       ├── best_model.pt                # DNI/NIF character recognition model
│       ├── exammodel4.pt                # Grade digit recognition model
│       └── training_history.csv         # Training history for the DNI/NIF model
│
├── data/
│   ├── zipfiles/                        # Raw dataset archives
│   ├── unify_handwriting_datasets.py    # Legacy single-pair dataset builder
│   ├── unify_handwriting_datasets_multi.py
│   │                                     # Multi-archive dataset builder
│   ├── create_selected_labels_dataset.py # Keeps the required DNI/NIF labels
│   ├── generate_labels_csv_from_imagefolder.py
│   │                                     # Generates labels.csv metadata
│   └── visualize_dataset_stats.py       # Generates dataset charts and reports
│
├── services/
│   └── logging_service.py               # Reserved placeholder
│
└── utils/
    ├── constants.py                     # Runtime arguments, paths and label constants
    ├── utils.py                         # Model loading, preprocessing and grade OCR
    ├── Model/
    │   ├── smallCNN.py                  # 64x64 character classifier for DNI/NIF OCR
    │   └── CNN.py                       # 28x28 digit classifier for grade OCR
    ├── traitement/
    │   ├── pdf_traitement.py            # PDF rendering and temporary path helpers
    │   ├── imageProcessing.py           # DNI box detection and image processing
    │   ├── dni_processing.py            # DNI/NIF normalization and check-letter logic
    │   └── training_random_traitement.py # Training augmentations
    ├── pipelines/
    │   ├── remplacement_bascar_inicio_copias.py
    │   │                                 # Detects the first page of each exam copy
    │   └── renplacement_compute_coords_from_main_block.py
    │                                     # Computes DNI crop coordinates and fallbacks
    └── metrics/
        └── classification_metric.py      # Evaluation metrics and plots
```

Generated files such as `__pycache__/` and `utils/.img-dumps/` are not source files. The `.img-dumps/<index>/` folder is a temporary workspace created while a PDF is processed and removed after a successful run.

## Requirements

No Python dependency lock file is currently provided in this directory. The runtime requires:

- Python 3;
- Poppler's `pdftoppm` executable;
- `torch`;
- `numpy`;
- `Pillow`;
- `opencv-python`;
- `PyPDF2`;
- `python-Levenshtein`.

Training, evaluation and dataset reports additionally use:

- `torchvision`;
- `matplotlib`;
- `pandas`.

Example installation on Debian or Ubuntu:

```bash
sudo apt install poppler-utils
python -m pip install torch torchvision numpy Pillow opencv-python PyPDF2 python-Levenshtein matplotlib pandas
```

CUDA is optional. The default device is `auto`: CUDA is used when available and working, otherwise the code falls back to the CPU.

## Runtime Input Convention

`main.py` expects three positional arguments:

```text
python main.py <index> <pdf_name_without_extension> <students_json>
```

The `index` must contain exactly three hyphen-separated identifiers:

```text
<user_id>-<subject_id>-<exam_id>
```

The student roster must be a JSON array. Every student object must contain:

```json
{
  "dni": "12345678Z",
  "nombre": "Ada",
  "apellidos": "Lovelace"
}
```

The PDF must exist at:

```text
<AI_MODULE_USER_DATA_ROOT>/<index>/<pdf_name_without_extension>.pdf
```

When `AI_MODULE_USER_DATA_ROOT` is not set, the module defaults to:

```text
AsistenteWebTFGBackendAIModule/user_data
```

## Backend Usage

The normal execution path is the Socket.IO handler in `AsistenteWebTFGBackend/routes/socket.js`.

When the backend receives the `examen-predict` event, it:

1. builds the `<user_id>-<subject_id>-<exam_id>` index;
2. fetches the students registered for the subject;
3. spawns `main.py` with the index, PDF name and roster JSON;
4. sets `AI_MODULE_USER_DATA_ROOT` to the backend `user_data` directory;
5. reads the child process output;
6. inserts the emitted grades into the database when processing is complete.

The Python interpreter path is currently configured directly in `routes/socket.js`. Update that path when the project is installed in another location or virtual environment.

## Manual Runtime Usage

Run commands from the AI module directory because imports are relative to this folder:

```bash
cd AsistenteWebTFGBackendAIModule

AI_MODULE_USER_DATA_ROOT=/absolute/path/to/AsistenteWebTFGBackend/user_data \
python main.py \
  "user1-subject2-exam3" \
  "mathematics_final" \
  '[{"dni":"12345678Z","nombre":"Ada","apellidos":"Lovelace"}]'
```

For this example, the input file must be:

```text
/absolute/path/to/AsistenteWebTFGBackend/user_data/user1-subject2-exam3/mathematics_final.pdf
```

Both model files must also exist:

```text
core/checkpoints/best_model.pt
core/checkpoints/exammodel4.pt
```

## Output Protocol

`Modules/emitter.py` writes line-based messages to `stdout`. The backend recognizes:

```text
progress <percentage> <state>
new-calificado <student_json>
done <elapsed_time>
```

Example:

```text
progress 25 Convirtiendo PDF a imagenes
progress 67 Buscando DNIs en páginas
new-calificado {"asignatura": "subject2", "examen": "exam3", "dni": "12345678Z", "nombre": "Ada", "apellidos": "Lovelace", "ini": "1", "fin": "4", "nota": 8.5}
done 0:00:12.345678
```

Some diagnostic messages are also printed. Detailed OCR matching diagnostics and exceptions are written to `stderr`.

## Runtime Processing Flow

### 1. Load configuration and models

Importing `utils/constants.py` reads the three command-line arguments, extracts the user, subject and exam identifiers, resolves the input PDF path, and defines the temporary output folder.

`main.py` then loads:

- `SmallCNN` from `core/checkpoints/best_model.pt` for DNI/NIF characters;
- `CNN` from `core/checkpoints/exammodel4.pt` for grade digits.

### 2. Convert PDF regions to images

`utils/traitement/pdf_traitement.py` calls `pdftoppm` in parallel. It renders:

- the page-header area where DNI boxes are expected;
- the area where the handwritten grade is expected.

The generated images are stored temporarily in:

```text
utils/.img-dumps/<index>/
```

### 3. Find the first page of every exam copy

The PDF may contain several copies, each spanning one or more pages.

`buscar_inicio_copias()` analyzes pages in parallel. It searches for a horizontal sequence of DNI boxes using several OpenCV variants: adaptive thresholds, dilation, Otsu thresholding and Canny edges.

The detected first pages are sorted. Each student's page range is inferred from one first page up to the page before the next first page. The last range ends on the final PDF page.

### 4. Read and match the DNI/NIF

For each detected copy:

1. the code obtains nine character box coordinates;
2. fallback coordinates are generated if a box or anchor cannot be detected reliably;
3. every crop is converted to grayscale, normalized, centered, padded and resized to `64x64`;
4. `SmallCNN` predicts the character sequence;
5. Spanish DNI/NIF normalization reconstructs the expected check letter when possible;
6. Levenshtein similarity selects the closest student from the roster.

The current matching acceptance threshold is `0.4`.

If no roster entry passes the threshold, the result is emitted with empty DNI and name fields while preserving the detected page range and grade.

### 5. Read the grade

The grade area is processed separately:

1. square contours are detected from the grade image;
2. empty boxes are ignored;
3. remaining crops are resized to `28x28`;
4. `CNN` predicts the handwritten digits;
5. the sequence is converted into a decimal grade.

Grades outside the expected `0` to `10` range are replaced with `0.0`.

### 6. Emit results and clean temporary files

Each recognized copy is emitted as a `new-calificado` JSON record. At the end, `main.py` emits `done` and deletes the temporary `.img-dumps/<index>/` folder.

## Dataset Preparation

The `data/` scripts are development utilities. They are not called by the runtime pipeline.

Run the following commands from `AsistenteWebTFGBackendAIModule`.

### Build a unified dataset

The multi-archive script is the recommended builder:

```bash
python data/unify_handwriting_datasets_multi.py \
  --archive_zips data/zipfiles/archive.zip data/zipfiles/archive1.zip \
  --choice_zips data/zipfiles/CHoiCe-Dataset-main.zip \
  --output_dir unified_dataset
```

It normalizes images, creates deterministic filenames, and generates train, validation and test splits.

### Keep the required DNI/NIF labels

```bash
python data/create_selected_labels_dataset.py \
  --input_dataset unified_dataset/images \
  --output_dataset selected_dataset/images \
  --clean_output
```

By default, this keeps digits and the letters needed for Spanish DNI/NIF identifiers.

### Generate CSV metadata and reports

```bash
python data/generate_labels_csv_from_imagefolder.py \
  --dataset_dir selected_dataset

python data/visualize_dataset_stats.py \
  --dataset_dir selected_dataset \
  --output_dir dataset_figures
```

## Training and Evaluation Utilities

The repository contains the intended training and evaluation commands:

```bash
python Modules/train/train.py \
  --dataset_root selected_dataset/images \
  --checkpoint_dir checkpoints_selected \
  --epochs 100 \
  --device auto \
  --augment_real_like \
  --weighted_sampler

python Modules/test/test.py \
  --checkpoint checkpoints_selected/best_model.pt \
  --dataset_root selected_dataset/images \
  --split test \
  --output_dir evaluation_results \
  --device auto
```

`example.py` is intended to test individual character images:

```bash
python example.py \
  --checkpoint core/checkpoints/best_model.pt \
  --images test_images/*.png \
  --device auto
```

### Current limitation

`utils/constants.py` parses the runtime positional arguments as soon as it is imported. Because `utils/utils.py` imports `utils/constants.py`, the current versions of `Modules/train/train.py`, `Modules/test/test.py`, and `example.py` are still coupled to the `main.py` runtime argument format.

The commands above describe their intended interfaces, but these utilities must be decoupled from runtime argument parsing before they can be executed normally. The standalone scripts under `data/` do not have this limitation.

## File-by-File Reference

This section provides a short description of every maintained file currently present in the module. Generated files under `__pycache__/`, the internal `.git/` directory, and temporary images under `utils/.img-dumps/` are excluded.

### Root files

| File | Contents and purpose |
| --- | --- |
| `main.py` | Main production entry point. It loads both CNN models, preprocesses the PDF, finds exam-copy boundaries, predicts DNI/NIF identifiers and grades, matches students, emits results, and removes temporary files. |
| `example.py` | Command-line helper intended to classify one or more handwritten character images with `SmallCNN`. It can print top predictions, export a CSV file, and save preprocessed images. It is currently affected by the runtime-argument coupling described above. |
| `README_AI_ASSISTANCE.md` | Technical documentation for the AI module: architecture, runtime usage, processing flow, data utilities, and this file reference. |

### `Modules/`

| File | Contents and purpose |
| --- | --- |
| `Modules/emitter.py` | Defines `Emitter`, the small output adapter used to send `progress`, `new-calificado`, and `done` lines to the Node.js parent process through `stdout`. |
| `Modules/student.py` | Defines `Alumno`, the result object emitted for each exam copy. Its `to_json()` method serializes subject, exam, identity, page range, and grade fields. |
| `Modules/knowledgebase.py` | Empty placeholder. It does not currently participate in the runtime pipeline. |
| `Modules/train/train.py` | Intended training script for the `SmallCNN` character classifier. It loads ImageFolder train/validation/test splits, supports data augmentation and weighted sampling, applies early stopping, and writes a best checkpoint plus a CSV history. |
| `Modules/test/test.py` | Intended evaluation script for `SmallCNN`. It computes loss, accuracy, precision, recall, F1 scores, per-class metrics, predictions, confusion matrices, class-accuracy charts, and misclassified examples. |

### `core/`

| File | Contents and purpose |
| --- | --- |
| `core/service.py` | Empty placeholder. No runtime service is implemented in this file yet. |
| `core/checkpoints/best_model.pt` | Serialized `SmallCNN` checkpoint used in production to recognize handwritten DNI/NIF characters. |
| `core/checkpoints/exammodel4.pt` | Serialized `CNN` checkpoint used in production to recognize handwritten grade digits. |
| `core/checkpoints/training_history.csv` | Training log for the character classifier. It records epoch number, train and validation loss, train and validation accuracy, best validation accuracy, learning rate, and whether the epoch produced the best model. |

### `data/`

| File | Contents and purpose |
| --- | --- |
| `data/unify_handwriting_datasets.py` | Legacy dataset builder for one archive-style ZIP and one CHoiCe ZIP. It normalizes handwritten characters, splits samples into train/validation/test sets, and writes metadata CSV files. |
| `data/unify_handwriting_datasets_multi.py` | Extended dataset builder that accepts multiple archive-style and CHoiCe ZIP files. This is the recommended version when rebuilding the unified dataset. |
| `data/create_selected_labels_dataset.py` | Creates a smaller ImageFolder dataset containing only the labels required for DNI/NIF recognition. It can copy images or create symbolic links. |
| `data/generate_labels_csv_from_imagefolder.py` | Scans a selected ImageFolder dataset and creates `labels.csv` metadata with file paths, split names, labels, label IDs, class folders, and source names. |
| `data/visualize_dataset_stats.py` | Generates dataset statistics, figures, example grids, optional training-history plots, optional confusion matrices, and a Markdown report. |

### `data/zipfiles/`

These files are raw source datasets retained for experiments and dataset rebuilding. They are not loaded by `main.py`.

| File | Contents and purpose |
| --- | --- |
| `data/zipfiles/CHoiCe-Dataset-main.zip` | CHoiCe handwritten-character dataset archive. The dataset builders can read its `V0.3/data-bin/` or `V0.3/data/` variants. |
| `data/zipfiles/archive.zip` | Archive-style handwritten-character dataset containing images such as `Img/img001-001.png`. It is used by the documented unified-dataset build command. |
| `data/zipfiles/archive1.zip` | Additional raw archive containing augmented handwritten images organized by label. It is retained as an experimental data source. |
| `data/zipfiles/alfabe_proje.v2i.retinanet.zip` | RetinaNet-format alphabet dataset archive with training images. It is retained for experiments and is not consumed by the current runtime pipeline. |
| `data/zipfiles/letter-recognition.v1i.retinanet.zip` | RetinaNet-format letter-recognition dataset archive with train/test data and annotation CSV files. It is retained for experiments and is not consumed by the current runtime pipeline. |

### `services/`

| File | Contents and purpose |
| --- | --- |
| `services/logging_service.py` | Empty placeholder reserved for a future logging abstraction. Runtime logging currently occurs directly in `main.py` and through diagnostic prints. |

### `utils/`

| File | Contents and purpose |
| --- | --- |
| `utils/constants.py` | Defines label constants and reads the runtime command-line arguments. It extracts user, subject, and exam IDs, resolves PDF and checkpoint paths, selects the default device, and defines the temporary image folder. |
| `utils/utils.py` | Shared utility module. It selects CPU or CUDA, loads both model types, preprocesses character images, runs standalone predictions, writes CSV results, evaluates models, creates weighted samplers, and detects grades. |

### `utils/Model/`

| File | Contents and purpose |
| --- | --- |
| `utils/Model/smallCNN.py` | Defines `SmallCNN`, the `64x64` grayscale classifier used for DNI/NIF characters. The network contains three convolution blocks and a fully connected classifier. |
| `utils/Model/CNN.py` | Defines `CNN`, the `28x28` grayscale digit classifier used for grades. The network contains four convolution blocks and a ten-class output layer. |

### `utils/traitement/`

| File | Contents and purpose |
| --- | --- |
| `utils/traitement/pdf_traitement.py` | Wraps `pdftoppm`, renders the DNI and grade regions of PDF pages in parallel, formats temporary filenames, and safely crops character images. |
| `utils/traitement/imageProcessing.py` | OpenCV-based DNI-box detector. It creates several binary variants, detects square candidates, groups boxes into rows, scores sequences, finds anchors, and caches page detections. |
| `utils/traitement/dni_processing.py` | Contains DNI/NIF cleaning, identifier-type detection, expected check-letter generation, matching candidates, and the optional CSV-based `DNIProcessor` helper. |
| `utils/traitement/training_random_traitement.py` | Defines torchvision training transformations, including affine changes, low-resolution simulation, blur, stroke filters, and random inversion. |

### `utils/pipelines/`

| File | Contents and purpose |
| --- | --- |
| `utils/pipelines/remplacement_bascar_inicio_copias.py` | Finds probable first pages of exam copies. It emits search progress, stores detected DNI page crops, scores candidate rows, and provides coordinate fallbacks. |
| `utils/pipelines/renplacement_compute_coords_from_main_block.py` | Recomputes DNI character coordinates for a detected first page. It uses strict and permissive detection modes, falls back to synthetic boxes when needed, and distributes PDF pages across CPU buckets. |

### `utils/metrics/`

| File | Contents and purpose |
| --- | --- |
| `utils/metrics/classification_metric.py` | Defines `ClassificationMetric`, which computes per-class precision, recall, F1 and accuracy values, writes CSV output, and generates evaluation figures. |

## Operational Notes

- Keep `core/checkpoints/best_model.pt` and `core/checkpoints/exammodel4.pt` available in production.
- Do not include hyphens inside the individual user, subject or exam identifiers because `utils/constants.py` splits the composite index on `-`.
- Ensure that the PDF name passed to `main.py` does not include the `.pdf` suffix.
- If a process is interrupted before normal completion, its `utils/.img-dumps/<index>/` directory can remain on disk and may be removed manually after confirming that no process is using it.
- Progress and result messages are part of the backend integration contract. Preserve their prefixes when modifying the emitter or the pipeline.
