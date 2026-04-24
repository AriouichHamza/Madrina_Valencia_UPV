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
    if union <= 0:
        return 0.0
    return inter / union

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

def preprocess_dni_page_from_path(path_to_img):
    """
    Retourne :
    - gray_inv : image grayscale inversée, compatible avec la logique OCR actuelle
    - bw       : image binaire pour la détection des boxes
    """
    img = cv.imread(path_to_img, cv.IMREAD_COLOR)
    if img is None:
        return None, None

    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

    # Même esprit que ton code actuel : inversion pour avoir traits / texte en blanc
    gray_inv = cv.bitwise_not(gray)

    # léger deskew
    gray_inv = light_deskew(gray_inv)

    # binarisation robuste
    blur = cv.GaussianBlur(gray_inv, (3, 3), 0)
    bw = cv.adaptiveThreshold(
        blur,
        255,
        cv.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv.THRESH_BINARY,
        31,
        -5
    )

    # fermeture morphologique pour reconnecter les bords des cases
    kernel = cv.getStructuringElement(cv.MORPH_RECT, (3, 3))
    bw = cv.morphologyEx(bw, cv.MORPH_CLOSE, kernel, iterations=1)

    return gray_inv, bw

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
        return {
            "border_fill_ratio": 0.0,
            "inner_fill_ratio": 0.0,
            "corner_fill_ratio": 0.0
        }

    t = max(2, int(min(w, h) * 0.12))

    border_mask = np.ones_like(roi, dtype=np.uint8)
    if h > 2 * t and w > 2 * t:
        border_mask[t:h-t, t:w-t] = 0

    inner_mask = 1 - border_mask

    border_pixels = roi[border_mask == 1]
    inner_pixels = roi[inner_mask == 1]

    border_fill_ratio = float(np.mean(border_pixels > 0)) if border_pixels.size else 0.0
    inner_fill_ratio = float(np.mean(inner_pixels > 0)) if inner_pixels.size else 0.0

    p = max(2, int(min(w, h) * 0.16))
    corners = [
        roi[0:p, 0:p],
        roi[0:p, max(0, w-p):w],
        roi[max(0, h-p):h, 0:p],
        roi[max(0, h-p):h, max(0, w-p):w],
    ]
    corner_fill_ratio = float(np.mean([np.mean(c > 0) for c in corners if c.size > 0])) if corners else 0.0

    return {
        "border_fill_ratio": border_fill_ratio,
        "inner_fill_ratio": inner_fill_ratio,
        "corner_fill_ratio": corner_fill_ratio,
    }

def detect_box_candidates(binary_img):
    """
    Détecte des cases candidates :
    - contour fermé
    - approxPolyDP avec 4 coins
    - dimensions cohérentes
    - bord et coins suffisamment remplis
    """
    contours, _ = cv.findContours(binary_img, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE)
    H, W = binary_img.shape[:2]

    candidates = []
    img_area = H * W

    for cnt in contours:
        area = cv.contourArea(cnt)
        if area < 1200 or area > img_area * 0.08:
            continue

        peri = cv.arcLength(cnt, True)
        approx = cv.approxPolyDP(cnt, 0.03 * peri, True)

        if len(approx) != 4:
            continue

        pts = order_points_clockwise(approx.reshape(-1, 2))
        x, y, w, h = cv.boundingRect(pts.astype(np.int32))

        if w < 25 or h < 25:
            continue

        ratio = w / float(h)
        if ratio < 0.45 or ratio > 2.20:
            continue

        metrics = box_metrics(binary_img, (x, y, w, h))

        # Coins présents + bords visibles + minimum de contenu interne
        if metrics["corner_fill_ratio"] < 0.05:
            continue
        if metrics["border_fill_ratio"] < 0.12:
            continue
        if metrics["inner_fill_ratio"] < 0.005:
            continue

        score = (
            2.2 * metrics["corner_fill_ratio"] +
            2.8 * metrics["border_fill_ratio"] +
            1.0 * metrics["inner_fill_ratio"]
        )

        candidates.append({
            "rect": (x, y, w, h),
            "metrics": metrics,
            "score": score,
        })

    # déduplication des rectangles qui se recouvrent trop
    candidates = sorted(candidates, key=lambda d: d["score"], reverse=True)
    filtered = []
    for cand in candidates:
        keep = True
        for kept in filtered:
            if rect_iou(cand["rect"], kept["rect"]) > 0.65:
                keep = False
                break
        if keep:
            filtered.append(cand)

    # tri gauche -> droite
    filtered = sorted(filtered, key=lambda d: (d["rect"][1], d["rect"][0]))
    return filtered

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

def detect_dni_chain_on_page(page_number):
    """
    Détecte :
    - la boxe ancre
    - les 9 boxes du DNI à sa droite
    """
    global DNI_CHAIN_CACHE

    if page_number in DNI_CHAIN_CACHE:
        return DNI_CHAIN_CACHE[page_number]

    path_to_img = build_dump_path("page", page_number)
    gray_inv, bw = preprocess_dni_page_from_path(path_to_img)

    if gray_inv is None or bw is None:
        DNI_CHAIN_CACHE[page_number] = None
        return None

    candidates = detect_box_candidates(bw)
    if len(candidates) < 9:
        DNI_CHAIN_CACHE[page_number] = None
        return None

    best_chain = None
    best_score = -1e9

    # on cherche idéalement 10 boxes : 1 ancre + 9 boxes de DNI
    for seed_idx in range(len(candidates)):
        chain = build_chain_from_seed(candidates, seed_idx, target_len=10)
        score = chain_global_score(chain)

        if score > best_score:
            best_score = score
            best_chain = chain

    if best_chain is None:
        DNI_CHAIN_CACHE[page_number] = None
        return None

    # cas 1 : on a bien 10 boxes -> ancre + 9 cases
    if len(best_chain) >= 10:
        best_chain = best_chain[:10]
        anchor = best_chain[0]["rect"]
        digit_rects = [c["rect"] for c in best_chain[1:10]]
    # cas 2 : fallback si on n’a que 9 boxes cohérentes
    elif len(best_chain) == 9:
        anchor = best_chain[0]["rect"]
        digit_rects = [c["rect"] for c in best_chain[:9]]
    else:
        DNI_CHAIN_CACHE[page_number] = None
        return None

    result = {
        "anchor_rect_xywh": anchor,
        "anchor_rect_xyxy": rect_xywh_to_xyxy(anchor),
        "digit_rects_xywh": digit_rects,
        "digit_rects_xyxy": [rect_xywh_to_xyxy(r) for r in digit_rects],
        "gray_for_ocr": gray_inv,
        "binary_debug": bw,
        "all_chain_xywh": [c["rect"] for c in best_chain],
    }

    DNI_CHAIN_CACHE[page_number] = result
    return result


# --------------------------------------------------------
# REMPLACEMENT de buscar_inicio_copias()
# --------------------------------------------------------
def buscar_inicio_copias(pages, nbp):
    pagesConfirmed = []

    for page in pages:
        progress = int((page + 1) / nbp * 100) - 1
        emitter.emit_progress(progress, "Buscando DNIs en páginas")

        detection = detect_dni_chain_on_page(page)

        if detection is not None:
            # On sauvegarde une version grayscale inversée pour rester
            # compatible avec la suite OCR actuelle.
            path_dni_page = build_dump_path("DNIpage", page)
            Image.fromarray(detection["gray_for_ocr"]).save(path_dni_page)

            anchor_rect = detection["anchor_rect_xyxy"]
            newPage = [anchor_rect, page]
            pagesConfirmed.append(newPage)

            # on peut supprimer l’image page originale si tu veux conserver
            # la même logique que ton code initial
            #pathToImg = build_dump_path("page", page)
            #if os.path.exists(pathToImg):
            #    os.remove(pathToImg)
            pass
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

    detection = detect_dni_chain_on_page(page_number)
    if detection is None:
        page_path = build_dump_path("page", page_number)
        dni_path = build_dump_path("DNIpage", page_number)
        raise RuntimeError(
            f"Aucune chaîne DNI détectée pour la page {page_number}. "
            f"page_exists={os.path.exists(page_path)} "
            f"dni_exists={os.path.exists(dni_path)}"
        )

    pathToDniPage = build_dump_path("DNIpage", page_number)
    if not os.path.exists(pathToDniPage):
        Image.fromarray(detection["gray_for_ocr"]).save(pathToDniPage)

    imgf = Image.open(pathToDniPage).convert("L")

    coords = np.zeros((9, 1, 4), dtype=int)

    for idx, box in enumerate(detection["digit_rects_xyxy"][:9]):
        x0, y0, x1, y1 = box
        coords[idx][0][0] = int(x0)
        coords[idx][0][1] = int(y0)
        coords[idx][0][2] = int(x1)
        coords[idx][0][3] = int(y1)

    return imgf, pathToDniPage, coords


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
