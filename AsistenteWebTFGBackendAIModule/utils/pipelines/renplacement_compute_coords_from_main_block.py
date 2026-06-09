from __future__ import annotations


from utils.traitement.pdf_traitement import build_dump_path
from utils.traitement.imageProcessing import detect_dni_chain_on_page
from utils.pipelines.remplacement_bascar_inicio_copias import _coords_from_digit_boxes, _synthetic_boxes_from_anchor
import os
import cv2 as cv
from PIL import Image





# --------------------------------------------------------
# REMPLACEMENT de compute_coords_from_main_block()
# --------------------------------------------------------
def compute_coords_from_main_block(j, coordsDNI, ListNumFirstPage):
    page_number = ListNumFirstPage[j - 1]

    # 1) tentative stricte
    detection = detect_dni_chain_on_page(page_number, mode="coords_detect")

    # 2) fallback permissif
    if detection is None:
        detection = detect_dni_chain_on_page(page_number, mode="page_detect")

    pathToDniPage = build_dump_path("DNIpage", page_number)

    # si le fichier DNIpage n'existe pas encore mais qu'on a une detection, on le sauve
    if detection is not None and not os.path.exists(pathToDniPage):
        Image.fromarray(detection["gray_for_ocr"]).save(pathToDniPage)

    # fallback ultime : si toujours pas d'image DNI, on repart de page-XX.png
    if not os.path.exists(pathToDniPage):
        page_path = build_dump_path("page", page_number)
        if os.path.exists(page_path):
            img = cv.imread(page_path, cv.IMREAD_GRAYSCALE)
            if img is None:
                raise RuntimeError(f"Impossible de lire page-{page_number}")
            img_inv = cv.bitwise_not(img)
            Image.fromarray(img_inv).save(pathToDniPage)
        else:
            raise RuntimeError(
                f"Ni detection ni image disponible pour la page {page_number}"
            )

    imgf = Image.open(pathToDniPage).convert("L")

    # 3) si on a une detection utilisable, on construit les coords depuis les boxes detectees
    if detection is not None:
        digit_boxes = detection.get("digit_rects_xyxy", [])
        coords = _coords_from_digit_boxes(digit_boxes)
        if coords is not None:
            return imgf, pathToDniPage, coords

    # 4) fallback final : reconstruire les boxes depuis l'ancre deja stockee
    anchor_rect = coordsDNI[j - 1]
    fallback_boxes = _synthetic_boxes_from_anchor(anchor_rect)
    coords = _coords_from_digit_boxes(fallback_boxes)

    if coords is not None:
        return imgf, pathToDniPage, coords

    raise RuntimeError(f"Impossible de construire les boxes DNI pour la page {page_number}")

def split_in_num_cpu(nbp):
    # Distribute page numbers across CPU buckets to parallelize first-page detection.
    cores = os.cpu_count() or 1
    result = [[] for _ in range(cores)]
    for i in range(1, nbp + 1):
        result[i % cores].append(i)
    return result
