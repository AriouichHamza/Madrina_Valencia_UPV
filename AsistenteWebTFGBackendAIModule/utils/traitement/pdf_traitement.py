from __future__ import annotations

import os
from PIL import Image
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    
    
def convert_pdf_batch(start_page, end_page, input_pdf, output_folder):
    command = [
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
        os.path.join(output_folder, "page"),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or "").strip()
        raise RuntimeError(f"pdftoppm failed for pages {start_page}-{end_page}: {message}") from exc

    return end_page - start_page + 1


def convert_grade_page(page_number, input_pdf, output_folder):
    raw_prefix = os.path.join(output_folder, f".grade-{page_number}")
    raw_path = f"{raw_prefix}.png"
    command = [
        "pdftoppm",
        "-png",
        "-singlefile",
        "-f", str(page_number),
        "-l", str(page_number),
        "-r", "300",
        "-x", "1600",
        "-y", "360",
        "-W", "900",
        "-H", "400",
        input_pdf,
        raw_prefix,
    ]

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        output_path = build_dump_path(
            "calification",
            page_number,
            output_folder_path=output_folder,
        )
        if not os.path.isfile(raw_path):
            raise RuntimeError(f"Missing generated grade image: {raw_path}")
        os.replace(raw_path, output_path)
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or "").strip()
        raise RuntimeError(f"pdftoppm failed for grade page {page_number}: {message}") from exc
    finally:
        if os.path.exists(raw_path):
            os.remove(raw_path)

    return page_number


def run_pdf_preprocessing(total_pages=None):
    if total_pages is None:
        from PyPDF2 import PdfReader

        total_pages = len(PdfReader(inputPDF).pages)

    os.makedirs(output_folder, exist_ok=True)
    set_page_num_width(total_pages)

    configured_workers = int(os.environ.get("AI_PDF_WORKERS", "4"))
    max_workers = max(1, min(configured_workers, total_pages))
    pages_per_batch = max(1, (total_pages + max_workers - 1) // max_workers)

    emitter.emit_progress(0, "Convirtiendo PDF a imagenes")

    completed_pages = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for start_page in range(1, total_pages + 1, pages_per_batch):
            end_page = min(start_page + pages_per_batch - 1, total_pages)
            futures.append(
                executor.submit(
                    convert_pdf_batch,
                    start_page,
                    end_page,
                    inputPDF,
                    output_folder,
                )
            )

        for future in as_completed(futures):
            completed_pages += future.result()
            progress = int((completed_pages / total_pages) * 100)
            emitter.emit_progress(progress, "Convirtiendo PDF a imagenes")

    missing_pages = [
        page_number
        for page_number in range(1, total_pages + 1)
        if not os.path.isfile(build_dump_path("page", page_number))
    ]
    if missing_pages:
        preview = ", ".join(str(page) for page in missing_pages[:10])
        raise RuntimeError(f"Missing generated page image(s): {preview}")



def run_grade_preprocessing(page_numbers):
    pages = sorted(set(int(page) for page in page_numbers))
    if not pages:
        return

    configured_workers = int(os.environ.get("AI_PDF_WORKERS", "4"))
    max_workers = max(1, min(configured_workers, len(pages)))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                convert_grade_page,
                page_number,
                inputPDF,
                output_folder,
            )
            for page_number in pages
        ]
        for future in as_completed(futures):
            future.result()
