"""
Evaluate a CNN model on train/val/test splits and generate metrics and figures.

Example:
  python test.py \
    --checkpoint checkpoints/best_model.pt \
    --dataset_root unified_dataset/images \
    --split val \
    --device cuda \
    --output_dir evaluation_val

Outputs:
  evaluation_val/
    metrics_summary.txt
    per_class_metrics.csv
    predictions.csv
    confusion_matrix_raw.png
    confusion_matrix_normalized.png
    class_accuracy_sorted.png
    misclassified_examples.png
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import numpy as np

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

from utils.metrics.classification_metric import ClassificationMetric
from utils.Model.smallCNN import SmallCNN
from utils.utils import choose_device, display_label



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the handwriting CNN model.")
    parser.add_argument("--checkpoint", type=Path, required=True, help="Path to checkpoints/best_model.pt")
    parser.add_argument("--dataset_root", type=Path, default=Path("unified_dataset/images"))
    parser.add_argument("--split", choices=["train", "val", "test"], default="val")
    parser.add_argument("--output_dir", type=Path, default=Path("evaluation_results"))
    parser.add_argument("--batch_size", type=int, default=128)
    parser.add_argument("--num_workers", type=int, default=2)
    parser.add_argument("--image_size", type=int, default=64)
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "gpu"], default="auto")
    parser.add_argument("--max_misclassified", type=int, default=25)
    return parser.parse_args()

def load_model(checkpoint_path: Path, device: torch.device, dataset_classes: List[str]) -> Tuple[nn.Module, List[str]]:
    checkpoint = torch.load(checkpoint_path, map_location="cpu")

    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
        classes = list(checkpoint.get("classes", dataset_classes))
    else:
        # Fallback for checkpoints saved with torch.save(model.state_dict(), path) directly.
        state_dict = checkpoint
        classes = dataset_classes

    model = SmallCNN(num_classes=len(classes))
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()

    return model, classes



classificationMetric = ClassificationMetric("handwriting_evaluation")

def main() -> None:
    args = parse_args()

    dataset_root = args.dataset_root.expanduser().resolve()
    split_dir = dataset_root / args.split
    checkpoint_path = args.checkpoint.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not split_dir.exists():
        raise FileNotFoundError(f"Split directory not found: {split_dir}")

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    transform = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((args.image_size, args.image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5]),
    ])

    dataset = datasets.ImageFolder(split_dir, transform=transform)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
    )

    device = choose_device(args.device)
    print("Using device:", device)
    print("Dataset split:", args.split)
    print("Images:", len(dataset))
    print("Classes dataset:", len(dataset.classes))

    model, checkpoint_classes = load_model(checkpoint_path, device, dataset.classes)

    if checkpoint_classes != dataset.classes:
        print("[WARN] Checkpoint classes differ from dataset classes.")
        print("       Continuing — verify that the class order is correct.")

    classes = checkpoint_classes
    num_classes = len(classes)

    criterion = nn.CrossEntropyLoss()

    y_true: List[int] = []
    y_pred: List[int] = []
    prediction_rows: List[dict] = []
    total_loss = 0.0
    total_examples = 0

    # dataset.samples preserves the same order as the DataLoader when shuffle=False.
    all_paths = [Path(p) for p, _ in dataset.samples]
    path_cursor = 0

    with torch.no_grad():
        for images, labels in loader:
            batch_paths = all_paths[path_cursor:path_cursor + images.size(0)]
            path_cursor += images.size(0)

            images = images.to(device)
            labels = labels.to(device)

            logits = model(images)
            loss = criterion(logits, labels)
            probs = torch.softmax(logits, dim=1)
            preds = probs.argmax(dim=1)

            total_loss += loss.item() * images.size(0)
            total_examples += images.size(0)

            topk = min(args.topk, num_classes)
            top_values, top_indices = torch.topk(probs, k=topk, dim=1)

            labels_cpu = labels.cpu().numpy().tolist()
            preds_cpu = preds.cpu().numpy().tolist()

            y_true.extend(labels_cpu)
            y_pred.extend(preds_cpu)

            for j in range(images.size(0)):
                true_idx = int(labels_cpu[j])
                pred_idx = int(preds_cpu[j])
                confidence = float(probs[j, pred_idx].cpu().item())

                top_items = []
                for prob, idx in zip(top_values[j].cpu().tolist(), top_indices[j].cpu().tolist()):
                    idx = int(idx)
                    top_items.append(f"{display_label(classes[idx])}={prob:.4f}")

                prediction_rows.append({
                    "path": str(batch_paths[j]),
                    "true_index": true_idx,
                    "true_class": classes[true_idx],
                    "true_label": display_label(classes[true_idx]),
                    "pred_index": pred_idx,
                    "pred_class": classes[pred_idx],
                    "pred_label": display_label(classes[pred_idx]),
                    "confidence": confidence,
                    "correct": int(true_idx == pred_idx),
                    "top_predictions": ", ".join(top_items),
                })

    confusion = np.zeros((num_classes, num_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        confusion[t, p] += 1

    total_correct = int(np.trace(confusion))
    accuracy = total_correct / total_examples if total_examples > 0 else 0.0
    avg_loss = total_loss / total_examples if total_examples > 0 else 0.0

    per_class_rows = classificationMetric.compute_per_class_metrics(confusion, classes)

    macro_precision = float(np.mean([r["precision"] for r in per_class_rows]))
    macro_recall = float(np.mean([r["recall"] for r in per_class_rows]))
    macro_f1 = float(np.mean([r["f1"] for r in per_class_rows]))

    supports = np.array([r["support"] for r in per_class_rows], dtype=float)
    total_support = supports.sum()
    if total_support > 0:
        weighted_precision = float(np.sum([r["precision"] * r["support"] for r in per_class_rows]) / total_support)
        weighted_recall = float(np.sum([r["recall"] * r["support"] for r in per_class_rows]) / total_support)
        weighted_f1 = float(np.sum([r["f1"] * r["support"] for r in per_class_rows]) / total_support)
    else:
        weighted_precision = weighted_recall = weighted_f1 = 0.0

    classificationMetric.save_csv(output_dir / "predictions.csv", prediction_rows)
    classificationMetric.save_csv(output_dir / "per_class_metrics.csv", per_class_rows)

    # Lowest-performing classes.
    worst_rows = sorted(per_class_rows, key=lambda r: r["class_accuracy"])[:15]
    classificationMetric.save_csv(output_dir / "worst_classes.csv", worst_rows)

    classificationMetric.plot_confusion_matrix(confusion, classes, output_dir / "confusion_matrix_raw.png", normalize=False)
    classificationMetric.plot_confusion_matrix(confusion, classes, output_dir / "confusion_matrix_normalized.png", normalize=True)
    classificationMetric.plot_class_accuracy(per_class_rows, output_dir / "class_accuracy_sorted.png")

    misclassified = [r for r in prediction_rows if r["correct"] == 0]
    classificationMetric.save_misclassified_examples(
        misclassified,
        output_dir / "misclassified_examples.png",
        max_examples=args.max_misclassified,
    )

    summary = f"""Evaluation summary
==================

Checkpoint: {checkpoint_path}
Dataset root: {dataset_root}
Split: {args.split}
Images: {total_examples}
Classes: {num_classes}

Loss: {avg_loss:.6f}
Accuracy: {accuracy:.6f}

Macro precision: {macro_precision:.6f}
Macro recall / balanced accuracy: {macro_recall:.6f}
Macro F1: {macro_f1:.6f}

Weighted precision: {weighted_precision:.6f}
Weighted recall: {weighted_recall:.6f}
Weighted F1: {weighted_f1:.6f}

Correct predictions: {total_correct}
Wrong predictions: {total_examples - total_correct}

Worst classes:
"""

    for r in worst_rows:
        summary += (
            f"- {r['label']} | support={r['support']} | "
            f"acc={r['class_accuracy']:.4f} | precision={r['precision']:.4f} | f1={r['f1']:.4f}\n"
        )

    (output_dir / "metrics_summary.txt").write_text(summary, encoding="utf-8")

    print()
    print(summary)
    print("Output files written to:", output_dir)
    print("- metrics_summary.txt")
    print("- per_class_metrics.csv")
    print("- predictions.csv")
    print("- confusion_matrix_raw.png")
    print("- confusion_matrix_normalized.png")
    print("- class_accuracy_sorted.png")
    if misclassified:
        print("- misclassified_examples.png")


if __name__ == "__main__":
    main()
