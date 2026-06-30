from __future__ import annotations

import csv
from itertools import combinations
from pathlib import Path
from typing import List, Tuple, Sequence
import torch
import numpy as np
import glob
from PIL import Image, ImageOps
import cv2 as cv
import os 

from utils.Model.smallCNN import SmallCNN
from utils.Model.CNN import CNN
from utils.Model.CNN_chiffre_new import CNN_chiffre_new
from utils.constants import FALLBACK_CLASSES
from utils.traitement.imageProcessing import is_square
from utils.traitement.pdf_traitement import build_dump_path







def choose_device(requested: str) -> torch.device:
    requested = requested.lower()
    if requested == "gpu":
        requested = "cuda"

    if requested == "cpu":
        return torch.device("cpu")

    if requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but not available. Run with --device cpu.")
        return torch.device("cuda")

    try:
        if torch.cuda.is_available():
            device = torch.device("cuda")
            torch.zeros(1).to(device)
            return device
    except Exception as exc:
        print(f"[WARN] CUDA unavailable, falling back to CPU: {exc}")

    return torch.device("cpu")

def normalize_DNI(dni):
    # Remove leading zeros so OCR output can be compared against stored DNI values reliably.
    return dni.lstrip('0')


def make_weighted_sampler(dataset):
    from torch.utils.data import WeightedRandomSampler

    targets = [label for _, label in dataset.samples]
    class_counts = np.bincount(targets, minlength=len(dataset.classes))
    class_counts = np.maximum(class_counts, 1)
    class_weights = 1.0 / class_counts
    sample_weights = [class_weights[label] for label in targets]

    return WeightedRandomSampler(
        weights=torch.DoubleTensor(sample_weights),
        num_samples=len(sample_weights),
        replacement=True,
    )
    
def display_label(class_name: str) -> str:
    # e.g. "000_0" -> "0", "036_A" -> "A"
    if "_" in class_name and class_name.split("_", 1)[0].isdigit():
        return class_name.split("_", 1)[1]
    return class_name





def evaluate(model, loader, criterion, device) -> Tuple[float, float]:
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total_examples = 0

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)

            logits = model(images)
            loss = criterion(logits, labels)

            total_loss += loss.item() * images.size(0)
            total_correct += (logits.argmax(dim=1) == labels).sum().item()
            total_examples += images.size(0)

    if total_examples == 0:
        return 0.0, 0.0
    return total_loss / total_examples, total_correct / total_examples


def write_history_row(path: Path, row: dict, write_header: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)
        
        
def ensure_white_background(gray: Image.Image) -> Image.Image:
    """Ensure white background with dark character (invert if needed)."""
    arr = np.asarray(gray)
    if arr.size == 0:
        return gray

    border_width = max(1, min(arr.shape[0], arr.shape[1]) // 20)
    border = np.concatenate([
        arr[:border_width, :].ravel(),
        arr[-border_width:, :].ravel(),
        arr[:, :border_width].ravel(),
        arr[:, -border_width:].ravel(),
    ])

    background_median = float(np.median(border))

    # Invert if background is dark so we always have white background with dark strokes.
    if background_median < 128:
        gray = ImageOps.invert(gray)

    return gray

def crop_to_character(gray: Image.Image, threshold: int = 245, margin_ratio: float = 0.20) -> Image.Image:
    arr = np.asarray(gray)
    mask = arr < threshold

    if not np.any(mask):
        return gray

    ys, xs = np.where(mask)
    y_min, y_max = int(ys.min()), int(ys.max())
    x_min, x_max = int(xs.min()), int(xs.max())

    width = x_max - x_min + 1
    height = y_max - y_min + 1
    margin = int(max(width, height) * margin_ratio)

    x_min = max(0, x_min - margin)
    y_min = max(0, y_min - margin)
    x_max = min(gray.width - 1, x_max + margin)
    y_max = min(gray.height - 1, y_max + margin)

    return gray.crop((x_min, y_min, x_max + 1, y_max + 1))

def pad_to_square(gray: Image.Image, background: int = 255) -> Image.Image:
    side = max(gray.width, gray.height)
    canvas = Image.new("L", (side, side), color=background)
    x = (side - gray.width) // 2
    y = (side - gray.height) // 2
    canvas.paste(gray, (x, y))
    return canvas


def preprocess_image(image: Image.Image, image_size: int = 64) -> Image.Image:
    gray = image.convert("L")
    gray = ensure_white_background(gray)
    gray = ImageOps.autocontrast(gray)
    gray = crop_to_character(gray, threshold=245, margin_ratio=0.20)
    gray = pad_to_square(gray, background=255)
    gray = gray.resize((image_size, image_size), Image.Resampling.LANCZOS)
    return gray

def resolve_images(patterns: Sequence[str]) -> List[Path]:
    paths: List[Path] = []
    for pattern in patterns:
        matched = sorted(glob.glob(pattern))
        if matched:
            paths.extend(Path(p) for p in matched)
        else:
            paths.append(Path(pattern))

    valid = []
    for p in paths:
        if p.exists() and p.is_file():
            valid.append(p)
        else:
            print(f"[WARN] Image not found, skipping: {p}")
    return valid



def image_to_tensor(image_path: Path, image_size: int) -> torch.Tensor:
    image = Image.open(image_path)
    processed = preprocess_image(image, image_size=image_size)

    arr = np.asarray(processed).astype(np.float32) / 255.0
    tensor = torch.from_numpy(arr).unsqueeze(0)  # [1, H, W]

    # Same normalisation as the training pipeline: Normalize(mean=[0.5], std=[0.5]).
    tensor = (tensor - 0.5) / 0.5
    return tensor


def display_label(class_name: str) -> str:
    # e.g. "000_0" -> "0", "036_A" -> "A"
    if "_" in class_name and class_name.split("_", 1)[0].isdigit():
        return class_name.split("_", 1)[1]
    return class_name


def load_model(checkpoint_path: Path, device: torch.device):
    checkpoint = torch.load(checkpoint_path, map_location="cpu")

    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
        classes = checkpoint.get("classes", FALLBACK_CLASSES)
    else:
        # Fallback for checkpoints saved with torch.save(model.state_dict(), path) directly.
        state_dict = checkpoint
        classes = FALLBACK_CLASSES

    model = SmallCNN(num_classes=len(classes))
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()

    return model, list(classes)


def load_exam_model(checkpoint_path: Path, device: torch.device):
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    state_dict = checkpoint.get("model_state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint

    model_name = checkpoint.get("model_name") if isinstance(checkpoint, dict) else None
    if model_name == "CNN_chiffre_new":
        classes = checkpoint.get("classes", [])
        if list(classes) != [f"{digit:03d}_{digit}" for digit in range(10)]:
            raise ValueError(
                "CNN_chiffre_new checkpoint must contain digit classes 000_0 through 009_9"
            )
        model = CNN_chiffre_new()
    else:
        model = CNN()

    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()

    return model


def make_prediction_rows(model, classes: List[str], image_paths: List[Path], device: torch.device, image_size: int, topk: int):
    rows = []
    topk = min(topk, len(classes))

    with torch.no_grad():
        for image_path in image_paths:
            tensor = image_to_tensor(image_path, image_size=image_size).unsqueeze(0).to(device)  # [1,1,H,W]
            logits = model(tensor)
            probs = torch.softmax(logits, dim=1)[0]
            values, indices = torch.topk(probs, k=topk)

            top_items = []
            for prob, idx in zip(values.cpu().tolist(), indices.cpu().tolist()):
                class_name = classes[idx]
                label = display_label(class_name)
                top_items.append((label, prob, class_name))

            rows.append({
                "image": str(image_path),
                "prediction": top_items[0][0],
                "confidence": top_items[0][1],
                "topk": top_items,
            })

    return rows


def save_csv(rows, output_csv: Path):
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image", "prediction", "confidence", "top_predictions"])
        for row in rows:
            top_text = " | ".join([f"{lab}:{prob:.4f}" for lab, prob, _ in row["topk"]])
            writer.writerow([row["image"], row["prediction"], f"{row['confidence']:.6f}", top_text])


def save_preprocessed_images(image_paths: List[Path], output_dir: Path, image_size: int):
    output_dir.mkdir(parents=True, exist_ok=True)
    for image_path in image_paths:
        processed = preprocess_image(Image.open(image_path), image_size=image_size)
        processed.save(output_dir / image_path.name)


def print_results(rows):
    print("\nPrediction results")
    print("-" * 100)
    print(f"{'image':45s} | {'pred':6s} | {'conf':8s} | top")
    print("-" * 100)
    for row in rows:
        name = Path(row["image"]).name
        top_text = ", ".join([f"{lab}={prob*100:.2f}%" for lab, prob, _ in row["topk"]])
        print(f"{name[:45]:45s} | {row['prediction']:^6s} | {row['confidence']*100:7.2f}% | {top_text}")
    print("-" * 100)


def _contiguous_runs(values):
    values = list(values)
    if len(values) == 0:
        return []

    runs = []
    start = values[0]
    previous = values[0]
    for value in values[1:]:
        if value <= previous + 1:
            previous = value
        else:
            runs.append((start, previous))
            start = value
            previous = value
    runs.append((start, previous))
    return runs


def _run_centers(runs):
    return [int(round((start + end) / 2)) for start, end in runs]


GRADE_DIGIT_CELL_COUNT = 4
GRADE_CELL_INK_THRESHOLD = 0.012


def _grade_cell_has_ink(img_grey, box):
    x0, y0, x1, y1 = box
    cell_width = x1 - x0
    cell_height = y1 - y0
    margin_x = max(10, int(cell_width * 0.14))
    margin_y = max(10, int(cell_height * 0.14))
    inner = img_grey[y0 + margin_y:y1 - margin_y, x0 + margin_x:x1 - margin_x]
    if inner.size == 0:
        return False

    ink_ratio = np.count_nonzero(inner < 200) / inner.size
    return ink_ratio > GRADE_CELL_INK_THRESHOLD


def _merge_nearby_positions(positions, tolerance=12):
    clusters = []
    for position in sorted(int(round(value)) for value in positions):
        if clusters and position - clusters[-1][-1] <= tolerance:
            clusters[-1].append(position)
        else:
            clusters.append([position])
    return [
        int(round(float(np.median(cluster))))
        for cluster in clusters
    ]


def _grade_horizontal_positions(img_grey, dark_pixels):
    """Find horizontal grid lines, including lines from slightly rotated scans."""
    height, width = dark_pixels.shape
    projection_runs = _contiguous_runs(
        np.where(dark_pixels.sum(axis=1) > width * 0.25)[0]
    )
    positions = _run_centers(projection_runs)

    edges = cv.Canny(img_grey, 50, 150)
    lines = cv.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=55,
        minLineLength=max(100, int(width * 0.12)),
        maxLineGap=50,
    )
    if lines is not None:
        for x0, y0, x1, y1 in lines[:, 0]:
            delta_x = abs(int(x1) - int(x0))
            delta_y = abs(int(y1) - int(y0))
            if delta_x == 0 or delta_y > max(8, int(delta_x * 0.08)):
                continue
            positions.append((int(y0) + int(y1)) / 2)

    return [
        position
        for position in _merge_nearby_positions(positions)
        if 0 <= position < height
    ]


def _grade_digit_boxes_for_row(img_grey, dark_pixels, row_top, row_bottom):
    height, width = dark_pixels.shape
    row_height = row_bottom - row_top
    line_search_margin = min(35, max(15, int(row_height * 0.22)))
    row_pixels = dark_pixels[row_top:row_bottom, :]
    vertical_runs = _contiguous_runs(
        np.where(row_pixels.sum(axis=0) > row_height * 0.35)[0]
    )
    x_positions = []
    for x_start, x_end in vertical_runs:
        x_pos = int(round((x_start + x_end) / 2))
        column = dark_pixels[
            row_top:row_bottom,
            max(0, x_pos - 3):min(width, x_pos + 4),
        ]
        if column.size == 0:
            continue

        coverage = (column.sum(axis=1) > 0).mean()
        # A partially erased grid line can fall below the old strict threshold,
        # while a handwritten vertical stroke generally covers less than 70%.
        if coverage <= 0.70:
            continue

        top_band = dark_pixels[
            max(0, row_top - line_search_margin):
            min(height, row_top + line_search_margin + 1),
            max(0, x_pos - 4):min(width, x_pos + 5),
        ]
        bottom_band = dark_pixels[
            max(0, row_bottom - line_search_margin):
            min(height, row_bottom + line_search_margin + 1),
            max(0, x_pos - 4):min(width, x_pos + 5),
        ]
        if top_band.sum() == 0 or bottom_band.sum() == 0:
            continue

        x_positions.append(x_pos)

    x_positions = _merge_nearby_positions(x_positions)
    if len(x_positions) < 6:
        return None

    best_candidate = None
    # Six real boundaries delimit DD,DD. Testing subsets allows vertical
    # handwriting strokes, especially the digit "1", to be ignored.
    for boundaries in combinations(x_positions, 6):
        cell_widths = [
            x1 - x0
            for x0, x1 in zip(boundaries, boundaries[1:])
        ]
        if any(cell_width < 35 or cell_width > 240 for cell_width in cell_widths):
            continue

        digit_widths = [
            cell_widths[0],
            cell_widths[1],
            cell_widths[3],
            cell_widths[4],
        ]
        reference_width = float(np.median(digit_widths))
        separator_width = cell_widths[2]
        cell_aspect_ratio = row_height / max(reference_width, 1.0)
        if (
            not 0.70 <= cell_aspect_ratio <= 1.60
            or separator_width >= reference_width * 0.65
            or any(
                cell_width < reference_width * 0.65
                or cell_width > reference_width * 1.45
                for cell_width in digit_widths
            )
        ):
            continue

        width_variation = (
            float(np.std(digit_widths))
            / max(float(np.mean(digit_widths)), 1.0)
        )
        if width_variation > 0.25:
            continue

        digit_boxes = [
            (boundaries[0], row_top, boundaries[1], row_bottom),
            (boundaries[1], row_top, boundaries[2], row_bottom),
            (boundaries[3], row_top, boundaries[4], row_bottom),
            (boundaries[4], row_top, boundaries[5], row_bottom),
        ]
        grid_left = boundaries[0]
        grid_right = boundaries[-1]
        top_line_band = dark_pixels[
            max(0, row_top - line_search_margin):
            min(height, row_top + line_search_margin + 1),
            grid_left:grid_right,
        ]
        bottom_line_band = dark_pixels[
            max(0, row_bottom - line_search_margin):
            min(height, row_bottom + line_search_margin + 1),
            grid_left:grid_right,
        ]
        top_line_coverage = (top_line_band.sum(axis=0) > 0).mean()
        bottom_line_coverage = (bottom_line_band.sum(axis=0) > 0).mean()
        if top_line_coverage < 0.45 or bottom_line_coverage < 0.45:
            continue

        # A candidate spanning two stacked grade rows contains their shared
        # horizontal divider. Reject it before that divider is mistaken for
        # handwriting in every cell.
        inner_margin = max(10, int(row_height * 0.18))
        inner_rows = dark_pixels[
            row_top + inner_margin:row_bottom - inner_margin,
            grid_left:grid_right,
        ]
        if (
            inner_rows.size > 0
            and (inner_rows.sum(axis=1) / max(grid_right - grid_left, 1)).max() > 0.30
        ):
            continue

        separator_ratio = separator_width / reference_width
        filled_cell_count = sum(
            _grade_cell_has_ink(img_grey, box)
            for box in digit_boxes
        )
        score = (
            filled_cell_count * 2.0
            - width_variation
            - abs(separator_ratio - 0.50)
            - row_top / max(height, 1) * 0.05
        )
        if best_candidate is None or score > best_candidate[1]:
            best_candidate = (digit_boxes, score)

    return best_candidate


def _grade_grid_cells(img_grey):
    """Return the four DD,DD grade cells, including cells with no handwriting."""
    dark_pixels = (img_grey < 180).astype(np.uint8)
    height, width = dark_pixels.shape

    y_positions = _grade_horizontal_positions(img_grey, dark_pixels)
    # Printed text or handwriting can create extra Hough lines inside a cell.
    # Evaluate non-adjacent line pairs too; the border-coverage checks below
    # reject pairs that are not the actual top and bottom grid borders.
    row_intervals = []
    for index, y0 in enumerate(y_positions):
        for y1 in y_positions[index + 1:]:
            distance = y1 - y0
            if distance < 70:
                continue
            if distance > 220:
                break
            row_intervals.append((y0, y1))
    if len(row_intervals) == 0:
        return []

    row_candidates = []
    for row_top, row_bottom in row_intervals:
        candidate = _grade_digit_boxes_for_row(
            img_grey,
            dark_pixels,
            row_top,
            row_bottom,
        )
        if candidate is not None:
            row_candidates.append(candidate)

    if not row_candidates:
        return []

    digit_boxes, _ = max(row_candidates, key=lambda candidate: candidate[1])
    return [
        (box, _grade_cell_has_ink(img_grey, box))
        for box in digit_boxes
    ]


def _crop_grade_cells(img, img_grey, cells):
    crops = []
    for (x0, y0, x1, y1), has_ink in cells:
        if not has_ink:
            crops.append(None)
            continue

        cell_width = x1 - x0
        cell_height = y1 - y0
        margin_x = max(10, int(cell_width * 0.14))
        margin_y = max(10, int(cell_height * 0.14))
        img_aux = img.crop((x0 + margin_x, y0 + margin_y, x1 - margin_x, y1 - margin_y))
        img_auxCV = cv.cvtColor(np.array(img_aux), cv.COLOR_BGR2GRAY)
        img_auxCV = cv.resize(img_auxCV, (28, 28))
        img_auxCV = cv.bitwise_not(img_auxCV)
        crops.append(Image.fromarray(img_auxCV).convert('L'))

    return crops


def _boxes_overlap(box_a, box_b):
    ax0, ay0, ax1, ay1 = box_a
    bx0, by0, bx1, by1 = box_b
    intersection_width = max(0, min(ax1, bx1) - max(ax0, bx0))
    intersection_height = max(0, min(ay1, by1) - max(ay0, by0))
    intersection = intersection_width * intersection_height
    area_a = max(0, ax1 - ax0) * max(0, ay1 - ay0)
    area_b = max(0, bx1 - bx0) * max(0, by1 - by0)
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def _grade_contour_cells(img_grey):
    """Fallback detector for the four square grade cells."""
    blur = cv.GaussianBlur(img_grey, (5, 5), 0)
    img_edge = cv.Canny(blur, 30, 200, 1)
    kernel = cv.getStructuringElement(cv.MORPH_RECT, (3, 3))
    closed = cv.morphologyEx(img_edge, cv.MORPH_CLOSE, kernel)
    contours, _ = cv.findContours(closed, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)

    boxes = []
    for contour in contours:
        if not is_square(contour):
            continue

        x, y, w, h = cv.boundingRect(contour)
        box = (x, y, x + w, y + h)
        if any(_boxes_overlap(box, existing) > 0.75 for existing in boxes):
            continue
        boxes.append(box)

    if len(boxes) < GRADE_DIGIT_CELL_COUNT:
        return []

    # The crop can contain parts of adjacent rows. Select four aligned boxes
    # belonging to the same DD,DD row.
    boxes.sort(key=lambda box: ((box[1] + box[3]) / 2, box[0]))
    rows = []
    for box in boxes:
        center_y = (box[1] + box[3]) / 2
        box_height = box[3] - box[1]
        for row in rows:
            if abs(center_y - row["center_y"]) <= max(15, box_height * 0.30):
                row["boxes"].append(box)
                row["center_y"] = float(np.mean([
                    (candidate[1] + candidate[3]) / 2
                    for candidate in row["boxes"]
                ]))
                break
        else:
            rows.append({"center_y": center_y, "boxes": [box]})

    candidate_rows = [
        sorted(row["boxes"], key=lambda box: box[0])
        for row in rows
        if len(row["boxes"]) >= GRADE_DIGIT_CELL_COUNT
    ]
    if not candidate_rows:
        return []

    digit_boxes = max(
        candidate_rows,
        key=lambda row: sum(
            (box[2] - box[0]) * (box[3] - box[1])
            for box in row
        ),
    )[:GRADE_DIGIT_CELL_COUNT]
    return [
        (box, _grade_cell_has_ink(img_grey, box))
        for box in digit_boxes
    ]


def _classify_grade_digit(crop, model, classes, device):
    pixels = np.asarray(crop, dtype=np.uint8)
    if getattr(model, "input_mode", None) == "normalized_inverted_28":
        model_input = pixels.astype(np.float32) / 255.0
        model_input = (model_input - 0.5) / 0.5
    else:
        # Legacy exammodel4.pt input preprocessing.
        model_input = np.select(
            [pixels <= 13, pixels <= 51, pixels <= 76],
            [0, 26, 153],
            default=254,
        ).astype(np.float32)

    tensor = torch.tensor(model_input, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
    if device is not None:
        tensor = tensor.to(device)

    with torch.no_grad():
        output = model(tensor)
        predicted_value = int(output.argmax(dim=1).item())

    if classes is not None and predicted_value < len(classes):
        label = display_label(classes[predicted_value])
        if not str(label).isdigit():
            raise ValueError(f"Non-digit grade class predicted: {label}")
        predicted_value = int(label)

    if not 0 <= predicted_value <= 9:
        raise ValueError(f"Invalid grade digit predicted: {predicted_value}")
    return predicted_value


def detec_calification(numPage, model, classes=None, device=None):
    # Detect all four DD,DD cells. Empty cells are zero; only filled cells go
    # through the digit classifier.
    path_to_calification = build_dump_path("calification", numPage)
    img = Image.open(path_to_calification)
    img_grey = cv.cvtColor(np.array(img), cv.COLOR_BGR2GRAY)
    cells = _grade_grid_cells(img_grey)
    detector_name = "grid"
    if len(cells) != GRADE_DIGIT_CELL_COUNT:
        detector_name = "contour fallback"
        cells = _grade_contour_cells(img_grey)

    if len(cells) != GRADE_DIGIT_CELL_COUNT:
        print(
            f"[GRADE] Page {numPage}: unable to detect the four DD,DD cells",
            flush=True,
        )
        os.remove(path_to_calification)
        return ""

    crops = _crop_grade_cells(img, img_grey, cells)
    statuses = ["filled" if crop is not None else "empty" for crop in crops]
    print(
        f"[GRADE] Page {numPage}: {detector_name} cells = {statuses}",
        flush=True,
    )

    digits = []
    for position, crop in enumerate(crops, start=1):
        if crop is None:
            digits.append(0)
            continue

        try:
            digits.append(_classify_grade_digit(crop, model, classes, device))
        except ValueError as exc:
            print(
                f"[GRADE] Page {numPage}: cell {position} classification failed ({exc}); using 0",
                flush=True,
            )
            digits.append(0)

    os.remove(path_to_calification)

    integer_part = digits[0] * 10 + digits[1]
    decimal_part = digits[2] * 10 + digits[3]
    grade = integer_part + decimal_part / 100.0
    formatted_grade = f"{integer_part}.{decimal_part:02d}"
    print(
        f"[GRADE] Page {numPage}: digits={digits} -> grade={formatted_grade}",
        flush=True,
    )
    if grade > 10:
        print(
            f"[GRADE WARNING] Page {numPage}: detected grade {formatted_grade} is greater than 10",
            flush=True,
        )

    return formatted_grade
