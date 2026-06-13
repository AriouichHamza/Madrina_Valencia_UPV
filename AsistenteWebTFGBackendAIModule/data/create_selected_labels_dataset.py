"""
Créer un dataset filtré avec seulement certains labels.

Exemple :
  python create_selected_labels_dataset.py \
    --input_dataset unified_dataset/images \
    --output_dataset selected_dataset/images \
    --labels 0 1 2 3 4 5 6 7 8 9 T R W A G M Y F P D X B N J Z S Q V H L C K E \
    --mode copy

Le script accepte les noms de dossiers de type :
  000_0, 001_1, 036_A
ou directement :
  0, 1, A, B, ...
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, List


DEFAULT_LABELS = [
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "T", "R", "W", "A", "G", "M", "Y", "F", "P", "D", "X",
    "B", "N", "J", "Z", "S", "Q", "V", "H", "L", "C", "K", "E",
]


def display_label(folder_name: str) -> str:
    if "_" in folder_name:
        prefix, suffix = folder_name.split("_", 1)
        if prefix.isdigit():
            return suffix
    return folder_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filtrer un dataset ImageFolder pour ne garder que certains labels."
    )
    parser.add_argument("--input_dataset", type=Path, default=Path("unified_dataset/images"))
    parser.add_argument("--output_dataset", type=Path, default=Path("selected_dataset/images"))
    parser.add_argument("--labels", nargs="+", default=DEFAULT_LABELS)
    parser.add_argument("--splits", nargs="+", default=["train", "val", "test"])
    parser.add_argument("--mode", choices=["copy", "symlink"], default="copy")
    parser.add_argument("--clean_output", action="store_true")
    return parser.parse_args()


def find_matching_class_dirs(split_dir: Path, wanted_labels: List[str]) -> Dict[str, Path]:
    wanted_set = set(wanted_labels)
    matches: Dict[str, Path] = {}

    if not split_dir.exists():
        raise FileNotFoundError(f"Split introuvable : {split_dir}")

    for class_dir in sorted(split_dir.iterdir()):
        if not class_dir.is_dir():
            continue

        label = display_label(class_dir.name)

        if label in wanted_set:
            if label in matches:
                raise RuntimeError(
                    f"Deux dossiers correspondent au même label '{label}' dans {split_dir}: "
                    f"{matches[label]} et {class_dir}"
                )
            matches[label] = class_dir

    return matches


def safe_copy_or_link(src: Path, dst: Path, mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        return

    if mode == "symlink":
        dst.symlink_to(src.resolve())
    else:
        shutil.copy2(src, dst)


def copy_split(
    input_split_dir: Path,
    output_split_dir: Path,
    wanted_labels: List[str],
    global_class_names: Dict[str, str],
    mode: str,
) -> Dict[str, int]:
    matches = find_matching_class_dirs(input_split_dir, wanted_labels)
    counts = {label: 0 for label in wanted_labels}

    missing = [label for label in wanted_labels if label not in matches]
    if missing:
        print(f"[WARN] Labels absents dans {input_split_dir}: {missing}")

    image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}

    for label in wanted_labels:
        src_class_dir = matches.get(label)
        if src_class_dir is None:
            continue

        class_folder_name = global_class_names[label]
        dst_class_dir = output_split_dir / class_folder_name
        dst_class_dir.mkdir(parents=True, exist_ok=True)

        for src_img in sorted(src_class_dir.rglob("*")):
            if not src_img.is_file():
                continue
            if src_img.suffix.lower() not in image_exts:
                continue

            dst_img = dst_class_dir / src_img.name
            if dst_img.exists():
                stem = src_img.stem
                suffix = src_img.suffix
                k = 1
                while True:
                    candidate = dst_class_dir / f"{stem}_{k}{suffix}"
                    if not candidate.exists():
                        dst_img = candidate
                        break
                    k += 1

            safe_copy_or_link(src_img, dst_img, mode)
            counts[label] += 1

    return counts


def main() -> None:
    args = parse_args()

    input_dataset = args.input_dataset.expanduser().resolve()
    output_dataset = args.output_dataset.expanduser().resolve()
    wanted_labels = [str(x) for x in args.labels]

    print("Input dataset :", input_dataset)
    print("Output dataset:", output_dataset)
    print("Labels gardés :", wanted_labels)
    print("Nombre de classes:", len(wanted_labels))
    print("Mode:", args.mode)

    if args.clean_output and output_dataset.exists():
        print(f"Suppression de l'ancien output: {output_dataset}")
        shutil.rmtree(output_dataset)

    if not input_dataset.exists():
        raise FileNotFoundError(f"Input dataset introuvable : {input_dataset}")

    train_dir = input_dataset / "train"
    train_matches = find_matching_class_dirs(train_dir, wanted_labels)

    missing_train = [label for label in wanted_labels if label not in train_matches]
    if missing_train:
        raise RuntimeError(
            "Certains labels sont absents du train set : " + ", ".join(missing_train)
        )

    global_class_names = {
        label: train_matches[label].name
        for label in wanted_labels
    }

    all_counts = {}

    for split in args.splits:
        input_split_dir = input_dataset / split
        output_split_dir = output_dataset / split

        print(f"\nTraitement split: {split}")
        counts = copy_split(
            input_split_dir=input_split_dir,
            output_split_dir=output_split_dir,
            wanted_labels=wanted_labels,
            global_class_names=global_class_names,
            mode=args.mode,
        )

        all_counts[split] = counts

        total_split = sum(counts.values())
        print(f"Total {split}: {total_split} images")
        for label in wanted_labels:
            print(f"  {label}: {counts[label]}")

    metadata = {
        "input_dataset": str(input_dataset),
        "output_dataset": str(output_dataset),
        "labels": wanted_labels,
        "num_classes": len(wanted_labels),
        "class_folder_names": global_class_names,
        "counts": all_counts,
    }

    metadata_path = output_dataset.parent / "selected_labels_metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    classes_path = output_dataset.parent / "selected_classes.json"
    classes_path.write_text(json.dumps(wanted_labels, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nDataset filtré créé avec succès.")
    print("Images:", output_dataset)
    print("Metadata:", metadata_path)
    print("Classes:", classes_path)
    print("\nPour entraîner :")
    print(f"  python train_cnn_with_metrics.py --dataset_root {output_dataset} --epochs 100 --device cuda")


if __name__ == "__main__":
    main()
