"""
Visualize statistics for a unified handwritten-character dataset.

Expected layout:
  unified_dataset/
    labels.csv
    images/train/...
    images/val/...
    images/test/...

Generates PNG figures and CSV/MD reports in an output directory.
Optionally plots training curves when a history CSV is provided with columns:
  epoch, train_loss, train_acc, val_loss, val_acc

Examples:
  python visualize_dataset_stats.py --dataset_dir unified_dataset

  python visualize_dataset_stats.py \
    --dataset_dir unified_dataset \
    --history_csv checkpoints/training_history.csv \
    --output_dir dataset_figures
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Iterable, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image


SPLIT_ORDER = ["train", "val", "test"]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate figures and statistics for a train/val/test dataset."
    )
    parser.add_argument(
        "--dataset_dir",
        type=Path,
        default=Path("selected_dataset"),
        help="Root directory of the unified dataset, containing labels.csv and images/.",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=Path("dataset_figures"),
        help="Directory where figures and reports will be saved.",
    )
    parser.add_argument(
        "--history_csv",
        type=Path,
        default=None,
        help="Optional: training metrics CSV with columns epoch/train_loss/train_acc/val_loss/val_acc.",
    )
    parser.add_argument(
        "--predictions_csv",
        type=Path,
        default=None,
        help="Optional: predictions CSV with true_label/pred_label columns for a confusion matrix.",
    )
    parser.add_argument(
        "--max_image_stats",
        type=int,
        default=5000,
        help="Max images to read for pixel/dimension stats. 0 = all images.",
    )
    parser.add_argument(
        "--examples_per_split",
        type=int,
        default=36,
        help="Number of example images to show per split.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling.",
    )
    return parser.parse_args()


def load_labels(dataset_dir: Path) -> pd.DataFrame:
    labels_path = dataset_dir / "labels.csv"
    if not labels_path.exists():
        raise FileNotFoundError(
            f"labels.csv not found: {labels_path}\n"
            "Run unify_handwriting_datasets*.py first."
        )

    df = pd.read_csv(labels_path)
    required = {"filepath", "split", "label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in labels.csv: {sorted(missing)}")

    df["split"] = df["split"].astype(str)
    df["label"] = df["label"].astype(str)
    df["abs_path"] = df["filepath"].apply(lambda p: str(dataset_dir / str(p)))
    df["exists"] = df["abs_path"].apply(lambda p: Path(p).exists())
    return df


def save_table_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _ordered_labels(df: pd.DataFrame) -> list[str]:
    if "label_id" in df.columns:
        tmp = df[["label", "label_id"]].drop_duplicates().copy()
        tmp["label_id"] = pd.to_numeric(tmp["label_id"], errors="coerce")
        tmp = tmp.sort_values(["label_id", "label"])
        return tmp["label"].astype(str).tolist()
    return sorted(df["label"].unique().tolist())


def _set_title_and_save(fig, title: str, output_path: Path) -> None:
    fig.suptitle(title, fontsize=14)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_split_distribution(df: pd.DataFrame, output_dir: Path) -> None:
    counts = df["split"].value_counts().reindex(SPLIT_ORDER).dropna()

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(counts.index.astype(str), counts.values)
    ax.set_xlabel("Split")
    ax.set_ylabel("Number of images")
    ax.set_title("Train / validation / test split")

    total = counts.sum()
    for bar, value in zip(bars, counts.values):
        pct = 100 * value / total if total else 0
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{int(value)}\n{pct:.1f}%",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    _set_title_and_save(fig, "Split distribution", output_dir / "01_split_distribution.png")


def plot_class_distribution(df: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    labels = _ordered_labels(df)
    pivot = (
        df.pivot_table(index="label", columns="split", values="filepath", aggfunc="count", fill_value=0)
        .reindex(labels)
        .fillna(0)
    )
    for split in SPLIT_ORDER:
        if split not in pivot.columns:
            pivot[split] = 0
    pivot = pivot[SPLIT_ORDER]
    pivot["total"] = pivot.sum(axis=1)

    pivot.to_csv(output_dir / "class_distribution.csv")

    # Figure 1: total per class.
    fig, ax = plt.subplots(figsize=(18, 6))
    ax.bar(pivot.index.astype(str), pivot["total"].values)
    ax.set_xlabel("Class")
    ax.set_ylabel("Total images")
    ax.set_title("Images per class")
    ax.tick_params(axis="x", rotation=90)
    _set_title_and_save(fig, "Total class distribution", output_dir / "02_class_distribution_total.png")

    # Figure 2: train/val/test per class as stacked bars.
    fig, ax = plt.subplots(figsize=(18, 7))
    bottom = np.zeros(len(pivot))
    for split in SPLIT_ORDER:
        values = pivot[split].values.astype(float)
        ax.bar(pivot.index.astype(str), values, bottom=bottom, label=split)
        bottom += values
    ax.set_xlabel("Class")
    ax.set_ylabel("Number of images")
    ax.set_title("Class distribution by split")
    ax.tick_params(axis="x", rotation=90)
    ax.legend()
    _set_title_and_save(fig, "Class distribution by split", output_dir / "03_class_distribution_by_split.png")

    # Figure 3: class imbalance, useful for spotting under-represented classes.
    sorted_total = pivot["total"].sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(10, 15))
    ax.barh(sorted_total.index.astype(str), sorted_total.values)
    ax.set_xlabel("Total images")
    ax.set_ylabel("Class")
    ax.set_title("Classes sorted by sample count (ascending)")
    _set_title_and_save(fig, "Class imbalance", output_dir / "04_class_imbalance_sorted.png")

    return pivot


def plot_train_val_balance(class_distribution: pd.DataFrame, output_dir: Path) -> None:
    pivot = class_distribution.copy()
    if "train" not in pivot.columns or "val" not in pivot.columns:
        return

    train = pivot["train"].replace(0, np.nan).astype(float)
    val = pivot["val"].astype(float)
    val_train_ratio = (val / train).replace([np.inf, -np.inf], np.nan)

    fig, ax = plt.subplots(figsize=(18, 6))
    ax.bar(pivot.index.astype(str), val_train_ratio.values)
    ax.axhline(val_train_ratio.median(skipna=True), linestyle="--", linewidth=1)
    ax.set_xlabel("Class")
    ax.set_ylabel("Validation / train ratio")
    ax.set_title("Validation/train balance per class")
    ax.tick_params(axis="x", rotation=90)
    _set_title_and_save(fig, "Validation/train ratio per class", output_dir / "05_val_train_ratio_by_class.png")


def plot_source_distribution(df: pd.DataFrame, output_dir: Path) -> None:
    if "source" not in df.columns:
        return

    source_counts = df["source"].value_counts()
    source_counts.to_csv(output_dir / "source_distribution.csv", header=["count"])

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(source_counts.index.astype(str), source_counts.values)
    ax.set_xlabel("Source")
    ax.set_ylabel("Number of images")
    ax.set_title("Images per dataset source")
    ax.tick_params(axis="x", rotation=30)
    _set_title_and_save(fig, "Source distribution", output_dir / "06_source_distribution.png")

    # Source per split.
    pivot = df.pivot_table(index="source", columns="split", values="filepath", aggfunc="count", fill_value=0)
    for split in SPLIT_ORDER:
        if split not in pivot.columns:
            pivot[split] = 0
    pivot = pivot[SPLIT_ORDER]
    pivot.to_csv(output_dir / "source_by_split.csv")

    fig, ax = plt.subplots(figsize=(11, 6))
    bottom = np.zeros(len(pivot))
    for split in SPLIT_ORDER:
        values = pivot[split].values.astype(float)
        ax.bar(pivot.index.astype(str), values, bottom=bottom, label=split)
        bottom += values
    ax.set_xlabel("Source")
    ax.set_ylabel("Number of images")
    ax.set_title("Image source by split")
    ax.tick_params(axis="x", rotation=30)
    ax.legend()
    _set_title_and_save(fig, "Sources by split", output_dir / "07_source_by_split.png")


def sample_image_paths(df: pd.DataFrame, max_images: int, seed: int) -> list[Path]:
    existing = df[df["exists"]].copy()
    paths = [Path(p) for p in existing["abs_path"].tolist()]
    if max_images and max_images > 0 and len(paths) > max_images:
        rng = random.Random(seed)
        paths = rng.sample(paths, max_images)
    return paths


def compute_image_stats(paths: Iterable[Path]) -> pd.DataFrame:
    rows = []
    for path in paths:
        try:
            with Image.open(path) as img:
                gray = img.convert("L")
                arr = np.asarray(gray, dtype=np.float32)
                rows.append(
                    {
                        "filepath": str(path),
                        "width": gray.width,
                        "height": gray.height,
                        "mean_pixel": float(arr.mean()),
                        "std_pixel": float(arr.std()),
                        "min_pixel": float(arr.min()),
                        "max_pixel": float(arr.max()),
                        "ink_ratio_pixels_lt_245": float((arr < 245).mean()),
                    }
                )
        except Exception as exc:
            rows.append({"filepath": str(path), "error": repr(exc)})
    return pd.DataFrame(rows)


def plot_image_stats(df: pd.DataFrame, output_dir: Path, max_images: int, seed: int) -> Optional[pd.DataFrame]:
    paths = sample_image_paths(df, max_images=max_images, seed=seed)
    if not paths:
        return None

    stats = compute_image_stats(paths)
    stats.to_csv(output_dir / "image_pixel_dimension_stats.csv", index=False)

    good = stats.dropna(subset=["width", "height", "mean_pixel", "ink_ratio_pixels_lt_245"]).copy()
    if good.empty:
        return stats

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(good["width"], bins=30, alpha=0.70, label="width")
    ax.hist(good["height"], bins=30, alpha=0.70, label="height")
    ax.set_xlabel("Pixels")
    ax.set_ylabel("Number of images")
    ax.set_title("Image dimension distribution")
    ax.legend()
    _set_title_and_save(fig, "Image dimensions", output_dir / "08_image_dimensions_distribution.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(good["mean_pixel"], bins=40)
    ax.set_xlabel("Mean pixel intensity, 0=black, 255=white")
    ax.set_ylabel("Number of images")
    ax.set_title("Mean pixel intensity distribution")
    _set_title_and_save(fig, "Mean pixel intensity", output_dir / "09_mean_pixel_distribution.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(good["ink_ratio_pixels_lt_245"], bins=40)
    ax.set_xlabel("Character pixel ratio")
    ax.set_ylabel("Number of images")
    ax.set_title("Ink ratio distribution")
    _set_title_and_save(fig, "Ink ratio", output_dir / "10_ink_ratio_distribution.png")

    return stats


def plot_random_examples(df: pd.DataFrame, output_dir: Path, examples_per_split: int, seed: int) -> None:
    rng = random.Random(seed)
    existing = df[df["exists"]].copy()

    for split in SPLIT_ORDER:
        split_df = existing[existing["split"] == split]
        if split_df.empty:
            continue

        n = min(examples_per_split, len(split_df))
        sample_df = split_df.sample(n=n, random_state=seed)

        cols = int(np.ceil(np.sqrt(n)))
        rows = int(np.ceil(n / cols))
        fig, axes = plt.subplots(rows, cols, figsize=(cols * 2.0, rows * 2.2))
        axes = np.array(axes).reshape(-1)

        for ax in axes:
            ax.axis("off")

        for ax, (_, row) in zip(axes, sample_df.iterrows()):
            path = Path(row["abs_path"])
            try:
                with Image.open(path) as img:
                    ax.imshow(img.convert("L"), cmap="gray")
                ax.set_title(f"{row['label']}", fontsize=11)
            except Exception:
                ax.set_title("error", fontsize=9)
            ax.axis("off")

        _set_title_and_save(fig, f"Random examples — {split}", output_dir / f"11_examples_{split}.png")


def plot_training_history(history_csv: Path, output_dir: Path) -> None:
    if history_csv is None:
        return
    if not history_csv.exists():
        print(f"[WARN] history_csv not found: {history_csv}")
        return

    hist = pd.read_csv(history_csv)
    required_any = {"epoch"}
    if not required_any.issubset(hist.columns):
        print(f"[WARN] history_csv must contain at least the 'epoch' column: {history_csv}")
        return

    hist.to_csv(output_dir / "training_history_copy.csv", index=False)

    # Loss curve.
    loss_cols = [c for c in ["train_loss", "val_loss", "test_loss"] if c in hist.columns]
    if loss_cols:
        fig, ax = plt.subplots(figsize=(9, 5))
        for col in loss_cols:
            ax.plot(hist["epoch"], hist[col], marker="o", label=col)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Loss")
        ax.set_title("Loss curves")
        ax.legend()
        ax.grid(True, alpha=0.3)
        _set_title_and_save(fig, "Training loss", output_dir / "12_training_loss_curves.png")

    # Accuracy curve.
    acc_cols = [c for c in ["train_acc", "val_acc", "test_acc"] if c in hist.columns]
    if acc_cols:
        fig, ax = plt.subplots(figsize=(9, 5))
        for col in acc_cols:
            ax.plot(hist["epoch"], hist[col], marker="o", label=col)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Accuracy")
        ax.set_title("Accuracy curves")
        ax.set_ylim(0, 1.0)
        ax.legend()
        ax.grid(True, alpha=0.3)
        _set_title_and_save(fig, "Training accuracy", output_dir / "13_training_accuracy_curves.png")

    if {"train_acc", "val_acc"}.issubset(hist.columns):
        gap = hist["train_acc"] - hist["val_acc"]
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(hist["epoch"], gap, marker="o")
        ax.axhline(0, linestyle="--", linewidth=1)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("train_acc - val_acc")
        ax.set_title("Train/validation gap (overfitting indicator)")
        ax.grid(True, alpha=0.3)
        _set_title_and_save(fig, "Train-validation gap", output_dir / "14_train_val_accuracy_gap.png")


def plot_confusion_matrix(predictions_csv: Path, output_dir: Path) -> None:
    if predictions_csv is None:
        return
    if not predictions_csv.exists():
        print(f"[WARN] predictions_csv not found: {predictions_csv}")
        return

    pred = pd.read_csv(predictions_csv)
    true_col = None
    pred_col = None
    for candidate in ["true_label", "label", "target", "y_true"]:
        if candidate in pred.columns:
            true_col = candidate
            break
    for candidate in ["pred_label", "prediction", "pred", "y_pred"]:
        if candidate in pred.columns:
            pred_col = candidate
            break

    if true_col is None or pred_col is None:
        print(
            "[WARN] predictions_csv must contain a true_label/label/y_true column "
            "and a pred_label/prediction/y_pred column."
        )
        return

    labels = sorted(set(pred[true_col].astype(str)).union(set(pred[pred_col].astype(str))))
    matrix = pd.crosstab(
        pred[true_col].astype(str),
        pred[pred_col].astype(str),
        rownames=["true"],
        colnames=["pred"],
        dropna=False,
    ).reindex(index=labels, columns=labels, fill_value=0)
    matrix.to_csv(output_dir / "confusion_matrix.csv")

    fig_size = max(8, len(labels) * 0.28)
    fig, ax = plt.subplots(figsize=(fig_size, fig_size))
    im = ax.imshow(matrix.values, interpolation="nearest")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_yticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Prediction")
    ax.set_ylabel("Ground truth")
    ax.set_title("Confusion matrix")
    _set_title_and_save(fig, "Confusion matrix", output_dir / "15_confusion_matrix.png")


def write_markdown_report(
    df: pd.DataFrame,
    class_distribution: pd.DataFrame,
    image_stats: Optional[pd.DataFrame],
    output_dir: Path,
) -> None:
    total = len(df)
    existing = int(df["exists"].sum()) if "exists" in df.columns else total
    missing = total - existing
    split_counts = df["split"].value_counts().to_dict()

    totals = class_distribution["total"] if "total" in class_distribution.columns else class_distribution.sum(axis=1)
    min_class = totals.idxmin() if len(totals) else None
    max_class = totals.idxmax() if len(totals) else None
    min_count = int(totals.min()) if len(totals) else 0
    max_count = int(totals.max()) if len(totals) else 0
    imbalance_ratio = (max_count / min_count) if min_count > 0 else float("inf")

    lines = []
    lines.append("# Dataset statistics report\n")
    lines.append(f"- Total entries in labels.csv: **{total}**")
    lines.append(f"- Images found on disk: **{existing}**")
    lines.append(f"- Missing images: **{missing}**")
    lines.append(f"- Number of classes: **{len(totals)}**")
    lines.append("\n## Split distribution\n")
    for split in SPLIT_ORDER:
        count = int(split_counts.get(split, 0))
        pct = 100 * count / total if total else 0
        lines.append(f"- {split}: **{count}** images ({pct:.2f}%)")

    lines.append("\n## Class balance\n")
    lines.append(f"- Least-represented class: **{min_class}** with **{min_count}** images")
    lines.append(f"- Most-represented class: **{max_class}** with **{max_count}** images")
    lines.append(f"- Max/min ratio: **{imbalance_ratio:.2f}**")

    if image_stats is not None and not image_stats.empty and "mean_pixel" in image_stats.columns:
        good = image_stats.dropna(subset=["mean_pixel"]).copy()
        if not good.empty:
            lines.append("\n## Sampled image statistics\n")
            lines.append(f"- Images analysed: **{len(good)}**")
            lines.append(f"- Mean width: **{good['width'].mean():.2f}px**")
            lines.append(f"- Mean height: **{good['height'].mean():.2f}px**")
            lines.append(f"- Mean pixel intensity: **{good['mean_pixel'].mean():.2f}**")
            lines.append(f"- Mean ink ratio: **{good['ink_ratio_pixels_lt_245'].mean():.4f}**")

    lines.append("\n## Generated figures\n")
    for png in sorted(output_dir.glob("*.png")):
        lines.append(f"- `{png.name}`")

    (output_dir / "dataset_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    dataset_dir = args.dataset_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Dataset : {dataset_dir}")
    print(f"Output  : {output_dir}")

    df = load_labels(dataset_dir)
    df.to_csv(output_dir / "labels_with_exists.csv", index=False)

    missing_count = int((~df["exists"]).sum())
    if missing_count:
        print(f"[WARN] {missing_count} images listed in labels.csv are not found on disk.")

    plot_split_distribution(df, output_dir)
    class_distribution = plot_class_distribution(df, output_dir)
    plot_train_val_balance(class_distribution, output_dir)
    plot_source_distribution(df, output_dir)
    image_stats = plot_image_stats(df, output_dir, args.max_image_stats, args.seed)
    plot_random_examples(df, output_dir, args.examples_per_split, args.seed)

    if args.history_csv is not None:
        plot_training_history(args.history_csv.expanduser().resolve(), output_dir)
    else:
        print("[INFO] No --history_csv provided: loss/accuracy curves will not be generated.")

    if args.predictions_csv is not None:
        plot_confusion_matrix(args.predictions_csv.expanduser().resolve(), output_dir)

    write_markdown_report(df, class_distribution, image_stats, output_dir)

    print("\nDone. Figures saved to:")
    print(output_dir)
    print("Report  :", output_dir / "dataset_report.md")


if __name__ == "__main__":
    main()
