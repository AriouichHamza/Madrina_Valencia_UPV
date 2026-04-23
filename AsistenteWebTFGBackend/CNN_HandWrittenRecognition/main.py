#!pip3 install opencv-python
#!pip3 install pypdf2
#!pip3 install pdfplumber
#!pip3 install pdfminer
#!pip3 install textract
#!pip3 install -U matplotlib

#!pip3 install torch
#!pip3 install torchvision
#!pip3 install scikit-learn

#!pip3 install emnist
#!pip3 install tqdm
import multiprocessing
import signal
import glob


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
import logging

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
        
# Flush each line immediately so the caller receives progress updates in real time.
sys.stdout.reconfigure(line_buffering=True)
initial_time = datetime.now()
emitter = Emitter()
current_folder = os.path.abspath(os.path.dirname(__file__))
root_folder = os.path.dirname(current_folder)

# Runtime arguments received from the parent application.
index = sys.argv[1]
examen_nombre = sys.argv[2]
alumnos = json.loads(sys.argv[3])


# The composite index encodes the user, subject, and exam identifiers.
aux = index.split('-')
usuario = aux[0]
asignatura_ID = aux[1]
examen_ID = aux[2]

# Build the main input/output paths used during the OCR pipeline.
examImgsPath = root_folder + "/user_data/" + index + "/"
inputPDF = examImgsPath + examen_nombre + ".pdf"

output_folder = current_folder + "/.img-dumps/"+ index + "/" # we use the current folder to stock the images
trained_model_name = 'exammodel4.pt'
trained_model_path = current_folder +"/"+  trained_model_name

PAGE_NUM_WIDTH = 1

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
    
# Create the temporary dump folder used to store page crops and intermediate images.
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    

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


# Split the PDF conversion work across available CPU cores.
total_pages = len(PdfReader(inputPDF).pages)
set_page_num_width(total_pages)
numCores = os.cpu_count()
pages_per_batch = total_pages // numCores
if(pages_per_batch == 0):
    pages_per_batch = 1

emitter.emit_progress(0, "Convirtiendo PDF a imagenes")

# Convert full-page DNI regions and grade regions in parallel for faster preprocessing.
with ProcessPoolExecutor() as executor:
    futures = []
    for start_page in range(1, total_pages + 1, pages_per_batch):
        end_page = min(start_page + pages_per_batch - 1, total_pages)
        futures.append(executor.submit(convert_pdf_to_images, start_page, end_page, inputPDF, output_folder, total_pages))
        futures.append(executor.submit(convert_pdf_to_images_calification, start_page, end_page, inputPDF, output_folder))

        # Wait for all the futures to complete.
    for future in futures:
        future.result()


emitter.emit_progress(100, "Conversion de PDF a imagenes completada")


# Load one shared model instance used to read the handwritten grade digits.
global_CNN_model = CNN()
global_CNN_model.load_state_dict(torch.load(trained_model_path))

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

def buscar_inicio_copias(pages, nbp):
    # Detect which pages are the first page of a student's copy by locating the DNI template box.
    
    pagesConfirmed = []
    for page in pages:
        # Emit integer progress updates while scanning the rendered page images.
        progress = int((page + 1) / nbp * 100) -1
        emitter.emit_progress(progress, "Buscando DNIs en páginas")
        # Open the rendered page image.
        pathToImg = build_dump_path("page", page)

        #print(pathToImg)
        img = Image.open(pathToImg)

        (largeur_image, hauteur_image) = img.size

        # Convert the page to grayscale pixel-by-pixel before inverting it for template detection.
        for y in range(hauteur_image):
            for x in range(largeur_image):
                r,v,b=img.getpixel((x,y)) 
                n_r=r*0.299
                n_v=v*0.587
                n_b=b*0.114
                gray=int(n_b+n_v+n_r)
                img.putpixel((x,y),(gray,gray,gray))
        aux_img = build_dump_path("aux", page)
        img.save(aux_img)        
        image = cv.imread(aux_img)

        # Invert the page so the form lines become bright and easier to detect.
        whiteonblackdata=cv.bitwise_not(image) 
        cv.imwrite(aux_img,whiteonblackdata) 

        imgf = Image.open(aux_img).convert('L') # to obtain only 1 grey channel    


        # Detect whether the expected DNI frame exists on this page.

        k=0
        max_h_1=0
        min_h_1=0
        max_l_1=0
        min_l_1=0


        x=280
        for y in range(300,200,-1):  # Scan upward to find the top horizontal border.
            z=imgf.getpixel((x,y))
            if z>150:
                for xb in range(x,x+50): 
                    if z>150:
                        k=k+1
                        if k==25:
                            min_h_1=y
                        else:
                            k=k
        k=0
        for y in range(310,400):  # Scan downward to find the bottom horizontal border.
            z=imgf.getpixel((x,y))
            if z>150:
                for xb in range(x,x+50):
                    if z>150:
                        k=k+1
                        if k==25:
                            max_h_1=y
                        else:
                            k=k
        #print("min_h_1=",min_h_1," max_h_1=",max_h_1)

        k=0  
        y=min_h_1+10
        for x in range(300,210,-1): # Scan leftward to find the right vertical border.
            z=imgf.getpixel((x,y))
            if z>150:
                for yb in range(y,y+40): 
                    if z>150:
                        k=k+1
                        if k==20:
                            min_l_1=x
                        else:
                            k=k
        k=0
        for x in range(430,370,-1): # Scan leftward to find the left vertical border.
            z=imgf.getpixel((x,y))
            if z>150:
                for yb in range(y,y+40):
                    if z>150:
                        k=k+1
                        if k==20:
                            max_l_1=x
                        else:
                            k=k
        #print("min_l_1=",min_l_1," max_l_1=",max_l_1)

        if min_l_1!=0:
            
            # Keep only pages confirmed as first pages; temporary renders can be discarded.
            os.remove(pathToImg)
            
            newPath = build_dump_path("DNIpage", page)
            imgf.save(newPath)
            newPage = [(min_l_1, min_h_1, max_l_1, max_h_1), page ]
            pagesConfirmed.append(newPage)
        else:
            # Non-matching pages will never be used again, so remove their grade crop as well.
            pathToCalificacion = build_dump_path("calification", page)
            os.remove(pathToCalificacion)
        
        os.remove(aux_img)
    return pagesConfirmed


    
    
def split_in_num_cpu(nbp):
    # Distribute page numbers across CPU buckets to parallelize first-page detection.
    cores = os.cpu_count()
    result = [[] for _ in range(cores)]
    for i in range(1, nbp + 1):
        result[i % cores].append(i)
    return result

def main():
    # Main pipeline:
    # 1. locate the first page of each student's copy,
    # 2. crop the 9 DNI digits,
    # 3. classify them with the CNN,
    # 4. match the OCR result against the known student list,
    # 5. read the handwritten grade and emit the result.
    
    numErrorsGlobal = 0
    Output = []
    L=[]
    
    nbStudent = 1  # Increase a variable number of students
    confirmed_pages = []
    

    # Preserve the original CSV-like structure even if the current flow emits JSON events.
    Output.append(['DNI', 'Name', 'Surname', 'First page', 'Last page'])
    
    # Keep a lightweight local roster for fuzzy DNI matching after OCR.
    for alumno in alumnos:
        L.append([alumno["dni"], alumno["nombre"], alumno["apellidos"]])
    
    
    pathToImg = ""
    
    pdfFileObj = open(inputPDF, 'rb')
    pdfReader = PyPDF2.PdfReader(pdfFileObj)
    nbp = len(pdfReader.pages)
    set_page_num_width(nbp)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Número de páginas: %s", nbp)

    
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
        
    # Once the first pages are known, each interval between two starts belongs to one student.
    confirmed_pages = sorted(confirmed_pages, key=lambda item: item[0])
    ListNumFirstPage = [page for page, coords in confirmed_pages]
    coordsDNI = [coords for page, coords in confirmed_pages]
    nbStudent = len(ListNumFirstPage)
    
    for j in range(1, nbStudent+1):
        try :
            exception_occurred = False
            
            # Store the crop rectangle for each of the 9 DNI digit boxes.
            coords = np.zeros((9, 1, 4), dtype=int)
            k=0
            max_h=0
            min_h=0
            max_l=0
            min_l=0
            
            pathToDniPage = build_dump_path("DNIpage", ListNumFirstPage[j-1])
            
            imgf = Image.open(pathToDniPage).convert('L')
            # Detect the first digit box using the anchor box found on the template.
            x= coordsDNI[j-1][2]+10    
            for y in range(290,210,-1):
                z=imgf.getpixel((x,y))
                if z>100:
                    for xb in range(x,x+50):
                        if z>100:
                            k=k+1
                            if k==25:
                                min_h=y
                            else:
                                k=k
            k=0
            for y in range(350,400):
                z=imgf.getpixel((x,y))
                if z>100:
                    for xb in range(x,x+50):
                        if z>100:
                            k=k+1
                            if k==25:
                                max_h=y
                            else:
                                k=k

            k=0  
            y=min_h+10
            for x in range(430,370,-1):
                z=imgf.getpixel((x,y))
                if z>100:
                    for yb in range(y,y+40):
                        if z>100:
                            k=k+1
                            if k==20:
                                min_l=x
                            else:
                                k=k
            k=0
            for x in range(540,480,-1):
                z=imgf.getpixel((x,y))
                if z>100:
                    for yb in range(y,y+40):
                        if z>100:
                            k=k+1
                            if k==20:
                                max_l=x
                            else:
                                k=k
        
            if min_l != 0:
                coords[0][0][0]= min_l
            else :
                coords[0][0][0] = coordsDNI[j-1][2] # =max_l_1
            if min_h != 0:
                coords[0][0][1]= min_h
            else :
                coords[0][0][1]= coordsDNI[j-1][1] #=min_h_1
            if max_l != 0:
                coords[0][0][2]= max_l
            else :
                coords[0][0][2]= coordsDNI[j-1][2] +140 #=max_l_1 + 140
            if max_h !=0 :
                coords[0][0][3]= max_h
            else :
                coords[0][0][3]= coordsDNI[j-1][3] #=max_h_1
        
            
            # Infer the remaining 8 boxes by walking right from the previous box.
            for d in range(1, len(coords)) :

                x= coords[d-1][0][0]+10
                for y in range(coords[d-1][0][1]+10,coords[d-1][0][1]-10,-1):
                    z=imgf.getpixel((x,y))
                    if z>100:
                        for xb in range(x,x+50):
                            if z>100:
                                k=k+1
                                if k==25:
                                    min_h=y
                                else:
                                    k=k
                k=0
                for y in range(coords[d-1][0][3]-10,coords[d-1][0][3]+10):
                    z=imgf.getpixel((x,y))
                    if z>100:
                        for xb in range(x,x+50):
                            if z>100:
                                k=k+1
                                if k==25:
                                    max_h=y
                                else:
                                    k=k

                k=0  
                y=min_h+10
                for x in range(coords[d-1][0][2]+10,coords[d-1][0][2]-10,-1):
                    z=imgf.getpixel((x,y))
                    if z>100:
                        for yb in range(y,y+40):
                            if z>100:
                                k=k+1
                                if k==20:
                                    min_l=x
                                else:
                                    k=k
                k=0
                for x in range(coords[d-1][0][2]+130,coords[d-1][0][2]+90,-1):
                    z=imgf.getpixel((x,y))
                    if z>100:
                        for yb in range(y,y+40):
                            if z>100:
                                k=k+1
                                if k==20:
                                    max_l=x
                                else:
                                    k=k
        
                if min_l != 0 :
                    coords[d][0][0]= min_l
                else :
                    coords[d][0][0]= coords[d-1][0][2]
                if min_h != 0 :
                    coords[d][0][1]= min_h
                else :
                    coords[d][0][1]= coords[d-1][0][1]
                if max_l !=0 :
                    coords[d][0][2]= max_l
                else :
                    coords[d][0][2]= coords[d][0][0]+104
                if max_h !=0 :
                    coords[d][0][3]= max_h
                else : 
                    coords[d][0][3]= coords[d-1][0][3]

                
        
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
            # Load a fresh model inside the worker flow used for DNI recognition.
            model = CNN()
            model.load_state_dict(torch.load(trained_model_path))
            
            
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
            
            # Delete temporary crops as soon as the prediction batch is complete.
            os.remove(pathToDniPage)
            for digit in range(len(coords)):
                os.remove(output_folder + "croping"+str(j)+"-"+str(digit)+".png")
            
            max_ratio = 0
            best_match = None
            prediction_str = ''.join([str(x) for x in predictions2])
            
            prediction_str = normalize_DNI(prediction_str)
            # Match the OCR output against the known roster using edit distance.
            for DNI_index in range(len(L)):
                DNI_str = normalize_DNI(L[DNI_index][0])
                
                distance = Levenshtein.distance(DNI_str, prediction_str)
                ratio = 1 - (distance / max(len(DNI_str), len(prediction_str)))
                
                if(ratio > max_ratio):
                    max_ratio = ratio
                    best_match = DNI_index

            # Build the final page interval assigned to the matched student.
            Line = copy.deepcopy(L[best_match])
            Line.append(str(ListNumFirstPage[j-1]))
            if j < nbStudent :
                Line.append(str(ListNumFirstPage[j]-1))
            else :
                Line.append(str(nbp))

            if exception_occurred :
                LineBis = ['','','']
                LineBis.append(str(ListNumFirstPage[j-1]))
                if j < nbStudent:
                    LineBis.append(str(ListNumFirstPage[j]-1))
                else :
                    LineBis.append(str(nbp))
                Output.append(LineBis)
            else :
                # Final step: detect and sanitize the grade before emitting the result.
                calificacion = detec_calification(ListNumFirstPage[j-1])
                if calificacion == "":
                    calificacion = 0.0
                else: 
                    calificacion = float(calificacion)
                    # Grades outside the expected range are treated as invalid OCR noise.
                    if calificacion < 0 or calificacion > 10:
                        calificacion = 0.0
 
                print(Line )
                emitter.emit_student(Alumno(asignatura_ID, examen_ID, Line[0], Line[1], Line[2], Line[3], Line[4], calificacion))
        except Exception as ex:
            print(ex)
            numErrorsGlobal += 1
            # Even on failure, try to salvage the grade and emit a placeholder student entry.
            calificacion = detec_calification(ListNumFirstPage[j-1])
            if calificacion == "":
                calificacion = 0.0
            else: 
                calificacion = float(calificacion)
                if calificacion < 0 or calificacion > 10:
                    calificacion = 0.0
            print("Error in student ", j)
            if j < nbStudent :
                fin_pag = ListNumFirstPage[j]-1
            else :
                fin_pag = nbp
            emitter.emit_student(Alumno(asignatura_ID, examen_ID, "Err"+str(numErrorsGlobal),"Err"+str(numErrorsGlobal), "Err"+str(numErrorsGlobal), ListNumFirstPage[j-1], fin_pag, calificacion))
        


main()
emitter.emit_done(datetime.now() - initial_time) 
# Remove the temporary working directory created for intermediate images.
shutil.rmtree(output_folder)
