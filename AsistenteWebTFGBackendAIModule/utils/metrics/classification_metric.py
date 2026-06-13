from __future__ import annotations

import numpy as np
from typing import List
from utils.utils import display_label
import csv
from pathlib import Path
import matplotlib.pyplot as plt
from PIL import Image
import math




class ClassificationMetric:
    def __init__(self, name):
        self.name = name

    def compute_per_class_metrics(self, confusion: np.ndarray, classes: List[str]) -> List[dict]:
        rows = []
        n = len(classes)

        for i in range(n):
            tp = int(confusion[i, i])
            support = int(confusion[i, :].sum())
            predicted_as_i = int(confusion[:, i].sum())
            fp = predicted_as_i - tp
            fn = support - tp

            precision = tp / predicted_as_i if predicted_as_i > 0 else 0.0
            recall = tp / support if support > 0 else 0.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
            acc_class = recall

            rows.append({
                "class_index": i,
                "class_name": classes[i],
                "label": display_label(classes[i]),
                "support": support,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "class_accuracy": acc_class,
            })

        return rows
    
    
    def save_csv(self, path: Path, rows: List[dict]) -> None:
        if not rows:
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0].keys())

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


    def plot_confusion_matrix(self, confusion: np.ndarray, classes: List[str], path: Path, normalize: bool = False) -> None:
        labels = [display_label(c) for c in classes]

        if normalize:
            denom = confusion.sum(axis=1, keepdims=True)
            matrix = np.divide(confusion, denom, out=np.zeros_like(confusion, dtype=float), where=denom != 0)
            title = "Confusion matrix normalized"
        else:
            matrix = confusion
            title = "Confusion matrix raw"

        fig = plt.figure(figsize=(18, 16))
        ax = plt.gca()
        im = ax.imshow(matrix)

        ax.set_title(title)
        ax.set_xlabel("Prediction")
        ax.set_ylabel("True label")

        ax.set_xticks(np.arange(len(labels)))
        ax.set_yticks(np.arange(len(labels)))
        ax.set_xticklabels(labels, rotation=90, fontsize=7)
        ax.set_yticklabels(labels, fontsize=7)

        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)


    def plot_class_accuracy(self, per_class_rows: List[dict], path: Path) -> None:
        sorted_rows = sorted(per_class_rows, key=lambda r: r["class_accuracy"])
        labels = [r["label"] for r in sorted_rows]
        values = [r["class_accuracy"] for r in sorted_rows]

        fig = plt.figure(figsize=(18, 8))
        ax = plt.gca()
        ax.bar(range(len(labels)), values)
        ax.set_title("Class accuracy sorted from worst to best")
        ax.set_xlabel("Class")
        ax.set_ylabel("Accuracy / Recall")
        ax.set_ylim(0, 1.05)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=90, fontsize=8)
        fig.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)


    def save_misclassified_examples(
        self,
        misclassified: List[dict],
        path: Path,
        max_examples: int = 25,
    ) -> None:
        selected = misclassified[:max_examples]
        if not selected:
            return

        cols = 5
        rows = math.ceil(len(selected) / cols)

        fig = plt.figure(figsize=(cols * 3, rows * 3))

        for i, item in enumerate(selected, start=1):
            ax = fig.add_subplot(rows, cols, i)
            img = Image.open(item["path"]).convert("L")
            ax.imshow(img, cmap="gray")
            ax.axis("off")
            title = f"T:{item['true_label']} | P:{item['pred_label']}\nconf={item['confidence']:.2%}"
            ax.set_title(title, fontsize=9)

        fig.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)