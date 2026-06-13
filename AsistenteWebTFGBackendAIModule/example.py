"""
Tester un modèle CNN entraîné sur le dataset unifié de caractères manuscrits.

Exemple :
  python example.py \
    --checkpoint checkpoints/best_model.pt \
    --images test_images/*.png \
    --device auto

Le script applique le même preprocessing que unify_handwriting_datasets.py :
  - grayscale
  - inversion si fond noir
  - autocontrast
  - crop autour du caractère
  - padding carré
  - resize 64x64
  - normalisation mean=0.5, std=0.5
"""

from __future__ import annotations

import argparse
from pathlib import Path

from utils.utils import load_model, resolve_images, choose_device, save_csv, save_preprocessed_images, print_results, preprocess_image , make_prediction_rows 






def main():
    parser = argparse.ArgumentParser(description="Tester un modèle CNN sur des images manuscrites.")
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/best_model1.pt"), help="Chemin vers best_model.pt")
    parser.add_argument("--images", nargs="+", required=True, help="Images ou patterns glob, exemple: test_images/*.png")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "gpu"], default="auto", help="auto, cpu, cuda/gpu")
    parser.add_argument("--image_size", type=int, default=64, help="Taille d'image utilisée à l'entraînement")
    parser.add_argument("--topk", type=int, default=3, help="Nombre de prédictions affichées")
    parser.add_argument("--output_csv", type=Path, default=None, help="Optionnel: sauver les prédictions dans un CSV")
    parser.add_argument("--save_preprocessed_dir", type=Path, default=None, help="Optionnel: sauver les images après preprocessing")
    args = parser.parse_args()

    if not args.checkpoint.exists():
        raise FileNotFoundError(f"Checkpoint introuvable: {args.checkpoint}")

    image_paths = resolve_images(args.images)
    if not image_paths:
        raise FileNotFoundError("Aucune image valide trouvée.")

    device = choose_device(args.device)
    print(f"Using device: {device}")

    model, classes = load_model(args.checkpoint, device)
    rows = make_prediction_rows(model, classes, image_paths, device, args.image_size, args.topk)
    print_results(rows)

    if args.output_csv is not None:
        save_csv(rows, args.output_csv)
        print(f"CSV sauvegardé: {args.output_csv}")

    if args.save_preprocessed_dir is not None:
        save_preprocessed_images(image_paths, args.save_preprocessed_dir, args.image_size)
        print(f"Images prétraitées sauvegardées dans: {args.save_preprocessed_dir}")


if __name__ == "__main__":
    main()