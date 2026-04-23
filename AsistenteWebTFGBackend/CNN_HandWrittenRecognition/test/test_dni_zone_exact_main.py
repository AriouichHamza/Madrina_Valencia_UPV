#!/usr/bin/env python3
import argparse
import csv
import os
import shutil
from PIL import Image, ImageDraw
from PyPDF2 import PdfReader

import main_exact_dni_lib as exact


def normalize_box(box):
    x0, y0, x1, y1 = [int(v) for v in box]
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def draw_debug_image(image_path, anchor_rect, coords, output_path):
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    if anchor_rect is not None:
        draw.rectangle(normalize_box(anchor_rect), outline=(255, 0, 0), width=3)

    for idx in range(len(coords)):
        box = (
            int(coords[idx][0][0]),
            int(coords[idx][0][1]),
            int(coords[idx][0][2]),
            int(coords[idx][0][3]),
        )
        box = normalize_box(box)
        draw.rectangle(box, outline=(0, 255, 0), width=2)
        draw.text((box[0], box[1]), str(idx + 1), fill=(255, 255, 0))

    image.save(output_path)


def main():
    parser = argparse.ArgumentParser(description="Test exact des zones DNI avec les fonctions de main.py sans modifier leur corps.")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--keep-workdir", action="store_true")
    args = parser.parse_args()

    pdf_path = os.path.abspath(args.pdf)
    output_dir = os.path.abspath(args.output)
    work_dir = os.path.join(output_dir, "workdir")
    annotated_dir = os.path.join(output_dir, "annotated")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(annotated_dir, exist_ok=True)

    exact.setup_globals(pdf_path=pdf_path, output_dir=work_dir, model_path=None, examen_name=os.path.splitext(os.path.basename(pdf_path))[0])

    nbp = exact.convert_pdf_like_main()
    coordsDNI, ListNumFirstPage = exact.detect_first_pages_like_main(nbp)

    summary_rows = []
    for j in range(1, len(ListNumFirstPage) + 1):
        imgf, pathToDniPage, coords = exact.compute_coords_from_main_block(j, coordsDNI, ListNumFirstPage)
        page = ListNumFirstPage[j - 1]
        anchor_rect = coordsDNI[j - 1]
        annotated_path = os.path.join(annotated_dir, f"page_{page}_dni_boxes.png")
        draw_debug_image(pathToDniPage, anchor_rect, coords, annotated_path)

        row = {
            "page": page,
            "dni_anchor_x0": anchor_rect[0],
            "dni_anchor_y0": anchor_rect[1],
            "dni_anchor_x1": anchor_rect[2],
            "dni_anchor_y1": anchor_rect[3],
            "annotated_image": annotated_path,
        }
        for idx in range(9):
            row[f"box_{idx+1}"] = str(tuple(int(v) for v in coords[idx][0]))
        summary_rows.append(row)

    summary_csv = os.path.join(output_dir, "summary.csv")
    fieldnames = [
        "page", "dni_anchor_x0", "dni_anchor_y0", "dni_anchor_x1", "dni_anchor_y1", "annotated_image",
        "box_1", "box_2", "box_3", "box_4", "box_5", "box_6", "box_7", "box_8", "box_9"
    ]
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Pages totales: {nbp}")
    print(f"Premières pages détectées: {len(ListNumFirstPage)}")
    print(f"Résumé: {summary_csv}")
    print(f"Images annotées: {annotated_dir}")

    if not args.keep_workdir:
        shutil.rmtree(work_dir, ignore_errors=True)
        print("Workdir temporaire supprimé.")
    else:
        print(f"Workdir conservé: {work_dir}")


if __name__ == "__main__":
    main()
