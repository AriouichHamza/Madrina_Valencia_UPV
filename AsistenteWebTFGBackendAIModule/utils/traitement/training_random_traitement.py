from __future__ import annotations

import random
from PIL import Image, ImageOps, ImageFilter
from torchvision import transforms



class RandomInvertPIL:
    def __init__(self, p: float = 0.35):
        self.p = p

    def __call__(self, img: Image.Image) -> Image.Image:
        if random.random() < self.p:
            return ImageOps.invert(img.convert("L"))
        return img


class RandomLowResolution:
    """
    Simule les images réelles de type 28x28, puis les remet en 64x64.
    Ça aide le modèle à mieux généraliser sur les images pixelisées.
    """
    def __init__(self, p: float = 0.50, min_size: int = 24, max_size: int = 40, final_size: int = 64):
        self.p = p
        self.min_size = min_size
        self.max_size = max_size
        self.final_size = final_size

    def __call__(self, img: Image.Image) -> Image.Image:
        if random.random() >= self.p:
            return img

        img = img.convert("L")
        s = random.randint(self.min_size, self.max_size)
        img = img.resize((s, s), Image.Resampling.BILINEAR)
        img = img.resize((self.final_size, self.final_size), Image.Resampling.BILINEAR)
        return img


class RandomStrokeFilter:
    """
    Épaissit ou affine légèrement les traits.
    Pour fond blanc + caractère noir :
      MinFilter épaissit le noir
      MaxFilter affine le noir
    """
    def __init__(self, p: float = 0.20):
        self.p = p

    def __call__(self, img: Image.Image) -> Image.Image:
        if random.random() >= self.p:
            return img

        img = img.convert("L")
        if random.random() < 0.5:
            return img.filter(ImageFilter.MinFilter(3))
        return img.filter(ImageFilter.MaxFilter(3))
  
  
  
  
# Ces transformations sont utilisées dans train_cnn_domain_robust.py et train_cnn_with_metrics.py  
def build_transforms(image_size: int, augment_real_like: bool):
    if augment_real_like:
        train_transform = transforms.Compose([
            transforms.Grayscale(num_output_channels=1),
            transforms.Resize((image_size, image_size)),
            transforms.RandomAffine(
                degrees=12,
                translate=(0.12, 0.12),
                scale=(0.85, 1.18),
                shear=8,
                fill=255,
            ),
            RandomLowResolution(p=0.50, min_size=24, max_size=40, final_size=image_size),
            transforms.RandomApply([transforms.GaussianBlur(kernel_size=3)], p=0.15),
            RandomStrokeFilter(p=0.20),
            RandomInvertPIL(p=0.25),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5], std=[0.5]),
        ])
    else:
        train_transform = transforms.Compose([
            transforms.Grayscale(num_output_channels=1),
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5], std=[0.5]),
        ])

    eval_transform = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5]),
    ])

    return train_transform, eval_transform