from __future__ import annotations


from Modules.emitter import Emitter
from utils.traitement.pdf_traitement import build_dump_path
import numpy as np
from PIL import Image
import os


emitter = Emitter()

# --------------------------------------------------------
# Replaces buscar_inicio_copias()
# --------------------------------------------------------



def buscar_inicio_copias(pages, nbp):
    from utils.traitement.imageProcessing import detect_dni_chain_on_page

    pagesConfirmed = []

    for page in pages:
        progress = int((page + 1) / nbp * 100) - 1
        emitter.emit_progress(progress, "Buscando DNIs en páginas")

        detection = detect_dni_chain_on_page(page, mode="page_detect")

        if detection is not None:
            path_dni_page = build_dump_path("DNIpage", page)
            Image.fromarray(detection["gray_for_ocr"]).save(path_dni_page)

            anchor_rect = detection["anchor_rect_xyxy"]
            pagesConfirmed.append([anchor_rect, page])

            # Keep page-XX.png — the next detection pass may read it again.
        else:
            pathToCalificacion = build_dump_path("calification", page)
            if os.path.exists(pathToCalificacion):
                os.remove(pathToCalificacion)

    return pagesConfirmed

def rect_center(rect):
    x, y, w, h = rect
    return (x + w / 2.0, y + h / 2.0)

def support_line_below(binary_img, digit_rects):
    """Checks for a long horizontal line below the DNI row — a strong indicator of a first page."""
    if len(digit_rects) < 7:
        return 0.0

    xs = [r[0] for r in digit_rects]
    ys = [r[1] for r in digit_rects]
    ws = [r[2] for r in digit_rects]
    hs = [r[3] for r in digit_rects]

    x_left = max(0, min(xs) - int(np.mean(ws) * 0.6))
    x_right = min(binary_img.shape[1], max([x + w for x, y, w, h in digit_rects]) + int(np.mean(ws) * 0.6))
    y_base = int(np.mean([y + h for x, y, w, h in digit_rects]) + np.mean(hs) * 0.9)

    if y_base < 0 or y_base >= binary_img.shape[0]:
        return 0.0

    band_h = max(3, int(np.mean(hs) * 0.18))
    y0 = max(0, y_base - band_h)
    y1 = min(binary_img.shape[0], y_base + band_h)

    roi = binary_img[y0:y1, x_left:x_right]
    if roi.size == 0:
        return 0.0

    # lit-pixel ratio per row
    row_fill = np.mean(roi > 0, axis=1)
    return float(np.max(row_fill))

def score_digit_row_for_page(window, binary_img):
    """Recall-oriented score used to decide whether a page is likely a first page."""
    n = len(window)
    if n < 7:
        return -1e9

    rects = [w["rect"] for w in window]
    widths = np.array([r[2] for r in rects], dtype=np.float32)
    heights = np.array([r[3] for r in rects], dtype=np.float32)
    ys = np.array([rect_center(r)[1] for r in rects], dtype=np.float32)

    gaps = []
    for i in range(n - 1):
        x1 = rects[i][0] + rects[i][2]
        x2 = rects[i + 1][0]
        gaps.append(x2 - x1)

    gaps = np.array(gaps, dtype=np.float32) if gaps else np.array([0], dtype=np.float32)

    mean_box_score = float(np.mean([w["score"] for w in window]))
    line_support = support_line_below(binary_img, rects)

    reg_pen = (
        np.std(widths) / (np.mean(widths) + 1e-6) +
        np.std(heights) / (np.mean(heights) + 1e-6) +
        np.std(ys) / (np.mean(heights) + 1e-6)
    )

    gap_pen = np.std(gaps) / max(np.mean(np.abs(gaps)), 1.0)

    length_bonus = 0.0
    if n == 9:
        length_bonus = 5.0
    elif n == 8:
        length_bonus = 2.5
    elif n == 7:
        length_bonus = 1.0

    return (
        mean_box_score * 10.0 +
        line_support * 6.0 +
        length_bonus -
        7.0 * reg_pen -
        4.0 * gap_pen
    )
    
def find_best_digit_sequence_for_page(rows, binary_img):
    """Searches for the best 7-to-9 box sequence, optimising for recall."""
    best = None
    best_score = -1e9

    for row in rows:
        row_len = len(row)
        if row_len < 7:
            continue

        for target_len in (9, 8, 7):
            if row_len < target_len:
                continue

            for start in range(0, row_len - target_len + 1):
                window = row[start:start + target_len]
                score = score_digit_row_for_page(window, binary_img)

                if score > best_score:
                    best_score = score
                    best = {
                        "row": row,
                        "start": start,
                        "window": window,
                        "score": score,
                    }

    return best

def _pad_digit_boxes_to_9(digit_boxes):
    """
    Ensures exactly 9 boxes:
    - 9 boxes: unchanged
    - 8 boxes: extrapolates the 9th
    - <8 boxes: returned as-is
    """
    digit_boxes = list(digit_boxes)

    if len(digit_boxes) >= 9:
        return digit_boxes[:9]

    if len(digit_boxes) == 8:
        x0, y0, x1, y1 = digit_boxes[-1]
        w = x1 - x0
        h = y1 - y0

        if len(digit_boxes) >= 2:
            px0, py0, px1, py1 = digit_boxes[-2]
            gap = x0 - px1
            if gap < 0:
                gap = max(2, int(0.05 * w))
        else:
            gap = max(2, int(0.05 * w))

        new_box = (x1 + gap, y0, x1 + gap + w, y1)
        digit_boxes.append(new_box)

    return digit_boxes


def _coords_from_digit_boxes(digit_boxes):
    coords = np.zeros((9, 1, 4), dtype=int)

    digit_boxes = _pad_digit_boxes_to_9(digit_boxes)

    if len(digit_boxes) < 8:
        return None

    # if still short after padding, duplicate the last box to fill to 9
    while len(digit_boxes) < 9:
        digit_boxes.append(digit_boxes[-1])

    for idx, box in enumerate(digit_boxes[:9]):
        x0, y0, x1, y1 = box
        coords[idx][0][0] = int(x0)
        coords[idx][0][1] = int(y0)
        coords[idx][0][2] = int(x1)
        coords[idx][0][3] = int(y1)

    return coords


def _synthetic_boxes_from_anchor(anchor_rect_xyxy):
    """Last fallback: reconstructs 9 boxes to the right of the anchor when no detection is available."""
    ax0, ay0, ax1, ay1 = anchor_rect_xyxy
    anchor_w = max(10, ax1 - ax0)
    anchor_h = max(10, ay1 - ay0)

    gap = max(2, int(0.05 * anchor_w))
    box_w = anchor_w
    box_h = anchor_h

    boxes = []
    x = ax1 + gap
    y = ay0

    for _ in range(9):
        boxes.append((x, y, x + box_w, y + box_h))
        x += box_w + gap

    return boxes
