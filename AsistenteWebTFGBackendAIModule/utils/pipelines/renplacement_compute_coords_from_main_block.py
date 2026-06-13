from __future__ import annotations


from utils.traitement.pdf_traitement import build_dump_path
from utils.traitement.imageProcessing import detect_dni_chain_on_page
from utils.pipelines.remplacement_bascar_inicio_copias import _coords_from_digit_boxes, _synthetic_boxes_from_anchor
import os
import cv2 as cv
from PIL import Image





# --------------------------------------------------------
# Replaces compute_coords_from_main_block()
# --------------------------------------------------------
def compute_coords_from_main_block(j, coordsDNI, ListNumFirstPage):
    page_number = ListNumFirstPage[j - 1]

    # 1) strict detection first
    detection = detect_dni_chain_on_page(page_number, mode="coords_detect")

    # 2) permissive fallback
    if detection is None:
        detection = detect_dni_chain_on_page(page_number, mode="page_detect")

    pathToDniPage = build_dump_path("DNIpage", page_number)

    # Save the inverted image for OCR if it does not exist yet.
    if detection is not None and not os.path.exists(pathToDniPage):
        Image.fromarray(detection["gray_for_ocr"]).save(pathToDniPage)

    # Last resort: rebuild from the raw page image if the DNI image is still missing.
    if not os.path.exists(pathToDniPage):
        page_path = build_dump_path("page", page_number)
        if os.path.exists(page_path):
            img = cv.imread(page_path, cv.IMREAD_GRAYSCALE)
            if img is None:
                raise RuntimeError(f"Cannot read page image: page-{page_number}")
            img_inv = cv.bitwise_not(img)
            Image.fromarray(img_inv).save(pathToDniPage)
        else:
            raise RuntimeError(
                f"No detection and no page image available for page {page_number}"
            )

    imgf = Image.open(pathToDniPage).convert("L")

    # 3) If we have a usable detection, build coordinates from the detected boxes.
    if detection is not None:
        digit_boxes = detection.get("digit_rects_xyxy", [])
        coords = _coords_from_digit_boxes(digit_boxes)
        if coords is not None:
            return imgf, pathToDniPage, coords

    # 4) Final fallback: reconstruct boxes from the stored anchor.
    anchor_rect = coordsDNI[j - 1]
    fallback_boxes = _synthetic_boxes_from_anchor(anchor_rect)
    coords = _coords_from_digit_boxes(fallback_boxes)

    if coords is not None:
        return imgf, pathToDniPage, coords

    raise RuntimeError(f"Cannot build DNI boxes for page {page_number}")

def split_in_num_cpu(nbp):
    # Distribute page numbers across CPU buckets to parallelize first-page detection.
    configured_workers = int(os.environ.get("AI_DETECTION_WORKERS", "4"))
    workers = max(1, min(configured_workers, nbp))
    result = [[] for _ in range(workers)]
    for i in range(1, nbp + 1):
        result[(i - 1) % workers].append(i)
    return result
