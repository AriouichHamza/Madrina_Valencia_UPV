from __future__ import annotations


import cv2 as cv
import numpy as np


from utils.traitement.pdf_traitement import build_dump_path
from utils.pipelines.remplacement_bascar_inicio_copias import find_best_digit_sequence_for_page


DNI_CHAIN_CACHE = {}


def remove_margin_all(img, margin = 0.05):
    # Trim a small border to reduce noise from box outlines before classification.
    h, w = img.shape[:2]
    
    margin_h = int(h * margin)
    margin_w = int(w * margin)
    borderless_img = img[margin_h:h - margin_h, margin_w:w - margin_w]
    return borderless_img
    
    
def is_square(contour, tolerance = 0.05):
    # Grade digits are expected inside square boxes, so we reject small or non-square contours.
    x, y, w, h = cv.boundingRect(contour)
    ratio = w / h
    if not ( 1- tolerance <= ratio <= 1 + tolerance):
        return False
    area = cv.contourArea(contour)
    if area < 900:
        return False
    peri = cv.arcLength(contour, True)
    approx = cv.approxPolyDP(contour, 0.04 * peri, True)
    return len(approx) == 4

# ----------------------------
# utilitaires
# ----------------------------
def rect_xyxy_to_xywh(rect):
    x0, y0, x1, y1 = rect
    return (int(x0), int(y0), int(x1 - x0), int(y1 - y0))

def rect_xywh_to_xyxy(rect):
    x, y, w, h = rect
    return (int(x), int(y), int(x + w), int(y + h))

def rect_center(rect):
    x, y, w, h = rect
    return (x + w / 2.0, y + h / 2.0)

def rect_area(rect):
    x, y, w, h = rect
    return max(0, w) * max(0, h)

def rect_iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b

    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh

    ix1 = max(ax, bx)
    iy1 = max(ay, by)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    union = rect_area(a) + rect_area(b) - inter
    return inter / union if union > 0 else 0.0

def order_points_clockwise(pts):
    pts = np.array(pts, dtype=np.float32).reshape(-1, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)

    top_left = pts[np.argmin(s)]
    bottom_right = pts[np.argmax(s)]
    top_right = pts[np.argmin(d)]
    bottom_left = pts[np.argmax(d)]

    return np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)

def rotate_image_keep_bounds(image, angle_deg):
    h, w = image.shape[:2]
    center = (w / 2.0, h / 2.0)
    M = cv.getRotationMatrix2D(center, angle_deg, 1.0)

    cos = abs(M[0, 0])
    sin = abs(M[0, 1])

    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))

    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]

    return cv.warpAffine(image, M, (new_w, new_h), flags=cv.INTER_LINEAR, borderValue=0)

def light_deskew(gray_inv):
    """Light deskew pass. Kept intentionally simple to avoid disrupting the main detection logic."""
    bw = cv.threshold(gray_inv, 0, 255, cv.THRESH_BINARY | cv.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(bw > 0))

    if len(coords) < 100:
        return gray_inv

    rect = cv.minAreaRect(coords[:, ::-1].astype(np.float32))
    angle = rect[-1]

    if angle < -45:
        angle = 90 + angle

    if abs(angle) < 0.2 or abs(angle) > 12:
        return gray_inv

    return rotate_image_keep_bounds(gray_inv, angle)

def preprocess_dni_page_multi(path_to_img):
    """Returns multiple binary variants of the same page to improve first-page recall."""
    img = cv.imread(path_to_img, cv.IMREAD_COLOR)
    if img is None:
        return []

    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    gray_inv = cv.bitwise_not(gray)

    variants = []

    # 1) adaptive standard
    blur = cv.GaussianBlur(gray_inv, (3, 3), 0)
    bw1 = cv.adaptiveThreshold(
        blur, 255,
        cv.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv.THRESH_BINARY,
        31, -5
    )
    bw1 = cv.morphologyEx(
        bw1, cv.MORPH_CLOSE,
        cv.getStructuringElement(cv.MORPH_RECT, (3, 3)),
        iterations=1
    )
    variants.append((gray_inv, bw1, "adaptive_close"))

    # 2) adaptive + small dilation to reconnect broken borders
    bw2 = cv.adaptiveThreshold(
        blur, 255,
        cv.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv.THRESH_BINARY,
        31, -5
    )
    bw2 = cv.morphologyEx(
        bw2, cv.MORPH_CLOSE,
        cv.getStructuringElement(cv.MORPH_RECT, (3, 3)),
        iterations=1
    )
    bw2 = cv.dilate(
        bw2,
        cv.getStructuringElement(cv.MORPH_RECT, (2, 2)),
        iterations=1
    )
    variants.append((gray_inv, bw2, "adaptive_close_dilate"))

    # 3) otsu
    blur2 = cv.GaussianBlur(gray_inv, (5, 5), 0)
    _, bw3 = cv.threshold(blur2, 0, 255, cv.THRESH_BINARY | cv.THRESH_OTSU)
    bw3 = cv.morphologyEx(
        bw3, cv.MORPH_CLOSE,
        cv.getStructuringElement(cv.MORPH_RECT, (3, 3)),
        iterations=1
    )
    variants.append((gray_inv, bw3, "otsu_close"))

    # 4) canny + stronger closing
    edges = cv.Canny(gray_inv, 35, 110)
    bw4 = cv.morphologyEx(
        edges, cv.MORPH_CLOSE,
        cv.getStructuringElement(cv.MORPH_RECT, (5, 3)),
        iterations=1
    )
    variants.append((gray_inv, bw4, "canny_close"))

    return variants

def box_metrics(binary_img, rect):
    """
    Computes accept/reject metrics for a candidate box:
    - border_fill_ratio: borders are sufficiently filled
    - inner_fill_ratio:  interior is not completely empty
    - corner_fill_ratio: all four corners are present
    """
    x, y, w, h = rect
    H, W = binary_img.shape[:2]

    x = max(0, min(x, W - 1))
    y = max(0, min(y, H - 1))
    w = max(1, min(w, W - x))
    h = max(1, min(h, H - y))

    roi = binary_img[y:y+h, x:x+w]
    if roi.size == 0:
        return {"border": 0.0, "inner": 0.0, "corners": 0.0}

    t = max(2, int(min(w, h) * 0.12))
    border_mask = np.ones_like(roi, dtype=np.uint8)
    if h > 2 * t and w > 2 * t:
        border_mask[t:h-t, t:w-t] = 0

    inner_mask = 1 - border_mask

    border = float(np.mean(roi[border_mask == 1] > 0)) if np.any(border_mask == 1) else 0.0
    inner = float(np.mean(roi[inner_mask == 1] > 0)) if np.any(inner_mask == 1) else 0.0

    p = max(2, int(min(w, h) * 0.16))
    corner_rois = [
        roi[0:p, 0:p],
        roi[0:p, max(0, w-p):w],
        roi[max(0, h-p):h, 0:p],
        roi[max(0, h-p):h, max(0, w-p):w],
    ]
    corners = float(np.mean([np.mean(c > 0) for c in corner_rois if c.size > 0])) if corner_rois else 0.0

    return {"border": border, "inner": inner, "corners": corners}

def detect_box_candidates(binary_img, recall_mode=False):
    """
    Detects box candidates from the binary image:
    - closed contour
    - approxPolyDP with 4 corners
    - consistent dimensions
    - border and corners sufficiently filled
    """
    contours, _ = cv.findContours(binary_img, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE)
    H, W = binary_img.shape[:2]
    img_area = H * W

    cands = []
    for cnt in contours:
        area = cv.contourArea(cnt)
        if area < 700 or area > img_area * 0.10:
            continue

        peri = cv.arcLength(cnt, True)
        approx = cv.approxPolyDP(cnt, 0.03 * peri, True)

        # in recall mode also accept 5-corner approximations if the bounding box looks right
        if len(approx) not in (4, 5):
            continue

        x, y, w, h = cv.boundingRect(approx)
        if w < 22 or h < 22:
            continue

        ratio = w / float(h)
        if ratio < 0.50 or ratio > 1.95:
            continue

        m = box_metrics(binary_img, (x, y, w, h))

        if recall_mode:
            if m["corners"] < 0.02:
                continue
            if m["border"] < 0.05:
                continue
        else:
            if m["corners"] < 0.04:
                continue
            if m["border"] < 0.10:
                continue

        score = (
            2.5 * m["corners"] +
            2.5 * m["border"] +
            0.7 * m["inner"]
        )

        cands.append({
            "rect": (x, y, w, h),
            "metrics": m,
            "score": score,
        })

    cands = sorted(cands, key=lambda d: d["score"], reverse=True)
    filtered = []
    for c in cands:
        keep = True
        for f in filtered:
            if rect_iou(c["rect"], f["rect"]) > 0.6:
                keep = False
                break
        if keep:
            filtered.append(c)

    filtered = sorted(filtered, key=lambda d: (d["rect"][1], d["rect"][0]))
    return filtered

def cluster_boxes_by_row(candidates):
    """Groups candidate boxes into horizontal rows."""
    rows = []
    for cand in sorted(candidates, key=lambda d: rect_center(d["rect"])[1]):
        cy = rect_center(cand["rect"])[1]
        placed = False
        for row in rows:
            row_cy = np.mean([rect_center(x["rect"])[1] for x in row])
            row_h = np.mean([x["rect"][3] for x in row])
            if abs(cy - row_cy) <= 0.45 * row_h:
                row.append(cand)
                placed = True
                break
        if not placed:
            rows.append([cand])

    for row in rows:
        row.sort(key=lambda d: d["rect"][0])

    return rows


def score_9_digit_window(window):
    """Scores an 8-or-9 box DNI sequence; higher score means more regular spacing and sizes."""
    n = len(window)
    if n < 2:
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

    if len(gaps) == 0:
        return -1e9

    gaps = np.array(gaps, dtype=np.float32)

    mean_score = float(np.mean([w["score"] for w in window]))
    reg_pen = (
        np.std(widths) / (np.mean(widths) + 1e-6) +
        np.std(heights) / (np.mean(heights) + 1e-6) +
        np.std(ys) / (np.mean(heights) + 1e-6) +
        np.std(gaps) / (max(np.mean(np.abs(gaps)), 1.0))
    )

    # Bonus for a complete 9-box chain.
    length_bonus = 4.0 if n == 9 else 0.0

    return mean_score * 10.0 - 8.0 * reg_pen + length_bonus


def find_best_9_digit_sequence(rows):
    """Searches for the best 9-box sequence; falls back to 8 boxes if a full sequence is unavailable."""
    best = None
    best_score = -1e9

    for row in rows:
        row_len = len(row)

        # prefer windows of 9
        if row_len >= 9:
            for start in range(0, row_len - 9 + 1):
                window = row[start:start + 9]
                score = score_9_digit_window(window)

                if score > best_score:
                    best_score = score
                    best = {
                        "row": row,
                        "start": start,
                        "window": window,
                        "score": score,
                    }

        # fallback: accept 8-box windows when a 9-box window is not available
        elif row_len == 8:
            window = row[:8]
            score = score_9_digit_window(window)

            if score > best_score:
                best_score = score
                best = {
                    "row": row,
                    "start": 0,
                    "window": window,
                    "score": score,
                }

    return best


def find_anchor_left_of_digits(row, digit_window):
    """Finds an anchor box strictly to the left of the digit sequence; synthesizes one if absent."""
    first_digit = digit_window[0]["rect"]
    fd_x, fd_y, fd_w, fd_h = first_digit
    fd_cy = rect_center(first_digit)[1]

    left_candidates = []
    for cand in row:
        r = cand["rect"]
        x, y, w, h = r
        cy = rect_center(r)[1]
        gap = fd_x - (x + w)

        # must be strictly to the left with no overlap
        if gap < 2:
            continue

        if abs(cy - fd_cy) > 0.35 * max(h, fd_h):
            continue

        if not (0.60 <= w / float(fd_w) <= 1.50):
            continue

        if not (0.60 <= h / float(fd_h) <= 1.50):
            continue

        # prefer the closest candidate to the left
        score = -abs(gap - 4) + 2.0 * cand["metrics"]["border"]
        left_candidates.append((score, cand))

    if left_candidates:
        left_candidates.sort(key=lambda x: x[0], reverse=True)
        return left_candidates[0][1]["rect"], False

    # fallback: synthesize a dummy anchor
    synth_gap = max(4, int(0.08 * fd_w))
    anchor_w = fd_w
    anchor_h = fd_h
    anchor_x = max(0, fd_x - synth_gap - anchor_w)
    anchor_y = fd_y
    return (anchor_x, anchor_y, anchor_w, anchor_h), True


def detect_dni_chain_on_page(page_number, mode="coords_detect"):
    """Detects the anchor box and the 9 DNI digit boxes to its right on the given page."""

    global DNI_CHAIN_CACHE

    cache_key = (page_number, mode)
    if cache_key in DNI_CHAIN_CACHE:
        return DNI_CHAIN_CACHE[cache_key]

    path_to_img = build_dump_path("page", page_number)
    variants = preprocess_dni_page_multi(path_to_img)
    if not variants:
        DNI_CHAIN_CACHE[cache_key] = None
        return None

    best_result = None
    best_score = -1e9

    for gray_inv, bw, variant_name in variants:
        recall_mode = (mode == "page_detect")
        candidates = detect_box_candidates(bw, recall_mode=recall_mode)
        if len(candidates) < 7:
            continue

        rows = cluster_boxes_by_row(candidates)

        if mode == "page_detect":
            best_seq = find_best_digit_sequence_for_page(rows, bw)
        else:
            best_seq = find_best_9_digit_sequence(rows)

        if best_seq is None:
            continue

        digit_rects = [w["rect"] for w in best_seq["window"]]
        anchor_rect, synthetic_anchor = find_anchor_left_of_digits(best_seq["row"], best_seq["window"])

        seq_len = len(digit_rects)

        if mode == "page_detect":
            # page_detect: accept from 7 consistent boxes for higher recall
            if seq_len < 7:
                continue
            accept_score = best_seq["score"] + (1.5 if not synthetic_anchor else -0.5)
        else:
            # coords_detect: require 8 or 9 boxes for reliable coordinates
            if seq_len < 8:
                continue
            accept_score = best_seq["score"] + (2.0 if not synthetic_anchor else -1.0)

        if accept_score > best_score:
            best_score = accept_score
            best_result = {
                "anchor_rect_xywh": anchor_rect,
                "anchor_rect_xyxy": rect_xywh_to_xyxy(anchor_rect),
                "digit_rects_xywh": digit_rects[:9],
                "digit_rects_xyxy": [rect_xywh_to_xyxy(r) for r in digit_rects[:9]],
                "gray_for_ocr": gray_inv,
                "binary_debug": bw,
                "score": accept_score,
                "variant_name": variant_name,
                "synthetic_anchor": synthetic_anchor,
                "seq_len": seq_len,
            }

    DNI_CHAIN_CACHE[cache_key] = best_result
    return best_result

def compatible_next_box(prev_rect, next_rect):
    """Returns (ok, cost) for two consecutive boxes: ok if they satisfy adjacency and size constraints."""
    px, py, pw, ph = prev_rect
    nx, ny, nw, nh = next_rect

    pcx, pcy = rect_center(prev_rect)
    ncx, ncy = rect_center(next_rect)

    gap = nx - (px + pw)   # distance horizontale entre les deux cases

    # must be on the same horizontal line
    if abs(ncy - pcy) > 0.35 * max(ph, nh):
        return False, None

    # similar size
    if not (0.65 <= nw / float(pw) <= 1.45):
        return False, None
    if not (0.65 <= nh / float(ph) <= 1.45):
        return False, None

    # must be adjacent (not overlapping and not too far)
    if gap < -0.20 * pw:
        return False, None
    if gap > 1.00 * pw:
        return False, None

    # neighbourhood cost: lower is better
    y_pen = abs(ncy - pcy) / max(ph, nh)
    w_pen = abs(nw - pw) / max(pw, 1)
    h_pen = abs(nh - ph) / max(ph, 1)
    gap_target = 0.05 * pw
    gap_pen = abs(gap - gap_target) / max(pw, 1)

    chain_cost = y_pen + w_pen + h_pen + gap_pen
    return True, chain_cost

def build_chain_from_seed(candidates, seed_idx, target_len=10):
    """Builds a horizontal chain of boxes (anchor + 9 DNI boxes) starting from a seed candidate."""
    used = {seed_idx}
    chain = [candidates[seed_idx]]

    while len(chain) < target_len:
        prev = chain[-1]
        prev_rect = prev["rect"]

        best = None
        best_cost = 1e9
        best_idx = None

        for idx, cand in enumerate(candidates):
            if idx in used:
                continue

            ok, cost = compatible_next_box(prev_rect, cand["rect"])
            if not ok:
                continue

            # bonus for a box that looks like a real cell
            cost = cost - 0.25 * cand["score"]

            if cost < best_cost:
                best_cost = cost
                best = cand
                best_idx = idx

        if best is None:
            break

        chain.append(best)
        used.add(best_idx)

    return chain

def chain_global_score(chain):
    if not chain:
        return -1e9

    rects = [c["rect"] for c in chain]
    widths = np.array([r[2] for r in rects], dtype=np.float32)
    heights = np.array([r[3] for r in rects], dtype=np.float32)
    centers_y = np.array([rect_center(r)[1] for r in rects], dtype=np.float32)

    scores = np.array([c["score"] for c in chain], dtype=np.float32)

    consistency_penalty = (
        np.std(widths) / (np.mean(widths) + 1e-6) +
        np.std(heights) / (np.mean(heights) + 1e-6) +
        np.std(centers_y) / (np.mean(heights) + 1e-6)
    )

    return len(chain) * 10.0 + float(np.mean(scores)) - 5.0 * consistency_penalty

def normalize_img(img):
    # Keep the digit normalization steps consistent with the training pipeline.
    from torchvision import transforms

    transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((28, 28)),
        transforms.ToTensor(),
        transforms.Normalize((0.5,), (0.5,))
    ])
    img = transform(img)
    img = img.unsqueeze(0)
    return img
