from __future__ import annotations

import csv
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
from utils.constants import FALLBACK_CLASSES
from utils.traitement.imageProcessing import remove_margin_all, is_square
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


def _grade_grid_digit_boxes(img_grey):
    dark_pixels = (img_grey < 180).astype(np.uint8)
    height, width = dark_pixels.shape

    horizontal_runs = _contiguous_runs(
        np.where(dark_pixels.sum(axis=1) > width * 0.25)[0]
    )
    y_positions = _run_centers(horizontal_runs)
    row_intervals = [
        (y0, y1)
        for y0, y1 in zip(y_positions, y_positions[1:])
        if 70 <= y1 - y0 <= 220
    ]
    if len(row_intervals) == 0:
        return []

    vertical_runs = _contiguous_runs(
        np.where(dark_pixels.sum(axis=0) > height * 0.15)[0]
    )

    best_interval = None
    for row_top, row_bottom in row_intervals:
        x_positions = []
        for x_start, x_end in vertical_runs:
            x_pos = int(round((x_start + x_end) / 2))
            column = dark_pixels[row_top:row_bottom, max(0, x_pos - 2):min(width, x_pos + 3)]
            if column.size == 0:
                continue

            coverage = (column.sum(axis=1) > 0).mean()
            if coverage <= 0.82:
                continue

            top_band = dark_pixels[
                max(0, row_top - 5):min(height, row_top + 8),
                max(0, x_pos - 3):min(width, x_pos + 4),
            ]
            bottom_band = dark_pixels[
                max(0, row_bottom - 8):min(height, row_bottom + 5),
                max(0, x_pos - 3):min(width, x_pos + 4),
            ]
            if top_band.sum() == 0 or bottom_band.sum() == 0:
                continue

            x_positions.append(x_pos)

        merged_positions = []
        for x_pos in sorted(x_positions):
            if len(merged_positions) > 0 and x_pos - merged_positions[-1] < 12:
                merged_positions[-1] = int(round((merged_positions[-1] + x_pos) / 2))
            else:
                merged_positions.append(x_pos)

        if best_interval is None or len(merged_positions) > len(best_interval[2]):
            best_interval = (row_top, row_bottom, merged_positions)

    if best_interval is None:
        return []

    row_top, row_bottom, x_positions = best_interval
    candidate_boxes = []
    candidate_widths = []
    for x0, x1 in zip(x_positions, x_positions[1:]):
        cell_width = x1 - x0
        if 40 <= cell_width <= 220:
            candidate_boxes.append((x0, row_top, x1, row_bottom))
            candidate_widths.append(cell_width)

    if len(candidate_boxes) == 0:
        return []

    wide_widths = [width for width in candidate_widths if width >= 100]
    reference_width = float(np.median(wide_widths if len(wide_widths) > 0 else candidate_widths))
    digit_boxes = []
    for box in candidate_boxes:
        x0, y0, x1, y1 = box
        cell_width = x1 - x0
        cell_height = y1 - y0
        if cell_width < reference_width * 0.65:
            continue

        margin_x = max(10, int(cell_width * 0.14))
        margin_y = max(10, int(cell_height * 0.14))
        inner = img_grey[y0 + margin_y:y1 - margin_y, x0 + margin_x:x1 - margin_x]
        if inner.size == 0:
            continue

        ink_ratio = np.count_nonzero(inner < 200) / inner.size
        if ink_ratio > 0.012:
            digit_boxes.append((x0, y0, x1, y1))

    return digit_boxes


def _crop_grade_digits_from_grid(img, img_grey):
    digit_boxes = _grade_grid_digit_boxes(img_grey)
    crop_califications_list = []
    for x0, y0, x1, y1 in digit_boxes:
        cell_width = x1 - x0
        cell_height = y1 - y0
        margin_x = max(10, int(cell_width * 0.14))
        margin_y = max(10, int(cell_height * 0.14))
        img_aux = img.crop((x0 + margin_x, y0 + margin_y, x1 - margin_x, y1 - margin_y))
        img_auxCV = cv.cvtColor(np.array(img_aux), cv.COLOR_BGR2GRAY)
        img_auxCV = cv.resize(img_auxCV, (28, 28))
        img_auxCV = cv.bitwise_not(img_auxCV)
        crop_califications_list.append(Image.fromarray(img_auxCV).convert('L'))

    return crop_califications_list


def detec_calification(numPage, model, classes=None, device=None):
    # Read the grade area, detect the filled boxes, and classify each handwritten digit.
    
    path_to_calification = build_dump_path("calification", numPage)
    
    img = Image.open(path_to_calification)
    
    img_grey = cv.cvtColor(np.array(img), cv.COLOR_BGR2GRAY)
    crop_califications_list = _crop_grade_digits_from_grid(img, img_grey)
    if len(crop_califications_list) > 0:
        print("Grid grade detection: " + str(len(crop_califications_list)) + " digit cells on page " + str(numPage))

    if len(crop_califications_list) == 0:
        print("Falling back to contour grade detection on page " + str(numPage))
    #cv.imwrite(output_folder + "calification-grey-1-" + str(numPage) + ".png", img_grey)
        blur = cv.GaussianBlur(img_grey, (5, 5), 0)
    #cv.imwrite(output_folder + "calification-blur-1-" + str(numPage) + ".png", blur)
        img_edge = cv.Canny(blur, 30, 200, 1)
    #cv.imwrite(output_folder + "calification-edge-1-" + str(numPage) + ".png", img_edge)
    # Close small gaps so square borders are detected as complete contours.
        kernel = cv.getStructuringElement(cv.MORPH_RECT, (3, 3))
        closed = cv.morphologyEx(img_edge, cv.MORPH_CLOSE, kernel)
    
    #cv.imwrite(output_folder + "calification-edge-closed" + str(numPage) + ".png", closed)
    
        contours, _ = cv.findContours(closed, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)
    
        square_contours = []
        for i, contour in enumerate(contours):
            if is_square(contour):
                square_contours.append(contour)
            
    # Sort left-to-right so the predicted digits keep the same order as the written grade.
        square_contours = sorted(square_contours, key = lambda contour: cv.boundingRect(contour)[0] )
    
    
        for i, contour in enumerate(square_contours):
            x, y, w, h = cv.boundingRect(contour)
        
        #print(str(numPage) + " and contour " + str(i) + " is square")
            pathToClean = build_dump_path("clean1", numPage) + f"-{i}.png"
        
            img_aux = img.crop((x, y, x + w, y + h))
        
            img_aux.save(pathToClean)
        #img_aux = closed[y:y+h, x:x+w]
        
            img_auxCV = cv.imread(pathToClean)
        
            img_auxCV = remove_margin_all(img_auxCV)
            img_auxCV = cv.cvtColor(img_auxCV, cv.COLOR_BGR2GRAY)
        #ToGrey
        
        #
            _, binary_img = cv.threshold(img_auxCV, 100, 255, cv.THRESH_BINARY)
            white_pixels = cv.countNonZero(binary_img)
            total_pixels = binary_img.size
    
        # Skip boxes that are completely blank.
            print("White pixels: " + str(white_pixels) + " Total pixels: " + str(total_pixels) + " = " + str(white_pixels/total_pixels)+ "  Page: " + str(numPage) + "  Contour: " + str(i))
            if white_pixels == total_pixels:
                print("Empty image")
                continue
        
            img_auxCV = cv.resize(img_auxCV, (28, 28))
        
            img_auxCV = cv.bitwise_not(img_auxCV)
        
            cv.imwrite(build_dump_path("final-cut", numPage) + f"-{i}.png", img_auxCV)
        #os.remove(pathToClean)
            imgf = Image.open(build_dump_path("final-cut", numPage) + f"-{i}.png").convert('L')
        
            crop_califications_list.append(imgf)
            continue


    predictions_califications = []
    for i, crop_calification in enumerate(crop_califications_list):
        # Quantize grayscale values to the same buckets used when preparing training samples.
        M = np.zeros((28,28), dtype=int)
        for x in range(28):
            for y in range(28):
                z=crop_calification.getpixel((x,y))
                    
                if z <= 13:
                    z = 0
                elif z <= 51:
                    z = 26
                elif z <= 76:
                    z = 153
                else:
                    z = 254
                M[y,x] = z
                
        tensor = torch.Tensor(M).unsqueeze(0).unsqueeze(0)
        if device is not None:
            tensor = tensor.to(device)
        
        with torch.no_grad():
            output = model(tensor)
            _, predicted = torch.max(output, dim=1)

        predicted_value = predicted.item()
        if classes is not None and predicted_value < len(classes):
            label = display_label(classes[predicted_value])
            if not str(label).isdigit():
                continue
            predicted_value = int(label)

        predictions_califications.append(predicted_value)
        
        
    
    
    os.remove(path_to_calification)
    
    calification = ''.join([str(x) for x in predictions_califications])
    print(str(len(predictions_califications)) + " " + str(calification))
    
    # Rebuild a decimal grade according to how many boxes were detected.
    if(len(predictions_califications) == 0):
        return ""
    if(len(predictions_califications) == 1):
        return str(predictions_califications[0])
    if(len(predictions_califications) == 2):
        return str(predictions_califications[0]) + "." + str(predictions_califications[1])
    if(len(predictions_califications) == 3):
        return str(predictions_califications[0]) + "."+ str(predictions_califications[1]) + str(predictions_califications[2])
    if(len(predictions_califications) == 4):
        if(predictions_califications[1] >0):
            return str(predictions_califications[1]) + "."+ str(predictions_califications[2]) + str(predictions_califications[3])
        else:
            return float(0)
