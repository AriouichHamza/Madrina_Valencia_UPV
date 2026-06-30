"""
Train CNN_chiffre_new only on handwritten digit classes 0 through 9.

The source dataset may contain letters: DigitImageFolder deliberately exposes
only the folders 000_0 through 009_9. The best validation checkpoint is saved
as exammodel4_new.pt.

Example from the repository root:

  python AsistenteWebTFGBackendAIModule/Modules/train/train_CNN_chiffre_new.py \
    --dataset-root OriginalVersion/hamza/handwriting_dataset_code/unified_dataset/images \
    --epochs 40 \
    --device auto
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

from utils.Model.CNN_chiffre_new import CNN_chiffre_new


DIGIT_CLASSES = [f"{digit:03d}_{digit}" for digit in range(10)]
MODULE_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = MODULE_ROOT.parent
DEFAULT_DATASET_ROOT = (
    REPOSITORY_ROOT
    / "OriginalVersion"
    / "hamza"
    / "handwriting_dataset_code"
    / "unified_dataset"
    / "images"
)
DEFAULT_CHECKPOINT_DIR = MODULE_ROOT / "core" / "checkpoints"


class DigitImageFolder(datasets.ImageFolder):
    """ImageFolder restricted to the ten canonical digit directories."""

    def find_classes(self, directory: str):
        root = Path(directory)
        missing = [
            class_name
            for class_name in DIGIT_CLASSES
            if not (root / class_name).is_dir()
        ]
        if missing:
            raise FileNotFoundError(
                f"Missing digit directories in {root}: {', '.join(missing)}"
            )

        return DIGIT_CLASSES.copy(), {
            class_name: index
            for index, class_name in enumerate(DIGIT_CLASSES)
        }


class EnsureWhiteBackground:
    """Normalize source images to a dark digit on a white background."""

    def __call__(self, image: Image.Image) -> Image.Image:
        image = image.convert("L")
        pixels = np.asarray(image)
        border_width = max(1, min(pixels.shape) // 16)
        border = np.concatenate((
            pixels[:border_width, :].ravel(),
            pixels[-border_width:, :].ravel(),
            pixels[:, :border_width].ravel(),
            pixels[:, -border_width:].ravel(),
        ))
        if float(border.mean()) < 127.5:
            image = ImageOps.invert(image)
        return image


class RandomStrokeWidth:
    """Slightly thicken or thin handwriting while retaining the digit shape."""

    def __init__(self, probability: float = 0.20) -> None:
        self.probability = probability

    def __call__(self, image: Image.Image) -> Image.Image:
        if random.random() >= self.probability:
            return image
        if random.random() < 0.5:
            return image.filter(ImageFilter.MinFilter(3))
        return image.filter(ImageFilter.MaxFilter(3))


def invert_tensor(tensor: torch.Tensor) -> torch.Tensor:
    # Production crops are inverted before classification: black background,
    # bright handwritten digit.
    return 1.0 - tensor


def build_transforms(augment: bool):
    common_start = [
        EnsureWhiteBackground(),
        transforms.Resize((CNN_chiffre_new.image_size, CNN_chiffre_new.image_size)),
    ]
    augmentation = []
    if augment:
        augmentation = [
            transforms.RandomAffine(
                degrees=10,
                translate=(0.10, 0.10),
                scale=(0.88, 1.12),
                shear=5,
                fill=255,
            ),
            transforms.RandomApply(
                [transforms.GaussianBlur(kernel_size=3)],
                p=0.10,
            ),
            RandomStrokeWidth(probability=0.20),
        ]

    end = [
        transforms.ToTensor(),
        transforms.Lambda(invert_tensor),
        transforms.Normalize(mean=[0.5], std=[0.5]),
    ]
    train_transform = transforms.Compose(common_start + augmentation + end)
    eval_transform = transforms.Compose(common_start + end)
    return train_transform, eval_transform


def choose_device(requested: str) -> torch.device:
    requested = "cuda" if requested == "gpu" else requested
    if requested == "auto":
        requested = "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    return torch.device(requested)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def evaluate(model, loader, criterion, device):
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

    return (
        total_loss / max(total_examples, 1),
        total_correct / max(total_examples, 1),
    )


def append_history(path: Path, row: dict, write_header: bool) -> None:
    with path.open("a", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=row.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train CNN_chiffre_new on digit classes 0 through 9."
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--lr-patience", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda", "gpu"],
        default="auto",
    )
    parser.add_argument(
        "--no-augmentation",
        action="store_true",
        help="Disable training-only handwriting augmentation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)

    dataset_root = args.dataset_root.expanduser().resolve()
    checkpoint_dir = args.checkpoint_dir.expanduser().resolve()
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / "exammodel4_new.pt"
    history_path = checkpoint_dir / "training_history_CNN_chiffre_new.csv"
    if history_path.exists():
        history_path.unlink()

    train_transform, eval_transform = build_transforms(
        augment=not args.no_augmentation
    )
    train_dataset = DigitImageFolder(
        dataset_root / "train",
        transform=train_transform,
    )
    val_dataset = DigitImageFolder(
        dataset_root / "val",
        transform=eval_transform,
    )
    test_dataset = DigitImageFolder(
        dataset_root / "test",
        transform=eval_transform,
    )

    generator = torch.Generator().manual_seed(args.seed)
    loader_options = {
        "batch_size": args.batch_size,
        "num_workers": args.num_workers,
        "pin_memory": args.device in {"cuda", "gpu"},
    }
    train_loader = DataLoader(
        train_dataset,
        shuffle=True,
        generator=generator,
        **loader_options,
    )
    val_loader = DataLoader(val_dataset, shuffle=False, **loader_options)
    test_loader = DataLoader(test_dataset, shuffle=False, **loader_options)

    device = choose_device(args.device)
    model = CNN_chiffre_new().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=0.5,
        patience=args.lr_patience,
    )

    print(f"Model: CNN_chiffre_new")
    print(f"Device: {device}")
    print(f"Dataset: {dataset_root}")
    print(f"Classes: {train_dataset.classes}")
    print(
        f"Images: train={len(train_dataset)}, "
        f"val={len(val_dataset)}, test={len(test_dataset)}"
    )
    print(f"Checkpoint: {checkpoint_path}")

    best_val_accuracy = -1.0
    epochs_without_improvement = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss_sum = 0.0
        train_correct = 0
        train_examples = 0

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

            train_loss_sum += loss.item() * images.size(0)
            train_correct += (logits.argmax(dim=1) == labels).sum().item()
            train_examples += images.size(0)

        train_loss = train_loss_sum / max(train_examples, 1)
        train_accuracy = train_correct / max(train_examples, 1)
        val_loss, val_accuracy = evaluate(
            model,
            val_loader,
            criterion,
            device,
        )
        scheduler.step(val_loss)

        is_best = val_accuracy > best_val_accuracy
        if is_best:
            best_val_accuracy = val_accuracy
            epochs_without_improvement = 0
            torch.save(
                {
                    "model_name": "CNN_chiffre_new",
                    "model_state_dict": model.state_dict(),
                    "classes": train_dataset.classes,
                    "image_size": CNN_chiffre_new.image_size,
                    "input_mode": CNN_chiffre_new.input_mode,
                    "epoch": epoch,
                    "val_accuracy": val_accuracy,
                    "dataset_root": str(dataset_root),
                    "seed": args.seed,
                },
                checkpoint_path,
            )
        else:
            epochs_without_improvement += 1

        current_lr = optimizer.param_groups[0]["lr"]
        append_history(
            history_path,
            {
                "epoch": epoch,
                "train_loss": round(train_loss, 6),
                "train_accuracy": round(train_accuracy, 6),
                "val_loss": round(val_loss, 6),
                "val_accuracy": round(val_accuracy, 6),
                "best_val_accuracy": round(best_val_accuracy, 6),
                "learning_rate": current_lr,
                "is_best": int(is_best),
            },
            write_header=(epoch == 1),
        )

        print(
            f"Epoch {epoch:03d}/{args.epochs} | "
            f"train_loss={train_loss:.4f} train_acc={train_accuracy:.4f} | "
            f"val_loss={val_loss:.4f} val_acc={val_accuracy:.4f} | "
            f"best={best_val_accuracy:.4f} lr={current_lr:.2e}",
            flush=True,
        )

        if epochs_without_improvement >= args.patience:
            print(
                f"Early stopping after {args.patience} epochs without improvement."
            )
            break

    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_accuracy = evaluate(
        model,
        test_loader,
        criterion,
        device,
    )
    print(
        f"Best epoch={checkpoint['epoch']} "
        f"val_acc={checkpoint['val_accuracy']:.4f}"
    )
    print(f"Test loss={test_loss:.4f} test_acc={test_accuracy:.4f}")
    print(f"Saved checkpoint: {checkpoint_path}")
    print(f"Saved history: {history_path}")


if __name__ == "__main__":
    main()
