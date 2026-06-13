"""
Merge two handwritten-character datasets into a single standardised dataset.

Expected inputs:
  1) archive (1)(1).zip
     - augmented_images/augmented_images1/<class>/*.png
     - handwritten-english-characters-and-digits/combined_folder/{train,test}/<class>/*.png

  2) CHoiCe-Dataset-main.zip
     - CHoiCe-Dataset-main/V0.3/label.txt
     - CHoiCe-Dataset-main/V0.3/data-bin/<class_id>/*.png
       or CHoiCe-Dataset-main/V0.3/data/<class_id>/*.png

Output:
  unified_dataset/
    images/
      train/<class_folder>/*.png
      val/<class_folder>/*.png
      test/<class_folder>/*.png
    labels.csv
    classes.json
    summary_by_class.csv
    summary_by_split.csv

Images are converted to grayscale, white background with dark character,
cropped around the character, padded to a square, then resized.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import random
import shutil
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageOps


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

# Stable class order: digits, lowercase, uppercase.
CANONICAL_LABELS = (
    [str(i) for i in range(10)]
    + [chr(ord("a") + i) for i in range(26)]
    + [chr(ord("A") + i) for i in range(26)]
)

LABEL_TO_ID = {label: idx for idx, label in enumerate(CANONICAL_LABELS)}


@dataclass(frozen=True)
class Sample:
    zip_path: Path
    inner_path: str
    label: str
    source: str


def safe_class_folder(label: str) -> str:
    """
    Returns an ImageFolder-compatible folder name, safe on case-insensitive filesystems.
    Examples:
      label 'a' -> '010_a'
      label 'A' -> '036_A'
    """
    return f"{LABEL_TO_ID[label]:03d}_{label}"


def normalize_archive_label(raw_label: str) -> Optional[str]:
    """
    The first dataset uses:
      - '0'...'9'
      - 'a'...'z'
      - 'A_caps'...'Z_caps'
    Converts everything to canonical labels:
      - '0'...'9'
      - 'a'...'z'
      - 'A'...'Z'
    """
    raw_label = raw_label.strip()
    if raw_label in LABEL_TO_ID:
        return raw_label

    if raw_label.endswith("_caps"):
        candidate = raw_label.replace("_caps", "")
        if len(candidate) == 1 and candidate.isalpha():
            return candidate.upper()

    return None


def load_choice_labels(choice_zip: zipfile.ZipFile) -> List[str]:
    candidates = [
        name for name in choice_zip.namelist()
        if name.endswith("V0.3/label.txt")
    ]
    if not candidates:
        raise FileNotFoundError("Cannot find V0.3/label.txt in CHoiCe-Dataset-main.zip")

    labels = choice_zip.read(candidates[0]).decode("utf-8", errors="replace").splitlines()
    labels = [x.strip() for x in labels if x.strip() != ""]

    if len(labels) != 62:
        raise ValueError(f"label.txt should contain 62 labels, found {len(labels)}")

    return labels


def iter_archive_samples(archive_zip_path: Path) -> Iterable[Sample]:
    """
    Reads images from the first dataset directly from the ZIP.
    Uses both:
      - augmented images
      - original train/test images
    """
    with zipfile.ZipFile(archive_zip_path) as z:
        for inner_path in z.namelist():
            if not inner_path.lower().endswith(IMAGE_EXTENSIONS):
                continue

            parts = inner_path.strip("/").split("/")
            if len(parts) < 2:
                continue

            # The class is the folder immediately above the file.
            raw_class = parts[-2]
            label = normalize_archive_label(raw_class)
            if label is None:
                continue

            if inner_path.startswith("augmented_images/"):
                source = "archive_augmented"
            elif "combined_folder/train/" in inner_path:
                source = "archive_original_train"
            elif "combined_folder/test/" in inner_path:
                source = "archive_original_test"
            else:
                source = "archive_other"

            yield Sample(
                zip_path=archive_zip_path,
                inner_path=inner_path,
                label=label,
                source=source,
            )


def iter_choice_samples(choice_zip_path: Path, variant: str = "data-bin") -> Iterable[Sample]:
    """
    Reads CHoiCe images from the ZIP.
    variant='data-bin': binarized 28x28 images.
    variant='data':     non-binarized 28x28 images.
    """
    assert variant in {"data-bin", "data"}

    with zipfile.ZipFile(choice_zip_path) as z:
        choice_labels = load_choice_labels(z)

        prefix_candidates = [
            name for name in z.namelist()
            if f"V0.3/{variant}/" in name
        ]
        if not prefix_candidates:
            raise FileNotFoundError(f"Cannot find V0.3/{variant}/ in CHoiCe-Dataset-main.zip")

        for inner_path in z.namelist():
            if not inner_path.lower().endswith(IMAGE_EXTENSIONS):
                continue
            if f"V0.3/{variant}/" not in inner_path:
                continue

            parts = inner_path.strip("/").split("/")
            if len(parts) < 2:
                continue

            raw_class_id = parts[-2]
            if not raw_class_id.isdigit():
                continue

            class_id = int(raw_class_id)
            if not 0 <= class_id < len(choice_labels):
                continue

            label = choice_labels[class_id]
            if label not in LABEL_TO_ID:
                continue

            yield Sample(
                zip_path=choice_zip_path,
                inner_path=inner_path,
                label=label,
                source=f"choice_{variant}",
            )


def read_image_from_zip_handle(zip_handle: zipfile.ZipFile, inner_path: str) -> Image.Image:
    data = zip_handle.read(inner_path)

    image = Image.open(io.BytesIO(data))

    # Composite RGBA images onto a white background before converting to grayscale.
    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        background.alpha_composite(image.convert("RGBA"))
        image = background.convert("RGB")

    return image.convert("L")


def ensure_white_background(gray: Image.Image) -> Image.Image:
    """
    Some datasets use white characters on a black background.
    Detects the background from border pixels and inverts if necessary.
    Goal: white background with a dark character.
    """
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

    # Dark background detected -> invert.
    if background_median < 128:
        gray = ImageOps.invert(gray)

    return gray


def crop_to_character(gray: Image.Image, threshold: int = 245, margin_ratio: float = 0.20) -> Image.Image:
    """
    Crops tightly around dark pixels.
    threshold=245 assumes that after normalisation the background is close to 255.
    """
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


def preprocess_image(
    image: Image.Image,
    image_size: int = 64,
    threshold: int = 245,
    margin_ratio: float = 0.20,
) -> Image.Image:
    """
    Full preprocessing pipeline:
      1. Grayscale
      2. White background / dark stroke
      3. Autocontrast
      4. Crop around the character
      5. Square padding
      6. Resize
    """
    gray = image.convert("L")
    gray = ensure_white_background(gray)
    gray = ImageOps.autocontrast(gray)
    gray = crop_to_character(gray, threshold=threshold, margin_ratio=margin_ratio)
    gray = pad_to_square(gray, background=255)
    gray = gray.resize((image_size, image_size), Image.Resampling.LANCZOS)
    return gray


def make_deterministic_filename(sample: Sample, extension: str = ".png") -> str:
    key = f"{sample.zip_path.name}|{sample.inner_path}|{sample.label}|{sample.source}"
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
    return f"{safe_class_folder(sample.label)}_{digest}{extension}"


def stratified_split(
    samples: Sequence[Sample],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> Dict[Sample, str]:
    if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 1e-8:
        raise ValueError("train_ratio + val_ratio + test_ratio must equal 1.")

    rng = random.Random(seed)
    by_label: Dict[str, List[Sample]] = defaultdict(list)
    for sample in samples:
        by_label[sample.label].append(sample)

    sample_to_split: Dict[Sample, str] = {}

    for label, label_samples in by_label.items():
        label_samples = list(label_samples)
        rng.shuffle(label_samples)

        n = len(label_samples)
        n_train = int(round(n * train_ratio))
        n_val = int(round(n * val_ratio))

        # Rounding correction: ensure train + val does not exceed total.
        if n_train + n_val > n:
            n_val = max(0, n - n_train)

        for idx, sample in enumerate(label_samples):
            if idx < n_train:
                split = "train"
            elif idx < n_train + n_val:
                split = "val"
            else:
                split = "test"
            sample_to_split[sample] = split

    return sample_to_split


def write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_dataset(
    archive_zip_paths: List[Path],
    archive_zip_path: Path,
    choice_zip_path: Path,
    output_dir: Path,
    image_size: int = 64,
    train_ratio: float = 0.80,
    val_ratio: float = 0.10,
    test_ratio: float = 0.10,
    seed: int = 42,
    choice_variant: str = "data-bin",
    clean_output: bool = True,
) -> None:
    archive_zip_path = archive_zip_path.resolve()
    choice_zip_path = choice_zip_path.resolve()
    output_dir = output_dir.resolve()

    if not archive_zip_path.exists():
        raise FileNotFoundError(f"File not found: {archive_zip_path}")
    if not choice_zip_path.exists():
        raise FileNotFoundError(f"File not found: {choice_zip_path}")

    if clean_output and output_dir.exists():
        shutil.rmtree(output_dir)

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    samples = []
    samples.extend(iter_archive_samples(archive_zip_path))
    for zip_path in archive_zip_paths:
        samples.extend(iter_archive_samples(zip_path))
        samples.extend(iter_choice_samples(choice_zip_path, variant=choice_variant))

    # Keep only canonical labels.
    samples = [s for s in samples if s.label in LABEL_TO_ID]

    if not samples:
        raise RuntimeError("No images found. Check the ZIP file paths.")

    sample_to_split = stratified_split(
        samples=samples,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        seed=seed,
    )

    metadata_rows: List[dict] = []
    errors: List[dict] = []

    total = len(samples)
    print(f"Total images detected: {total}")

    zip_handles = {
        archive_zip_path: zipfile.ZipFile(archive_zip_path),
        choice_zip_path: zipfile.ZipFile(choice_zip_path),
    }

    try:
        for idx, sample in enumerate(samples, start=1):
            split = sample_to_split[sample]
            label_id = LABEL_TO_ID[sample.label]
            class_folder = safe_class_folder(sample.label)
            filename = make_deterministic_filename(sample)
            relative_path = Path("images") / split / class_folder / filename
            output_path = output_dir / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                raw_image = read_image_from_zip_handle(zip_handles[sample.zip_path], sample.inner_path)
                processed = preprocess_image(raw_image, image_size=image_size)
                processed.save(output_path)
            except Exception as exc:
                errors.append({
                    "zip": str(sample.zip_path),
                    "inner_path": sample.inner_path,
                    "label": sample.label,
                    "source": sample.source,
                    "error": repr(exc),
                })
                continue

            metadata_rows.append({
                "filepath": str(relative_path).replace("\\", "/"),
                "split": split,
                "label": sample.label,
                "label_id": label_id,
                "class_folder": class_folder,
                "source": sample.source,
                "original_zip": sample.zip_path.name,
                "original_path": sample.inner_path,
            })

            if idx % 1000 == 0 or idx == total:
                print(f"Processing: {idx}/{total}")
    finally:
        for handle in zip_handles.values():
            handle.close()

    # Main labels.csv file
    write_csv(
        output_dir / "labels.csv",
        metadata_rows,
        fieldnames=[
            "filepath", "split", "label", "label_id", "class_folder",
            "source", "original_zip", "original_path"
        ],
    )

    # Class mapping
    classes = [
        {
            "label_id": idx,
            "label": label,
            "class_folder": safe_class_folder(label),
        }
        for idx, label in enumerate(CANONICAL_LABELS)
    ]
    with (output_dir / "classes.json").open("w", encoding="utf-8") as f:
        json.dump(classes, f, indent=2, ensure_ascii=False)

    # Summaries
    by_class = Counter(row["label"] for row in metadata_rows)
    summary_by_class = [
        {
            "label_id": LABEL_TO_ID[label],
            "label": label,
            "class_folder": safe_class_folder(label),
            "count": by_class[label],
        }
        for label in CANONICAL_LABELS
    ]
    write_csv(
        output_dir / "summary_by_class.csv",
        summary_by_class,
        fieldnames=["label_id", "label", "class_folder", "count"],
    )

    by_split = Counter(row["split"] for row in metadata_rows)
    summary_by_split = [
        {"split": split, "count": by_split[split]}
        for split in ["train", "val", "test"]
    ]
    write_csv(
        output_dir / "summary_by_split.csv",
        summary_by_split,
        fieldnames=["split", "count"],
    )

    if errors:
        write_csv(
            output_dir / "errors.csv",
            errors,
            fieldnames=["zip", "inner_path", "label", "source", "error"],
        )

    print("\nDataset created successfully.")
    print(f"Output directory: {output_dir}")
    print(f"Images saved    : {len(metadata_rows)}")
    print(f"Errors          : {len(errors)}")
    print("Split breakdown :", dict(by_split))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a unified dataset for handwritten characters."
    )
    parser.add_argument(
        "--archive_zip",
        type=Path,
        required=True,
        help="Path to archive (1)(1).zip",
    )
    parser.add_argument(
        "--choice_zip",
        type=Path,
        required=True,
        help="Path to CHoiCe-Dataset-main.zip",
    )
    parser.add_argument(
        "--archive_zips",
        type=Path,
        nargs="+",
        default=[],
        help="One or more ZIPs with the archive dataset structure",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=Path("unified_dataset"),
        help="Output directory",
    )
    parser.add_argument(
        "--image_size",
        type=int,
        default=64,
        help="Final image size: image_size x image_size",
    )
    parser.add_argument("--train_ratio", type=float, default=0.80)
    parser.add_argument("--val_ratio", type=float, default=0.10)
    parser.add_argument("--test_ratio", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--choice_variant",
        choices=["data-bin", "data"],
        default="data-bin",
        help="CHoiCe variant to use. data-bin is recommended as a starting point.",
    )
    parser.add_argument(
        "--no_clean_output",
        action="store_true",
        help="Do not delete the output directory if it already exists.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_dataset(
        archive_zip_path=args.archive_zip,
        choice_zip_path=args.choice_zip,
        output_dir=args.output_dir,
        image_size=args.image_size,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
        choice_variant=args.choice_variant,
        clean_output=not args.no_clean_output,
    )
