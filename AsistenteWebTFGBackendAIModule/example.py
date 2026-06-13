"""
Run a trained CNN on handwritten character images.

Example:
  python example.py \
    --checkpoint checkpoints/best_model.pt \
    --images test_images/*.png \
    --device auto

Applies the same preprocessing pipeline as unify_handwriting_datasets.py:
  - grayscale
  - invert if background is dark
  - autocontrast
  - crop around the character
  - square padding
  - resize to 64x64
  - normalize mean=0.5, std=0.5
"""

from __future__ import annotations

import argparse
from pathlib import Path

from utils.utils import load_model, resolve_images, choose_device, save_csv, save_preprocessed_images, print_results, preprocess_image , make_prediction_rows 






def main():
    parser = argparse.ArgumentParser(description="Run a trained CNN on handwritten character images.")
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/best_model1.pt"), help="Path to best_model.pt")
    parser.add_argument("--images", nargs="+", required=True, help="Image paths or glob patterns, e.g. test_images/*.png")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "gpu"], default="auto", help="Device: auto, cpu, cuda, or gpu")
    parser.add_argument("--image_size", type=int, default=64, help="Image size used during training")
    parser.add_argument("--topk", type=int, default=3, help="Number of top predictions to display")
    parser.add_argument("--output_csv", type=Path, default=None, help="Optional: save predictions to a CSV file")
    parser.add_argument("--save_preprocessed_dir", type=Path, default=None, help="Optional: save preprocessed images to a directory")
    args = parser.parse_args()

    if not args.checkpoint.exists():
        raise FileNotFoundError(f"Checkpoint not found: {args.checkpoint}")

    image_paths = resolve_images(args.images)
    if not image_paths:
        raise FileNotFoundError("No valid images found.")

    device = choose_device(args.device)
    print(f"Using device: {device}")

    model, classes = load_model(args.checkpoint, device)
    rows = make_prediction_rows(model, classes, image_paths, device, args.image_size, args.topk)
    print_results(rows)

    if args.output_csv is not None:
        save_csv(rows, args.output_csv)
        print(f"CSV saved: {args.output_csv}")

    if args.save_preprocessed_dir is not None:
        save_preprocessed_images(image_paths, args.save_preprocessed_dir, args.image_size)
        print(f"Preprocessed images saved to: {args.save_preprocessed_dir}")


if __name__ == "__main__":
    main()