"""
Generate labels.csv for an ImageFolder-format dataset.

Typical layout:
  selected_dataset/
    images/
      train/
        000_0/
        001_1/
        ...
      val/
      test/
    selected_classes.json

Usage:
  python generate_labels_csv_from_imagefolder.py --dataset_dir selected_dataset
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


def display_label(folder_name: str) -> str:
    if "_" in folder_name:
        prefix, suffix = folder_name.split("_", 1)
        if prefix.isdigit():
            return suffix
    return folder_name


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset_dir",
        type=Path,
        default=Path("selected_dataset"),
        help="Dataset root directory containing images/train, images/val, images/test.",
    )
    parser.add_argument(
        "--images_subdir",
        type=str,
        default="images",
        help="Sub-directory containing train/val/test splits.",
    )
    parser.add_argument(
        "--output_csv",
        type=Path,
        default=None,
        help="Output CSV path. Default: dataset_dir/labels.csv",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "val", "test"],
    )
    return parser.parse_args()


def main():
    args = parse_args()

    dataset_dir = args.dataset_dir.expanduser().resolve()
    images_dir = dataset_dir / args.images_subdir
    output_csv = args.output_csv.expanduser().resolve() if args.output_csv else dataset_dir / "labels.csv"

    if not images_dir.exists():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")

    # Class order: use selected_classes.json if available.
    selected_classes_path = dataset_dir / "selected_classes.json"
    if selected_classes_path.exists():
        labels_order = json.loads(selected_classes_path.read_text(encoding="utf-8"))
        labels_order = [str(x) for x in labels_order]
    else:
        found_labels = set()
        for split in args.splits:
            split_dir = images_dir / split
            if not split_dir.exists():
                continue
            for class_dir in split_dir.iterdir():
                if class_dir.is_dir():
                    found_labels.add(display_label(class_dir.name))
        labels_order = sorted(found_labels)

    label_to_id = {label: idx for idx, label in enumerate(labels_order)}

    rows = []

    for split in args.splits:
        split_dir = images_dir / split
        if not split_dir.exists():
            print(f"[WARN] Split not found: {split_dir}")
            continue

        for class_dir in sorted(split_dir.iterdir()):
            if not class_dir.is_dir():
                continue

            label = display_label(class_dir.name)

            if label not in label_to_id:
                label_to_id[label] = len(label_to_id)
                labels_order.append(label)

            for img_path in sorted(class_dir.rglob("*")):
                if not img_path.is_file():
                    continue
                if img_path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue

                rel_path = img_path.relative_to(dataset_dir)

                rows.append({
                    "filepath": str(rel_path),
                    "split": split,
                    "label": label,
                    "label_id": label_to_id[label],
                    "class_folder": class_dir.name,
                    "source": "selected_dataset",
                })

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["filepath", "split", "label", "label_id", "class_folder", "source"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"labels.csv created: {output_csv}")
    print(f"Number of images: {len(rows)}")
    print(f"Number of classes: {len(label_to_id)}")

    counts_by_split = {}
    for row in rows:
        counts_by_split[row["split"]] = counts_by_split.get(row["split"], 0) + 1

    for split, count in counts_by_split.items():
        print(f"  {split}: {count}")


if __name__ == "__main__":
    main()
