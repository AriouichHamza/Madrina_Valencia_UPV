from __future__ import annotations

import os
from PIL import Image
import subprocess
from concurrent.futures import ProcessPoolExecutor
from utils.constants import output_folder, inputPDF
from Modules.emitter import Emitter


emitter = Emitter()
PAGE_NUM_WIDTH = 1



def set_page_num_width(total_pages):
    global PAGE_NUM_WIDTH
    PAGE_NUM_WIDTH = max(1, len(str(total_pages)))

def format_page_number(page_number, width=None):
    if width is None:
        width = PAGE_NUM_WIDTH
    return f"{int(page_number):0{width}d}"

def build_dump_path(prefix, page_number, extension="png", output_folder_path=None):
    if output_folder_path is None:
        output_folder_path = output_folder
    return os.path.join(output_folder_path, f"{prefix}-{format_page_number(page_number)}.{extension}")

def safe_crop_digit(image, box):
    width, height = image.size
    original_box = tuple(int(v) for v in box)
    left, top, right, bottom = original_box

    if right <= left or bottom <= top:
        return Image.new(image.mode, (28, 28), 0), True

    crop_width = right - left
    crop_height = bottom - top
    clamped_box = (
        max(0, min(left, width)),
        max(0, min(top, height)),
        max(0, min(right, width)),
        max(0, min(bottom, height)),
    )

    if clamped_box[2] <= clamped_box[0] or clamped_box[3] <= clamped_box[1]:
        return Image.new(image.mode, (28, 28), 0), True

    try:
        if clamped_box == original_box:
            return image.crop(clamped_box), False

        area = Image.new(image.mode, (crop_width, crop_height), 0)
        cropped = image.crop(clamped_box)
        area.paste(cropped, (clamped_box[0] - left, clamped_box[1] - top))
        return area, True
    except Exception:
        return Image.new(image.mode, (28, 28), 0), True
    
    
def convert_pdf_to_images(start_page, end_page, input_pdf, output_folder, total_pages):
    # Render the header area of each page, which contains the DNI boxes.
    commande = [
        "pdftoppm",
        "-png",
        "-f", str(start_page),
        "-l", str(end_page),
        "-r", "300",
        "-x", "900",
        "-y", "0",
        "-W", "3000",
        "-H", "600",
        input_pdf,
        os.path.join(output_folder, "page")
    ]
    subprocess.run(commande)
    progress = int((start_page / total_pages) * 100)
    emitter.emit_progress(progress, "Convirtiendo PDF a imagenes")
    
def convert_pdf_to_images_calification(start_page, end_page, input_pdf, output_folder):
    # Render the area where the handwritten grade is expected to appear.
    commande = [
        "pdftoppm",
        "-png",
        "-f", str(start_page),
        "-l", str(end_page),
        "-r", "300",
        "-x", "1600",
        "-y", "360",
        "-W", "900",
        "-H", "400",
        input_pdf,
        os.path.join(output_folder, "calification")
    ]
    subprocess.run(commande)
    
    
def run_pdf_preprocessing(total_pages=None):
    if total_pages is None:
        from PyPDF2 import PdfReader

        total_pages = len(PdfReader(inputPDF).pages)

    os.makedirs(output_folder, exist_ok=True)
    set_page_num_width(total_pages)

    num_cores = os.cpu_count() or 1
    pages_per_batch = max(1, total_pages // num_cores)

    emitter.emit_progress(0, "Convirtiendo PDF a imagenes")

    # Convert full-page DNI regions and grade regions in parallel for faster preprocessing.
    with ProcessPoolExecutor() as executor:
        futures = []
        for start_page in range(1, total_pages + 1, pages_per_batch):
            end_page = min(start_page + pages_per_batch - 1, total_pages)
            futures.append(executor.submit(convert_pdf_to_images, start_page, end_page, inputPDF, output_folder, total_pages))
            futures.append(executor.submit(convert_pdf_to_images_calification, start_page, end_page, inputPDF, output_folder))

        for future in futures:
            future.result()

    emitter.emit_progress(100, "Conversion de PDF a imagenes completada")
