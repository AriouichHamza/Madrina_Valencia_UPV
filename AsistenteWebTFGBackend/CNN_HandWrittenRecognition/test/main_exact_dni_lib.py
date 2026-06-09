import multiprocessing
import signal
import glob
import re


import PyPDF2 
from PyPDF2 import PdfFileReader, PdfFileWriter, PdfReader

from PIL import Image
import csv
from csv import reader

import matplotlib.pyplot as plt

import sys
from skimage.transform import resize
from skimage.io import imread, imshow
from skimage import exposure
from skimage.color import rgb2gray
import numpy as np
from skimage.filters import threshold_mean, threshold_otsu
import pandas as pd
  
import os

import cv2 as cv

import torch
from torch.utils.data import DataLoader, random_split, TensorDataset
from torch import nn

import torchvision
from torchvision.datasets import MNIST
from torchvision import transforms

from sklearn.metrics import accuracy_score

import copy
import random
from tqdm import tqdm

import sys
#Nuevo
import subprocess
from concurrent.futures import ProcessPoolExecutor
import json
from datetime import datetime
import Levenshtein
import threading
#import cProfile
import shutil

# ---------------------------------------------------------------------------
# Variables globales attendues par le code exact de main.py
# ---------------------------------------------------------------------------
initial_time = datetime.now()
emitter = None
current_folder = os.path.abspath(os.path.dirname(__file__))
root_folder = os.path.dirname(current_folder)
index = ""
examen_nombre = ""
alumnos = []
usuario = ""
asignatura_ID = ""
examen_ID = ""
examImgsPath = ""
inputPDF = ""
output_folder = ""
trained_model_name = 'exammodel4.pt'
trained_model_path = "/home/ariouich/Bureau/valencia/Madrina/AsistenteWebTFGBackend/CNN_HandWrittenRecognition/" + trained_model_name
global_CNN_model = None
PAGE_NUM_WIDTH = 1
DNI_CHAIN_CACHE = {}


def set_page_num_width(total_pages):
    global PAGE_NUM_WIDTH
    PAGE_NUM_WIDTH = max(1, len(str(total_pages)))


def format_page_number(page_number, width=None):
    if width is None:
        width = PAGE_NUM_WIDTH
    return f"{int(page_number):0{width}d}"


def build_dump_path(prefix, page_number, extension="png"):
    return os.path.join(output_folder, f"{prefix}-{format_page_number(page_number)}.{extension}")


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


class Alumno:
    def __init__(self, asignatura, examen, dni, nombre, apellidos, ini, fin , nota):
        self.asignatura=  asignatura
        self.examen=  examen
        self.dni = dni
        self.nombre =  nombre
        self.apellidos = apellidos  
        self.ini =  ini
        self.fin =  fin
        self.nota  =  nota
    def to_json(self):
        return json.dumps(self.__dict__)
        

class Emitter:
    # Stdout is used as a lightweight protocol to report progress/results to the parent process.
    def emit_progress(self, progress, state):
        sys.stdout.write(f"progress {progress} {state}\n")
        
    def emit_done(self, time_elapsed):
        sys.stdout.write(f"done {time_elapsed}\n")
        
    def emit_student(self, alumno : Alumno):
        sys.stdout.write(f"new-calificado {alumno.to_json()}\n")
        
    
    
def normalize_DNI(dni):
    # Remove leading zeros so OCR output can be compared against stored DNI values reliably.
    return dni.lstrip('0')


class SilentEmitter(Emitter):
    def emit_progress(self, progress, state):
        pass

    def emit_done(self, time_elapsed):
        pass

    def emit_student(self, alumno : Alumno):
        pass


def setup_globals(pdf_path, output_dir, model_path=None, examen_name=None, silent=True):
    global emitter, current_folder, root_folder, index, examen_nombre, alumnos
    global usuario, asignatura_ID, examen_ID, examImgsPath, inputPDF, output_folder
    global trained_model_path, global_CNN_model

    current_folder = os.path.abspath(os.path.dirname(__file__))
    root_folder = os.path.dirname(current_folder)
    index = "test-0-0"
    examen_nombre = examen_name if examen_name is not None else os.path.splitext(os.path.basename(pdf_path))[0]
    alumnos = []
    usuario = "test"
    asignatura_ID = "0"
    examen_ID = "0"
    examImgsPath = os.path.dirname(os.path.abspath(pdf_path)) + "/"
    inputPDF = os.path.abspath(pdf_path)
    output_folder = os.path.abspath(output_dir)
    if not output_folder.endswith(os.sep):
        output_folder += os.sep
    trained_model_path = os.path.abspath(model_path) if model_path else ""
    set_page_num_width(len(PdfReader(inputPDF).pages))

    if silent:
        emitter = SilentEmitter()
    else:
        emitter = Emitter()

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    global_CNN_model = None
    if trained_model_path:
        global_CNN_model = CNN()
        global_CNN_model.load_state_dict(torch.load(trained_model_path, map_location='cpu'))
        global_CNN_model.eval()


class CNN(nn.Module): # inherite of the class Module
    def __init__(self):
        super().__init__()
        
        # First convolutionnal Layer
        self.conv1 = nn.Conv2d(in_channels=1, out_channels=32, kernel_size=3, stride=1, padding=1)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2)
        
        # Second convolutionnal layer
        self.conv2 = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=1, padding=1)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool2d(kernel_size=2, stride=2)
        
        # Third convolutionnal layer
        self.conv3 = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=1, padding=1)
        self.relu3 = nn.ReLU()
        self.pool3 = nn.MaxPool2d(kernel_size=2, stride=2)
        
        # Fourth convolutionnal layer
        self.conv4 = nn.Conv2d(in_channels=32, out_channels=64, kernel_size=3, stride=1, padding=1)
        self.relu4 = nn.ReLU()
        self.pool4 = nn.MaxPool2d(kernel_size=2, stride=2)
        
        # Fully-Connected Layer (FC)
        self.fc = nn.Linear(64 * 1 * 1, 10)  # 64 channels * 2x2 feature map size
        
                
        #Softmax
        # We don't appli softmax here because he is already include in the CrossEntropyLoss function use after.
        
    def forward(self, x):
        # Each block extracts higher-level digit features before the final classifier layer.
        x = self.conv1(x)
        x = self.relu1(x)
        x = self.pool1(x)
        
        x = self.conv2(x)
        x = self.relu2(x)
        x = self.pool2(x)
        
        x = self.conv3(x)
        x = self.relu3(x)
        x = self.pool3(x)
        
        x = self.conv4(x)
        x = self.relu4(x)
        x = self.pool4(x)
        
        x = x.view(x.size(0), -1)  # Flatten features for FC layer
        
        x = self.fc(x)
        
        return x


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
    if not ( 1- tolerance <= ratio <= 1 + tolerance):# we will see later if this condition is good or not, maybe we can just check if the contour have 4 angles with approxPolyDP and not check the ratio, because maybe some boxes are not perfectly square, but they are still good for us.
        return False
    area = cv.contourArea(contour)
    if area < 900:
        return False
    peri = cv.arcLength(contour, True)
    approx = cv.approxPolyDP(contour, 0.04 * peri, True)
    return len(approx) == 4


transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((28, 28)),
    transforms.ToTensor(),
    transforms.Normalize((0.5,), (0.5,))
])
transform_to_Tensor = transforms.Compose([
    transforms.ToTensor()
])
def normalize_img(img):
    # Keep the digit normalization steps consistent with the training pipeline.
    img = transform(img)
    img = img.unsqueeze(0)
    return img

    
def detec_calification(numPage):
    # Read the grade area, detect the filled boxes, and classify each handwritten digit.
    
    path_to_calification = build_dump_path("calification", numPage)
    
    img = Image.open(path_to_calification)
    
    img_grey = cv.cvtColor(np.array(img), cv.COLOR_BGR2GRAY)
    #cv.imwrite(output_folder + "calification-grey-1-" + str(numPage) + ".png", img_grey)
    blur = cv.GaussianBlur(img_grey, (5, 5), 0)
    #cv.imwrite(output_folder + "calification-blur-1-" + str(numPage) + ".png", blur)
    img_edge = cv.Canny(blur, 30, 200, 1)
    #cv.imwrite(output_folder + "calification-edge-1-" + str(numPage) + ".png", img_edge)
    # Close small gaps so square borders are detected as complete contours.
    kernel = cv.getStructuringElement(cv.MORPH_RECT, (3, 3))
    closed = cv.morphologyEx(img_edge, cv.MORPH_CLOSE, kernel)
    
    #cv.imwrite(output_folder + "calification-edge-closed" + str(numPage) + ".png", closed)
    
    contours, _ = cv.findContours(closed, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)
    crop_califications_list = []
    
    square_contours = []
    for i, contour in enumerate(contours):
        if is_square(contour):
            square_contours.append(contour)
            
    # Sort left-to-right so the predicted digits keep the same order as the written grade.
    square_contours = sorted(square_contours, key = lambda contour: cv.boundingRect(contour)[0] ) 
    
    
    for i, contour in enumerate(square_contours):
        x, y, w, h = cv.boundingRect(contour)
        
        #print(str(numPage) + " and contour " + str(i) + " is square")
        pathToClean = build_dump_path("clean1", numPage) + f"-{i}.png"
        
        img_aux = img.crop((x, y, x + w, y + h))
        
        img_aux.save(pathToClean)
        #img_aux = closed[y:y+h, x:x+w]
        
        img_auxCV = cv.imread(pathToClean)
        
        img_auxCV = remove_margin_all(img_auxCV)
        img_auxCV = cv.cvtColor(img_auxCV, cv.COLOR_BGR2GRAY)
        #ToGrey
        
        #
        _, binary_img = cv.threshold(img_auxCV, 100, 255, cv.THRESH_BINARY)
        white_pixels = cv.countNonZero(binary_img)
        total_pixels = binary_img.size
    
        # Skip boxes that are completely blank.
        print("White pixels: " + str(white_pixels) + " Total pixels: " + str(total_pixels) + " = " + str(white_pixels/total_pixels)+ "  Page: " + str(numPage) + "  Contour: " + str(i))
        if white_pixels == total_pixels:
            print("Empty image")
            continue
        
        img_auxCV = cv.resize(img_auxCV, (28, 28))
        
        img_auxCV = cv.bitwise_not(img_auxCV)
        
        cv.imwrite(build_dump_path("final-cut", numPage) + f"-{i}.png", img_auxCV)
        #os.remove(pathToClean)
        imgf = Image.open(build_dump_path("final-cut", numPage) + f"-{i}.png").convert('L')
        
        crop_califications_list.append(imgf)
        continue


    predictions_califications = []
    for i, crop_calification in enumerate(crop_califications_list):
        # Quantize grayscale values to the same buckets used when preparing training samples.
        M = np.zeros((28,28), dtype=int)
        for x in range(28):
            for y in range(28):
                z=crop_calification.getpixel((x,y))
                    
                if z <= 13:
                    z = 0
                elif z <= 51:
                    z = 26
                elif z <= 76:
                    z = 153
                else:
                    z = 254
                M[y,x] = z
                
        tensor = torch.Tensor(M).unsqueeze(0).unsqueeze(0)
        
        output = global_CNN_model(tensor)
        _, predicted = torch.max(output, dim=1)
        predictions_califications.append(predicted.item())
        
        
    
    
    os.remove(path_to_calification)
    
    calification = ''.join([str(x) for x in predictions_califications])
    print(str(i) + " " + str(calification))
    
    # Rebuild a decimal grade according to how many boxes were detected.
    if(len(predictions_califications) == 0):
        return ""
    if(len(predictions_califications) == 1):
        return str(predictions_califications[0])
    if(len(predictions_califications) == 2):
        return str(predictions_califications[0]) + "." + str(predictions_califications[1])
    if(len(predictions_califications) == 3):
        return str(predictions_califications[0]) + "."+ str(predictions_califications[1]) + str(predictions_califications[2])
    if(len(predictions_califications) == 4):
        if(predictions_califications[1] >0):
            return str(predictions_califications[1]) + "."+ str(predictions_califications[2]) + str(predictions_califications[3])
        else:
            return float(0)

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
    """
    Petit redressement léger.
    On reste volontairement simple pour ne pas casser ta logique.
    """
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
    """
    Retourne plusieurs variantes binaires de la meme page
    pour augmenter le recall des premieres pages.
    """
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

    # 2) adaptive + petite dilation pour recoller les bords cassés
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

    # 4) canny + fermeture plus forte
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
    Mesures pour accepter / rejeter une case :
    - border_fill_ratio : bords bien présents
    - inner_fill_ratio  : contenu interne non vide
    - corner_fill_ratio : les 4 coins existent bien
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
    Détecte des cases candidates :
    - contour fermé
    - approxPolyDP avec 4 coins
    - dimensions cohérentes
    - bord et coins suffisamment remplis
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

        # en recall mode, on accepte aussi 5 coins si la bounding box est bonne
        if len(approx) not in (4, 5):
            continue

        x, y, w, h = cv.boundingRect(approx)
        if w < 26 or h < 26:
            continue

        ratio = w / float(h)
        if ratio < 0.55 or ratio > 1.75:
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
    """
    Groupe les boxes par ligne horizontale.
    """
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
def filter_row_candidates_by_median_geometry(row):
    if len(row) < 3:
        return row

    widths = np.array([c["rect"][2] for c in row], dtype=np.float32)
    heights = np.array([c["rect"][3] for c in row], dtype=np.float32)

    med_w = float(np.median(widths))
    med_h = float(np.median(heights))

    filtered = []
    for c in row:
        x, y, w, h = c["rect"]

        if w < 0.55 * med_w or h < 0.55 * med_h:
            continue

        if w > 1.45 * med_w or h > 1.45 * med_h:
            continue

        filtered.append(c)

    return filtered


def digit_blob_score(binary_img, rect):
    x, y, w, h = rect

    pad_x = max(2, int(0.12 * w))
    pad_y = max(2, int(0.12 * h))

    x0 = x + pad_x
    y0 = y + pad_y
    x1 = x + w - pad_x
    y1 = y + h - pad_y

    if x1 <= x0 or y1 <= y0:
        return 0.0

    roi = binary_img[y0:y1, x0:x1]
    if roi.size == 0:
        return 0.0

    num_labels, labels, stats, _ = cv.connectedComponentsWithStats(
        (roi > 0).astype(np.uint8), connectivity=8
    )

    areas = []
    H, W = roi.shape[:2]
    roi_area = H * W

    for i in range(1, num_labels):
        area = stats[i, cv.CC_STAT_AREA]
        if area >= 0.01 * roi_area:
            areas.append(area)

    if len(areas) == 0:
        return 0.0

    largest = max(areas) / float(roi_area)
    count_penalty = abs(len(areas) - 1)

    return largest - 0.12 * count_penalty


def filter_digit_like_boxes(binary_img, row):
    out = []
    for c in row:
        blob = digit_blob_score(binary_img, c["rect"])
        c["digit_blob_score"] = blob

        if blob < 0.02:
            continue

        out.append(c)
    return out


def build_regular_dni_grid_from_row(row, expected_slots=9):
    if len(row) < 4:
        return None

    row = sorted(row, key=lambda c: c["rect"][0])

    widths = np.array([c["rect"][2] for c in row], dtype=np.float32)
    heights = np.array([c["rect"][3] for c in row], dtype=np.float32)
    centers_x = np.array([c["rect"][0] + c["rect"][2] / 2.0 for c in row], dtype=np.float32)
    centers_y = np.array([c["rect"][1] + c["rect"][3] / 2.0 for c in row], dtype=np.float32)

    med_w = float(np.median(widths))
    med_h = float(np.median(heights))
    med_cy = float(np.median(centers_y))

    if len(centers_x) >= 2:
        diffs = np.diff(np.sort(centers_x))
        diffs = diffs[diffs > 0]
        if len(diffs) == 0:
            pitch = med_w * 1.05
        else:
            pitch = float(np.median(diffs))
    else:
        pitch = med_w * 1.05

    start_cx = float(np.min(centers_x))

    slots = []
    for i in range(expected_slots):
        cx = start_cx + i * pitch
        x0 = int(round(cx - med_w / 2.0))
        y0 = int(round(med_cy - med_h / 2.0))
        x1 = int(round(cx + med_w / 2.0))
        y1 = int(round(med_cy + med_h / 2.0))
        slots.append((x0, y0, x1, y1))

    return {
        "slots": slots,
        "med_w": med_w,
        "med_h": med_h,
        "pitch": pitch,
        "cy": med_cy,
    }


def assign_candidates_to_grid_slots(row, grid):
    assigned = [None] * len(grid["slots"])
    used = set()

    for slot_idx, slot in enumerate(grid["slots"]):
        sx0, sy0, sx1, sy1 = slot
        scx = (sx0 + sx1) / 2.0
        scy = (sy0 + sy1) / 2.0
        sw = sx1 - sx0
        sh = sy1 - sy0

        best = None
        best_cost = 1e9
        best_idx = None

        for idx, cand in enumerate(row):
            if idx in used:
                continue

            x, y, w, h = cand["rect"]
            ccx = x + w / 2.0
            ccy = y + h / 2.0

            dx = abs(ccx - scx) / max(sw, 1)
            dy = abs(ccy - scy) / max(sh, 1)
            dw = abs(w - sw) / max(sw, 1)
            dh = abs(h - sh) / max(sh, 1)

            cost = dx + dy + 0.6 * dw + 0.6 * dh

            if cost < best_cost:
                best_cost = cost
                best = cand
                best_idx = idx

        if best is not None and best_cost < 1.35:
            assigned[slot_idx] = best["rect"]
            used.add(best_idx)

    return assigned


def fill_missing_slots_from_grid(assigned_slots, grid):
    final_boxes = []
    for idx, rect in enumerate(assigned_slots):
        if rect is None:
            final_boxes.append(grid["slots"][idx])
        else:
            x, y, w, h = rect
            final_boxes.append((x, y, x + w, y + h))
    return final_boxes


def synthetic_anchor_from_first_digit(first_digit_box):
    x0, y0, x1, y1 = first_digit_box
    w = x1 - x0
    gap = max(4, int(0.08 * w))
    return (x0 - gap - w, y0, x0 - gap, y1)


def score_9_digit_window(window):
    """
    Score d'une suite de 8 ou 9 cases DNI.
    Plus la suite est régulière, plus le score est élevé.
    """
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

    # Bonus si on a 9 boxes complètes
    length_bonus = 4.0 if n == 9 else 0.0

    return mean_score * 10.0 - 8.0 * reg_pen + length_bonus


def find_best_9_digit_sequence(rows):
    """
    Cherche la meilleure suite de 9 boxes.
    Si 9 n'est pas possible, accepte une suite de 8 en fallback.
    """
    best = None
    best_score = -1e9

    for row in rows:
        row_len = len(row)

        # priorité aux fenêtres de 9
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

        # fallback : fenêtres de 8 seulement si pas assez de 9
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
    """
    Cherche une ancre a gauche des digits, sans chevauchement.
    Si elle manque, on la reconstruit.
    """
    first_digit = digit_window[0]["rect"]
    fd_x, fd_y, fd_w, fd_h = first_digit
    fd_cy = rect_center(first_digit)[1]

    left_candidates = []
    for cand in row:
        r = cand["rect"]
        x, y, w, h = r
        cy = rect_center(r)[1]
        gap = fd_x - (x + w)

        # strictement a gauche, sans overlap
        if gap < 2:
            continue

        if abs(cy - fd_cy) > 0.35 * max(h, fd_h):
            continue

        if not (0.60 <= w / float(fd_w) <= 1.50):
            continue

        if not (0.60 <= h / float(fd_h) <= 1.50):
            continue

        # l'ancre doit etre la plus proche a gauche
        score = -abs(gap - 4) + 2.0 * cand["metrics"]["border"]
        left_candidates.append((score, cand))

    if left_candidates:
        left_candidates.sort(key=lambda x: x[0], reverse=True)
        return left_candidates[0][1]["rect"], False

    # fallback : ancre synthetique
    synth_gap = max(4, int(0.08 * fd_w))
    anchor_w = fd_w
    anchor_h = fd_h
    anchor_x = max(0, fd_x - synth_gap - anchor_w)
    anchor_y = fd_y
    return (anchor_x, anchor_y, anchor_w, anchor_h), True

def regularize_digit_boxes_no_overlap(digit_rects_xyxy, force_touch=False):
    """
    Rend les 9 boxes régulières et interdit tout overlap.
    On reconstruit la chaîne de gauche à droite.

    force_touch=False  -> petite séparation estimée
    force_touch=True   -> x0(i) = x1(i-1)
    """
    if not digit_rects_xyxy:
        return digit_rects_xyxy

    rects = []
    for r in digit_rects_xyxy:
        x0, y0, x1, y1 = r
        if x1 > x0 and y1 > y0:
            rects.append((int(x0), int(y0), int(x1), int(y1)))

    if len(rects) < 2:
        return rects

    rects = sorted(rects, key=lambda r: r[0])

    widths = [x1 - x0 for x0, y0, x1, y1 in rects]
    heights = [y1 - y0 for x0, y0, x1, y1 in rects]
    y0s = [y0 for x0, y0, x1, y1 in rects]
    y1s = [y1 for x0, y0, x1, y1 in rects]

    med_w = int(round(np.median(widths)))
    med_h = int(round(np.median(heights)))
    med_y0 = int(round(np.median(y0s)))
    med_y1 = med_y0 + med_h

    # gap horizontal médian observé
    gaps = []
    for i in range(len(rects) - 1):
        g = rects[i + 1][0] - rects[i][2]
        if 0 <= g <= 0.35 * med_w:
            gaps.append(g)

    if force_touch:
        med_gap = 0
    else:
        med_gap = int(round(np.median(gaps))) if gaps else 0
        med_gap = max(0, min(med_gap, int(0.15 * med_w)))

    # point de départ = première vraie box
    start_x0 = rects[0][0]

    out = []
    x0 = start_x0
    for _ in range(len(rects)):
        x1 = x0 + med_w
        out.append((int(x0), int(med_y0), int(x1), int(med_y1)))
        x0 = x1 + med_gap

    return out


def detect_dni_chain_on_page(page_number, mode="coords_detect"):
    """
    Détecte :
    - la boxe ancre
    - les 9 boxes du DNI à sa droite
    """
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

        row = best_seq["row"]

        # 1) nettoyage géométrique
        row = filter_row_candidates_by_median_geometry(row)

        # 2) garder seulement les boxes qui ressemblent à un caractère manuscrit
        row = filter_digit_like_boxes(bw, row)

        if len(row) < 4:
            continue

        # 3) grille régulière de 9 cases
        grid = build_regular_dni_grid_from_row(row, expected_slots=9)
        if grid is None:
            continue

        # 4) affectation des candidates à la grille
        assigned = assign_candidates_to_grid_slots(row, grid)

        # 5) complétion des cases manquantes
        digit_rects_xyxy = fill_missing_slots_from_grid(assigned, grid)
        seq_len = sum(1 for x in assigned if x is not None)

        if mode == "page_detect":
            if seq_len < 7:
                continue
            accept_score = best_seq["score"]
        else:
            if seq_len < 8:
                continue
            accept_score = best_seq["score"] + 1.0

        anchor_rect_xyxy = synthetic_anchor_from_first_digit(digit_rects_xyxy[0])

        if accept_score > best_score:
            best_score = accept_score
            best_result = {
                "anchor_rect_xywh": rect_xyxy_to_xywh(anchor_rect_xyxy),
                "anchor_rect_xyxy": anchor_rect_xyxy,
                "digit_rects_xyxy": digit_rects_xyxy[:9],
                "digit_rects_xywh": [rect_xyxy_to_xywh(r) for r in digit_rects_xyxy[:9]],
                "gray_for_ocr": gray_inv,
                "binary_debug": bw,
                "score": accept_score,
                "variant_name": variant_name,
                "synthetic_anchor": True,
                "seq_len": seq_len,
            }

    DNI_CHAIN_CACHE[cache_key] = best_result
    return best_result

def compatible_next_box(prev_rect, next_rect):
    """
    Contraintes entre deux cases successives.
    """
    px, py, pw, ph = prev_rect
    nx, ny, nw, nh = next_rect

    pcx, pcy = rect_center(prev_rect)
    ncx, ncy = rect_center(next_rect)

    gap = nx - (px + pw)   # distance horizontale entre les deux cases

    # même ligne
    if abs(ncy - pcy) > 0.35 * max(ph, nh):
        return False, None

    # tailles proches
    if not (0.65 <= nw / float(pw) <= 1.45):
        return False, None
    if not (0.65 <= nh / float(ph) <= 1.45):
        return False, None

    # position "à côté"
    if gap < -0.20 * pw:
        return False, None
    if gap > 1.00 * pw:
        return False, None

    # score de voisinage : plus petit = meilleur
    y_pen = abs(ncy - pcy) / max(ph, nh)
    w_pen = abs(nw - pw) / max(pw, 1)
    h_pen = abs(nh - ph) / max(ph, 1)
    gap_target = 0.05 * pw
    gap_pen = abs(gap - gap_target) / max(pw, 1)

    chain_cost = y_pen + w_pen + h_pen + gap_pen
    return True, chain_cost

def build_chain_from_seed(candidates, seed_idx, target_len=10):
    """
    Construit une chaîne horizontale de boxes :
    ancre + 9 boxes du DNI.
    """
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

            # bonus si la box ressemble bien à une vraie case
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




# --------------------------------------------------------
# REMPLACEMENT de buscar_inicio_copias()
# --------------------------------------------------------
def buscar_inicio_copias(pages, nbp):
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

            # IMPORTANT: on garde page-XX.png
            # car la suite peut relancer la detection
        else:
            pathToCalificacion = build_dump_path("calification", page)
            if os.path.exists(pathToCalificacion):
                os.remove(pathToCalificacion)

    return pagesConfirmed


def split_in_num_cpu(nbp):
    # Distribute page numbers across CPU buckets to parallelize first-page detection.
    cores = os.cpu_count()
    result = [[] for _ in range(cores)]
    for i in range(1, nbp + 1):
        result[i % cores].append(i)
    return result


# ---------------------------------------------------------------------------
# Wrappers de test (nouveaux) qui utilisent les blocs exacts ci-dessus
# ---------------------------------------------------------------------------
def rename_pdftoppm_outputs_like_main(nbp):
    set_page_num_width(nbp)
    # Normalize pdftoppm outputs to the same padding convention used by main.py.
    for prefix in ["page", "calification"]:
        matches = glob.glob(os.path.join(output_folder, f"{prefix}-*.png"))
        if not matches:
            continue

        parsed = []
        for src in matches:
            name = os.path.basename(src)
            m = re.match(rf"^{re.escape(prefix)}-(\d+)\.png$", name)
            if m:
                parsed.append((int(m.group(1)), src))

        for page_num, src in sorted(parsed, key=lambda x: x[0], reverse=True):
            dst = build_dump_path(prefix, page_num)
            if os.path.abspath(src) != os.path.abspath(dst):
                if os.path.exists(dst):
                    os.remove(dst)
                os.rename(src, dst)


def convert_pdf_like_main():
    total_pages = len(PdfReader(inputPDF).pages)
    set_page_num_width(total_pages)
    numCores = os.cpu_count()
    pages_per_batch = total_pages // numCores
    if(pages_per_batch == 0):
        pages_per_batch = 1

    with ProcessPoolExecutor() as executor:
        futures = []
        for start_page in range(1, total_pages + 1, pages_per_batch):
            end_page = min(start_page + pages_per_batch - 1, total_pages)
            futures.append(executor.submit(convert_pdf_to_images, start_page, end_page, inputPDF, output_folder, total_pages))
            futures.append(executor.submit(convert_pdf_to_images_calification, start_page, end_page, inputPDF, output_folder))
        for future in futures:
            future.result()

    rename_pdftoppm_outputs_like_main(total_pages)
    return total_pages


def detect_first_pages_like_main(nbp):
    set_page_num_width(nbp)
    confirmed_pages = []

    pagesLists = split_in_num_cpu(nbp)

    with ProcessPoolExecutor() as executor:
        futures = []
        for pages in pagesLists:
            futures.append(executor.submit(buscar_inicio_copias, pages, nbp ))
        executor.shutdown(wait=True)
        for future in futures:
            results = future.result()
            if results != None:
                for result in results:
                    confirmed_pages.append((result[1], result[0]))

    confirmed_pages = sorted(confirmed_pages, key=lambda item: item[0])
    ListNumFirstPage = [page for page, coords in confirmed_pages]
    coordsDNI = [coords for page, coords in confirmed_pages]
    return coordsDNI, ListNumFirstPage


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


def predict_dni_from_main_block(j, coordsDNI, ListNumFirstPage, model_path=None):
    if model_path and (trained_model_path != model_path or global_CNN_model is None):
        setup_globals(inputPDF, output_folder, model_path=model_path, examen_name=examen_nombre)
    model = CNN()
    model.load_state_dict(torch.load(trained_model_path, map_location='cpu'))
    model.eval()

    exception_occurred = False
    imgf, pathToDniPage, coords = compute_coords_from_main_block(j, coordsDNI, ListNumFirstPage)

    digits_images=[]

    for l in range(len(coords)):
        
        # Shrink the crop slightly to avoid capturing the box borders.
        box = (coords[l][0][0]+5, coords[l][0][1]+5, coords[l][0][2]-5, coords[l][0][3]-5)
        
        area, crop_adjusted = safe_crop_digit(imgf, box)
        if crop_adjusted:
            exception_occurred = True
        area.save(output_folder + "croping"+str(j)+"-"+str(l)+".png", "PNG")
        
        # Resize every crop to the 28x28 format expected by the CNN.
        image = cv.imread(output_folder + "croping"+str(j)+"-"+str(l)+".png", 1) 
        imResized = cv.resize(image, (28, 28)) 
        cv.imwrite(output_folder + "croping"+str(j)+"-"+str(l)+".png",imResized)
        imResized = Image.open(output_folder + "croping"+str(j)+"-"+str(l)+".png").convert('L')
        
        # Keep the filenames so they can be loaded into the tensor batch below.
        digits_images.append(output_folder + "croping"+str(j)+"-"+str(l)+".png")
    
    # Assemble the 9 normalized digit images into one tensor-friendly matrix.
    M = np.zeros((9,28,28), dtype=int)
    
    for c in range(9):
        imDigits = Image.open(digits_images[c])
        for x in range(28):
            for y in range(28):
                z=imDigits.getpixel((x,y))
                    
                if z[0]<=13:
                    z=0
                elif(z[0]<=51):
                    z=26
                elif(z[0]<=76):
                    z=153
                else:
                    z=254
                M[c,y,x] = z
    
    M_tensorsList = []
    predictions2 = []
    
    for i in range(9) :
        m = M[i]
        tensor = torch.Tensor(m).unsqueeze(0)
        M_tensorsList.append(tensor)
    M_tensors = torch.stack(M_tensorsList)  
    outputs = model(M_tensors)
    predictions2.append(torch.argmax(outputs, dim=1))
    
    predictions2 = torch.stack(predictions2).numpy()
    # The model output is wrapped once, so flatten it back to a simple 9-digit vector.
    predictions2 = predictions2[0]

    prediction_str = ''.join([str(x) for x in predictions2])
    prediction_str = normalize_DNI(prediction_str)

    return {
        "exception_occurred": exception_occurred,
        "pathToDniPage": pathToDniPage,
        "coords": coords,
        "prediction_digits": [int(x) for x in predictions2],
        "prediction_str": prediction_str,
    }
def support_line_below(binary_img, digit_rects):
    """
    Vérifie qu'il existe une longue ligne horizontale sous la rangée du DNI.
    C'est un indice fort d'une vraie première page.
    """
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

    # taux de pixels allumés par ligne
    row_fill = np.mean(roi > 0, axis=1)
    return float(np.max(row_fill))

def score_digit_row_for_page(window, binary_img):
    """
    Score recall pour décider si une page est probablement une première page.
    Ici on privilégie le rappel.
    """
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
    """
    Cherche la meilleure suite de 7 à 9 boxes pour le rappel.
    """
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
    Garantit 9 boxes.
    - 9 -> inchangé
    - 8 -> extrapole la 9e
    - <8 -> retourne tel quel
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

    # si on n'a que 8 boxes après padding raté, on duplique la dernière
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
    """
    Dernier fallback si aucune detection de boxes n'est dispo.
    Reconstruit 9 boxes a droite de l'ancre.
    """
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