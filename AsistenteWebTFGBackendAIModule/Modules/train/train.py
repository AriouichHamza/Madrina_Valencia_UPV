"""
Train a robust CNN for handwriting recognition.

Features:
- train on selected_dataset/images
- save a separate best-model checkpoint
- realistic augmentation: rotation, translation, zoom, blur, low-resolution, random inversion
- WeightedRandomSampler for class balancing
- weight_decay, ReduceLROnPlateau scheduler, and early stopping

Example:
  python train.py \
    --dataset_root selected_dataset0/images \
    --checkpoint_dir checkpoints_selected_new0 \
    --epochs 100 \
    --batch_size 64 \
    --device cuda \
    --augment_real_like \
    --weighted_sampler
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets

from utils.Model.smallCNN import SmallCNN
from utils.traitement.training_random_traitement import build_transforms    
from utils.utils import choose_device, make_weighted_sampler, evaluate, write_history_row




#Utils Functions

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a robust CNN for handwriting recognition.")
    parser.add_argument("--dataset_root", type=Path, default=Path("selected_dataset/images"))
    parser.add_argument("--checkpoint_dir", type=Path, default=Path("checkpoints_selected"))
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight_decay", type=float, default=1e-4)
    parser.add_argument("--num_workers", type=int, default=2)
    parser.add_argument("--image_size", type=int, default=64)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "gpu"], default="auto")
    parser.add_argument("--augment_real_like", action="store_true")
    parser.add_argument("--weighted_sampler", action="store_true")
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--lr_patience", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    dataset_root = args.dataset_root.expanduser().resolve()
    checkpoint_dir = args.checkpoint_dir.expanduser().resolve()
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    history_path = checkpoint_dir / "training_history.csv"
    best_model_path = checkpoint_dir / "best_model.pt"

    if history_path.exists():
        history_path.unlink()

    train_transform, eval_transform = build_transforms(args.image_size, args.augment_real_like)

    train_dataset = datasets.ImageFolder(dataset_root / "train", transform=train_transform)
    val_dataset = datasets.ImageFolder(dataset_root / "val", transform=eval_transform)
    test_dataset = datasets.ImageFolder(dataset_root / "test", transform=eval_transform)

    if args.weighted_sampler:
        sampler = make_weighted_sampler(train_dataset)
        train_loader = DataLoader(
            train_dataset,
            batch_size=args.batch_size,
            sampler=sampler,
            num_workers=args.num_workers,
        )
    else:
        train_loader = DataLoader(
            train_dataset,
            batch_size=args.batch_size,
            shuffle=True,
            num_workers=args.num_workers,
        )

    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)

    device = choose_device(args.device)

    print("Using device:", device)
    print("Dataset root:", dataset_root)
    print("Checkpoint dir:", checkpoint_dir)
    print("Classes:", len(train_dataset.classes))
    print("Class names:", [c.split('_', 1)[1] if '_' in c else c for c in train_dataset.classes])
    print("Train images:", len(train_dataset))
    print("Val images:", len(val_dataset))
    print("Test images:", len(test_dataset))
    print("Augment real-like:", args.augment_real_like)
    print("Weighted sampler:", args.weighted_sampler)

    model = SmallCNN(num_classes=len(train_dataset.classes)).to(device)
    criterion = nn.CrossEntropyLoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=args.lr,
        weight_decay=args.weight_decay,
    )

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=0.5,
        patience=args.lr_patience,
    )

    best_val_acc = -1.0
    epochs_without_improvement = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_examples = 0

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * images.size(0)
            train_correct += (logits.argmax(dim=1) == labels).sum().item()
            train_examples += images.size(0)

        train_loss = train_loss / max(train_examples, 1)
        train_acc = train_correct / max(train_examples, 1)

        val_loss, val_acc = evaluate(model, val_loader, criterion, device)
        scheduler.step(val_loss)

        current_lr = optimizer.param_groups[0]["lr"]
        is_best = val_acc > best_val_acc

        if is_best:
            best_val_acc = val_acc
            epochs_without_improvement = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "classes": train_dataset.classes,
                    "val_acc": val_acc,
                    "epoch": epoch,
                    "image_size": args.image_size,
                    "dataset_root": str(dataset_root),
                },
                best_model_path,
            )
        else:
            epochs_without_improvement += 1

        row = {
            "epoch": epoch,
            "train_loss": round(train_loss, 6),
            "train_acc": round(train_acc, 6),
            "val_loss": round(val_loss, 6),
            "val_acc": round(val_acc, 6),
            "best_val_acc": round(best_val_acc, 6),
            "lr": current_lr,
            "is_best": int(is_best),
        }
        write_history_row(history_path, row, write_header=(epoch == 1))

        print(
            f"Epoch {epoch:03d}/{args.epochs} | "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} | "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f} | "
            f"best_val_acc={best_val_acc:.4f} | "
            f"lr={current_lr:.2e}"
        )

        if epochs_without_improvement >= args.patience:
            print(f"Early stopping: no improvement for {args.patience} epochs.")
            break

    checkpoint = torch.load(best_model_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_acc = evaluate(model, test_loader, criterion, device)

    print()
    print(f"Best epoch={checkpoint.get('epoch')} | best val_acc={checkpoint['val_acc']:.4f}")
    print(f"Test loss={test_loss:.4f} | test_acc={test_acc:.4f}")
    print("Best model:", best_model_path)
    print("History:", history_path)


if __name__ == "__main__":
    main()



