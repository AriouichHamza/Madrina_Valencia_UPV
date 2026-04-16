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
    def emit_progress(self, progress, state):
        sys.stdout.write(f"progress {progress} {state}\n")
        
    def emit_done(self, time_elapsed):
        sys.stdout.write(f"done {time_elapsed}\n")
        
    def emit_student(self, alumno : Alumno):
        sys.stdout.write(f"new-calificado {alumno.to_json()}\n")
        

    
def normalize_DNI(dni):
    return dni.lstrip('0')
        
sys.stdout.reconfigure(line_buffering=True) #Para no esperar al buffer y recibir respuestas en tiempo real
initial_time = datetime.now()
emitter = Emitter()
current_folder = os.path.abspath(os.path.dirname(__file__))
root_folder = os.path.dirname(current_folder)

#Argumentos 
index = sys.argv[1]
examen_nombre = sys.argv[2]
alumnos = json.loads(sys.argv[3])


#Split datos examen

aux = index.split('-')
usuario = aux[0]
asignatura_ID = aux[1]
examen_ID = aux[2]

#transform into absolute path

examImgsPath = root_folder + "/user_data/" + index + "/"
inputPDF = examImgsPath + examen_nombre + ".pdf"

output_folder = current_folder + "/.img-dumps/"+ index + "/" # we use the current folder to stock the images
trained_model_name = 'exammodel4.pt'
trained_model_path = current_folder +"/"+  trained_model_name

# Définition of CNN by a class

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
    


#Crear la carpeta si no existe
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    

# Function to convert the pdf into images
# Command to execute
def convert_pdf_to_images(start_page, end_page, input_pdf, output_folder, total_pages):
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


total_pages = len(PdfReader(inputPDF).pages)
numCores = os.cpu_count()
pages_per_batch = total_pages // numCores
if(pages_per_batch == 0):
    pages_per_batch = 1

emitter.emit_progress(0, "Convirtiendo PDF a imagenes")

#Paralelizacion de la conversion de las paginas del PDF a imagenes
with ProcessPoolExecutor() as executor:
    futures = []
    for start_page in range(1, total_pages + 1, pages_per_batch):
        end_page = min(start_page + pages_per_batch - 1, total_pages)
        futures.append(executor.submit(convert_pdf_to_images, start_page, end_page, inputPDF, output_folder, total_pages))
        futures.append(executor.submit(convert_pdf_to_images_calification, start_page, end_page, inputPDF, output_folder))

        # Wait for all the futures to complete
    for future in futures:
        future.result()


emitter.emit_progress(100, "Conversion de PDF a imagenes completada")


global_CNN_model = CNN() #create another instance of the model to charge our trained model
global_CNN_model.load_state_dict(torch.load(trained_model_path)) # charge the trained saved model

def remove_margin_all(img, margin = 0.05):
    h, w = img.shape[:2]
    
    margin_h = int(h * margin)
    margin_w = int(w * margin)
    borderless_img = img[margin_h:h - margin_h, margin_w:w - margin_w]
    return borderless_img
    
    
def is_square(contour, tolerance = 0.05):
    x, y, w, h = cv.boundingRect(contour)
    ratio = w / h
    #Ratio entre [1-tolerance, 1+tolerance] para comprobar que tenga las proporciones de un cuadrado
    if not ( 1- tolerance <= ratio <= 1 + tolerance):
        return False
    #Comprobar si es lo suficientemente grande
    area = cv.contourArea(contour)
    #print("AREA " + str(area))
    if area < 900:
        return False
    #Aproximacion a poligono
    peri = cv.arcLength(contour, True)
    approx = cv.approxPolyDP(contour, 0.04 * peri, True)
    return len(approx) == 4 #Si es un cuadrado, tendra 4 vertices


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
    img = transform(img)
    img = img.unsqueeze(0)
    return img

    
def detec_calification(numPage):
    
    if numPage < 10:
        path_to_calification = output_folder + "calification-0" + str(numPage) + ".png"
    else:
        path_to_calification = output_folder + "calification-" + str(numPage) + ".png"
    
    img = Image.open(path_to_calification)
    #deberia asumir que si hay calificacion pues hay nombre? Y si no hay nombre pero si calificacion por una mala prediccion?
    
    img_grey = cv.cvtColor(np.array(img), cv.COLOR_BGR2GRAY)
    #cv.imwrite(output_folder + "calification-grey-1-" + str(numPage) + ".png", img_grey)
    blur = cv.GaussianBlur(img_grey, (5, 5), 0)
    #cv.imwrite(output_folder + "calification-blur-1-" + str(numPage) + ".png", blur)
    img_edge = cv.Canny(blur, 30, 200, 1)
    #cv.imwrite(output_folder + "calification-edge-1-" + str(numPage) + ".png", img_edge)
    #Para cerrar posibles huecos en los bordes
    kernel = cv.getStructuringElement(cv.MORPH_RECT, (3, 3))
    closed = cv.morphologyEx(img_edge, cv.MORPH_CLOSE, kernel)
    
    #cv.imwrite(output_folder + "calification-edge-closed" + str(numPage) + ".png", closed)
    
    contours, _ = cv.findContours(closed, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)
    crop_califications_list = []
    
    square_contours = []
    for i, contour in enumerate(contours):
        if is_square(contour):
            square_contours.append(contour) #Añadir a la lista de cuadrados
            
    square_contours = sorted(square_contours, key = lambda contour: cv.boundingRect(contour)[0] ) 
    
    
    for i, contour in enumerate(square_contours):
        x, y, w, h = cv.boundingRect(contour)
        
        #print(str(numPage) + " and contour " + str(i) + " is square")
        pathToClean = output_folder + "clean1-" + str(numPage) + "-" + str(i) + ".png"
        
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
    
        #empty_threshold = 0.002  # Porcentaje de píxeles no blancos permitido
        print("White pixels: " + str(white_pixels) + " Total pixels: " + str(total_pixels) + " = " + str(white_pixels/total_pixels)+ "  Page: " + str(numPage) + "  Contour: " + str(i))
        if white_pixels == total_pixels:
            print("Empty image")
            continue
        
        img_auxCV = cv.resize(img_auxCV, (28, 28))
        
        img_auxCV = cv.bitwise_not(img_auxCV)
        
        cv.imwrite(output_folder + "final-cut" + str(numPage) +"-"  + str(i) + ".png", img_auxCV)
        #os.remove(pathToClean)
        imgf = Image.open(output_folder + "final-cut" + str(numPage) +"-"  + str(i) + ".png").convert('L')
        
        crop_califications_list.append(imgf)
        continue


    predictions_califications = []
    for i, crop_calification in enumerate(crop_califications_list):
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
                
        #tensor = transform_to_Tensor(M).unsqueeze(0)
        #tensor = torch.Tensor(crop_calification).unsqueeze(0)
        tensor = torch.Tensor(M).unsqueeze(0).unsqueeze(0)
        
        output = global_CNN_model(tensor)
        _, predicted = torch.max(output, dim=1)
        predictions_califications.append(predicted.item())
        
        
    
    
    os.remove(path_to_calification)#removing all the unnecessary image from the computer memory
    
    calification = ''.join([str(x) for x in predictions_califications])
    print(str(i) + " " + str(calification))
    
    if(len(predictions_califications) == 0): #
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
    
    pagesConfirmed = []
    for page in pages:
        #porcentaje sin coma flotante, solo enteros
        progress = int((page + 1) / nbp * 100) -1
        emitter.emit_progress(progress, "Buscando DNIs en páginas")
        # Open the associate page at PNG format
        if nbp>9 and page<10:
            pathToImg = output_folder + "page-0"+ str(page) + ".png"
        else :
            pathToImg = output_folder + "page-"+str(page) + ".png"

        #print(pathToImg)
        img = Image.open(pathToImg)

        #define the size of the area with the digits
        (largeur_image, hauteur_image) = img.size

        # Transform RGB format to gray scale
        for y in range(hauteur_image):
            for x in range(largeur_image):
                r,v,b=img.getpixel((x,y)) 
                #0.299(red) + 0.587(green) + 0.114(blue) are values to obtain a greyscale 
                n_r=r*0.299
                n_v=v*0.587
                n_b=b*0.114
                gray=int(n_b+n_v+n_r)
                img.putpixel((x,y),(gray,gray,gray))
        aux_img = output_folder + examen_nombre +"-" + str(page) + "-aux.png"
        img.save(aux_img)        
        image = cv.imread(aux_img)

        #transforming the image in a greyscale image with dark background
        whiteonblackdata=cv.bitwise_not(image) 
        cv.imwrite(aux_img,whiteonblackdata) 

        imgf = Image.open(aux_img).convert('L') # to obtain only 1 grey channel    


        # DETECT IF IT IS AN ID PAGE OR NOT

        k=0
        max_h_1=0
        min_h_1=0
        max_l_1=0
        min_l_1=0


        x=280
        for y in range(300,200,-1):  # To detect y-coordinate of the horizontal line upper
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
        for y in range(310,400):  # To detect y-coordinate of the horizontal line bottom
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
        for x in range(300,210,-1): # To detect x-coordinate of the vertical line right
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
        for x in range(430,370,-1): # To detect x-coordinate of the vertical line left
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

        if min_l_1!=0: # If the coordinates are detected, we save the image
            
            os.remove(pathToImg) #removing all the unnecessary image from the computer memory
            
            newPath = output_folder + "DNIpage-"+ str(page) +".png" 
            imgf.save(newPath)
            newPage = [(min_l_1, min_h_1, max_l_1, max_h_1), page ]
            pagesConfirmed.append(newPage)
            #coordsDNI.append([min_l_1, min_h_1, max_l_1, max_h_1, page ])
            #ListNumFirstPage.append(page)
        # If the coordinates are not detected, we remove the image
        else:
            pathToCalificacion = ""
            if(page < 10):
                pathToCalificacion = output_folder + "calification-0" + str(page) + ".png"
            else:
                pathToCalificacion = output_folder + "calification-" + str(page) + ".png"
            os.remove(pathToCalificacion)
        
        os.remove(aux_img)
        #os.remove(pathToImg) #removing all the unnecessary image from the computer memory 
    return pagesConfirmed


    
    
def split_in_num_cpu(nbp):
    cores = os.cpu_count()
    result = [[] for _ in range(cores)]
    for i in range(1, nbp + 1):
        result[i % cores].append(i)
    return result

def main():
    
    numErrorsGlobal = 0
    Output = []
    L=[]
    
    nbStudent = 1  # Increase a variable number of students
    coordsDNI = [] # Create a list to stock the coordinates of the DNI
    ListNumFirstPage = [] # Create a list to stock the number of the first page of the student
    

    # Add the titles line of the csv file
    Output.append(['DNI', 'Name', 'Surname', 'First page', 'Last page'])
    
    for alumno in alumnos:
        L.append([alumno["dni"], alumno["nombre"], alumno["apellidos"]])
    
    
    pathToImg = ""
    
    pdfFileObj = open(inputPDF, 'rb')
    pdfReader = PyPDF2.PdfReader(pdfFileObj)
    nbp = len(pdfReader.pages) #Se puede sacar tambien del numero de archivos .jpg que haya en la carpeta de imagenes

    
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
                    coordsDNI.append(result[0])
                    ListNumFirstPage.append(result[1])
        
    nbStudent = len(ListNumFirstPage)
    
    ListNumFirstPage = sorted(ListNumFirstPage)
    
    for j in range(1, nbStudent+1):
        try :
            exception_occurred = False
            
            coords = np.zeros((9, 1, 4), dtype=int) #Create a matrix to stock coordinates of the boxes
            k=0
            max_h=0
            min_h=0
            max_l=0
            min_l=0
            
            pathToDniPage =output_folder + "DNIpage-"+str(ListNumFirstPage[j-1])+".png"
            
            imgf = Image.open(pathToDniPage).convert('L')
            #actually testing to know the exact coordinates of where to crop the digits
            # For the first digit box    
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
        
            #print("case1 : min_l=",min_l," max_l=",max_l)
 

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
        
            
    # For the second digit box to the ninth one
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

                #print("case", d+1, ": min_h=",min_h," max_h=",max_h)

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
        
                #print("case", d+1, ":min_l=",min_l," max_l=",max_l)
        
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
                
                # Create Box
                box = (coords[l][0][0]+5, coords[l][0][1]+5, coords[l][0][2]-5, coords[l][0][3]-5)
                #print(box)
                
                # Crop Image
                try :
                    area = imgf.crop(box) #actually cutting the digits
                except :
                    area = Image.new('L', (28, 28), 0)
                    exception_occurred = True
                #visualizar imagen
                #area.show()
                area.save(output_folder + "croping"+str(j)+"-"+str(l)+".png", "PNG") # Save Image
                
                # Resize image into EMNIST size
                image = cv.imread(output_folder + "croping"+str(j)+"-"+str(l)+".png", 1) 
                imResized = cv.resize(image, (28, 28)) 
                cv.imwrite(output_folder + "croping"+str(j)+"-"+str(l)+".png",imResized)
                imResized = Image.open(output_folder + "croping"+str(j)+"-"+str(l)+".png").convert('L')
                
                #Fill the list of crop digits
                digits_images.append(output_folder + "croping"+str(j)+"-"+str(l)+".png")
            
            # Creating the matrix 9x28x28
            M = np.zeros((9,28,28), dtype=int)
            
            #fig, ax = plt.subplots(nrows=1, ncols=9, figsize=(10, 2))
            #For each digit 
            for c in range(9):   #arranging the value of pixel for each digit of the current student
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
                #ax[c].imshow(M[c], cmap='gray')
            #plt.tight_layout()
            #plt.show()   #showing
        
        
            #print(M.shape)
            model = CNN() #create another instance of the model to charge our trained model
            model.load_state_dict(torch.load(trained_model_path)) # charge the trained saved model
            
            
            M_tensorsList = []
            predictions2 = []
            
            for i in range(9) :
                m = M[i]
                tensor = torch.Tensor(m).unsqueeze(0)
                M_tensorsList.append(tensor)
            M_tensors = torch.stack(M_tensorsList)  
            #print(M_tensors.shape)
            outputs = model(M_tensors)
            predictions2.append(torch.argmax(outputs, dim=1))
            
            predictions2 = torch.stack(predictions2).numpy()
            # predictions2 is then a list containing one list, to get a simple list, we select the first list in the list
            predictions2 = predictions2[0]
            
            #print(predictions2[0:9])  #display the predictions for the student
        
            
            # Remove from the memroy images now useless
            os.remove(pathToDniPage)
            for digit in range(len(coords)):
                os.remove(output_folder + "croping"+str(j)+"-"+str(digit)+".png")
            
            max_ratio = 0
            best_match = None
            prediction_str = ''.join([str(x) for x in predictions2])
            
            prediction_str = normalize_DNI(prediction_str)
            for DNI_index in range(len(L)):
                DNI_str = normalize_DNI(L[DNI_index][0])
                
                distance = Levenshtein.distance(DNI_str, prediction_str)
                ratio = 1 - (distance / max(len(DNI_str), len(prediction_str)))
                
                if(ratio > max_ratio):
                    max_ratio = ratio
                    best_match = DNI_index

            # Save the output information in the Output list
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
                #Paso final, buscamos calificiacion
                calificacion = detec_calification(ListNumFirstPage[j-1])
                if calificacion == "":
                    calificacion = 0.0
                else: 
                    calificacion = float(calificacion)
                    #Debe estar entra 0 y 10
                    if calificacion < 0 or calificacion > 10:
                        calificacion = 0.0
 
                #Output.append(Line)
                print(Line )
                emitter.emit_student(Alumno(asignatura_ID, examen_ID, Line[0], Line[1], Line[2], Line[3], Line[4], calificacion))
            #print("Line = ", Line, "Output = ", Output)
            #print("Vmax =",Vmax)
        except Exception as ex:
            #Imprimir excepcion
            print(ex)
            numErrorsGlobal += 1
            #Emitimos la informacion que tengamos
            calificacion = detec_calification(ListNumFirstPage[j-1])
            if calificacion == "":
                calificacion = 0.0
            else: 
                calificacion = float(calificacion)
                #Debe estar entra 0 y 10
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
#Borramos todos los ficheros auxiliares creados
shutil.rmtree(output_folder)

