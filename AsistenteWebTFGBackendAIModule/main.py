from __future__ import annotations


from Modules.emitter import Emitter
from Modules.student import Alumno
from datetime import datetime
import os
import copy
import logging
import shutil
import sys
import traceback
import torch
import PyPDF2
import Levenshtein

from utils.traitement.pdf_traitement import set_page_num_width, safe_crop_digit, run_pdf_preprocessing
from utils.constants import device, trained_model_path, exam_model_path, output_folder, alumnos, inputPDF , asignatura_ID, examen_ID
from utils.utils import choose_device, load_model, load_exam_model, display_label, detec_calification, preprocess_image
from utils.traitement.dni_processing import clean_identifier, build_expected_identifier
from utils.pipelines.remplacement_bascar_inicio_copias import buscar_inicio_copias
from utils.pipelines.renplacement_compute_coords_from_main_block import split_in_num_cpu, compute_coords_from_main_block
import numpy as np
from concurrent.futures import ProcessPoolExecutor



# Flush each line immediately so the caller receives progress updates in real time.
initial_time = datetime.now()
emitter = Emitter()
MATCH_RATIO_THRESHOLD = 0.4


# Create the temporary dump folder used to store page crops and intermediate images.
if not os.path.exists(output_folder):
    os.makedirs(output_folder)



def prediction_indices_to_text(prediction_indices, classes):
    labels = []
    for prediction_index in prediction_indices:
        index = int(prediction_index)
        if 0 <= index < len(classes):
            labels.append(str(display_label(classes[index])))
        else:
            labels.append(str(index))
    return clean_identifier("".join(labels))


def complete_identifier_for_matching(value):
    identifier = clean_identifier(value)
    if not identifier:
        return ""

    if identifier.isdigit() and len(identifier) > 8:
        try:
            return build_expected_identifier(identifier[:8])
        except Exception:
            pass

    try:
        return build_expected_identifier(identifier)
    except Exception:
        # DNI espagnol: si l'OCR a lu un chiffre a la place de la lettre finale,
        # on reconstruit le DNI complet depuis les 8 premiers chiffres.
        if identifier.isdigit() and len(identifier) >= 8:
            try:
                return build_expected_identifier(identifier[:8])
            except Exception:
                pass
        return identifier


def best_student_match(roster, prediction):
    prediction_dni = complete_identifier_for_matching(prediction)
    if not prediction_dni:
        return None, -1

    max_ratio = -1
    best_match = None

    for student_index, student in enumerate(roster):
        roster_dni = complete_identifier_for_matching(student[0])
        if not roster_dni:
            continue

        distance = Levenshtein.distance(roster_dni, prediction_dni)
        ratio = 1 - (distance / max(len(roster_dni), len(prediction_dni)))

        if ratio > max_ratio:
            max_ratio = ratio
            best_match = student_index

    return best_match, max_ratio



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
    runtime_device = choose_device(device)
    dni_model, dni_classes = load_model(trained_model_path, runtime_device)
    exam_model = load_exam_model(exam_model_path, runtime_device)
    
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
    run_pdf_preprocessing(nbp)
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
        Line = None
        try :
            exception_occurred = False
            
            # Use the shared DNI box detector from main_exact_dni_lib.py.
            imgf, pathToDniPage, coords = compute_coords_from_main_block(j, coordsDNI, ListNumFirstPage)

            digit_tensors = []

            for l in range(len(coords)):
                
                # Shrink the crop slightly to avoid capturing the box borders.
                box = (coords[l][0][0]+5, coords[l][0][1]+5, coords[l][0][2]-5, coords[l][0][3]-5)
                
                area, crop_adjusted = safe_crop_digit(imgf, box)
                if crop_adjusted:
                    exception_occurred = True

                # SmallCNN was trained with the unified character preprocessing:
                # white background, character crop, square padding, 64x64, Normalize(0.5, 0.5).
                processed_digit = preprocess_image(area, image_size=64)
                digit_array = np.asarray(processed_digit).astype(np.float32) / 255.0
                digit_tensor = torch.from_numpy(digit_array).unsqueeze(0)
                digit_tensor = (digit_tensor - 0.5) / 0.5
                digit_tensors.append(digit_tensor)

            M_tensors = torch.stack(digit_tensors).to(runtime_device)
            with torch.no_grad():
                outputs = dni_model(M_tensors)
            predictions2 = torch.argmax(outputs, dim=1).cpu().tolist()
            
            # Delete temporary crops as soon as the prediction batch is complete.
            os.remove(pathToDniPage)
            
            prediction_str = prediction_indices_to_text(predictions2, dni_classes)
            print(f"prediction_str copy {j}: {prediction_str}", file=sys.stderr, flush=True)
            prediction_complete_dni = complete_identifier_for_matching(prediction_str)
            print(f"prediction_dni_complet copy {j}: {prediction_complete_dni}", file=sys.stderr, flush=True)
            best_match, max_ratio = best_student_match(L, prediction_str)
            match_is_accepted = best_match is not None and max_ratio >= MATCH_RATIO_THRESHOLD
            if match_is_accepted:
                print(
                    f"best_match copy {j}: index={best_match}, dni={L[best_match][0]}, "
                    f"nombre={L[best_match][1]}, apellidos={L[best_match][2]}, ratio={max_ratio:.2f}",
                    file=sys.stderr,
                    flush=True,
                )
            elif best_match is not None:
                print(
                    f"best_match copy {j}: ignored index={best_match}, dni={L[best_match][0]}, "
                    f"ratio={max_ratio:.2f} < {MATCH_RATIO_THRESHOLD:.2f}",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print(f"best_match copy {j}: None, ratio={max_ratio:.2f}", file=sys.stderr, flush=True)

            # Build the final page interval assigned to the matched student.
            if match_is_accepted:
                Line = copy.deepcopy(L[best_match])
                Line[0] = complete_identifier_for_matching(Line[0])
            else:
                Line = ['', '', '']
            Line.append(str(ListNumFirstPage[j-1]))
            if j < nbStudent :
                Line.append(str(ListNumFirstPage[j]-1))
            else :
                Line.append(str(nbp))

            if exception_occurred:
                print(f"DNI crop adjusted for copy {j}, page {ListNumFirstPage[j-1]}", file=sys.stderr)

            # Final step: detect and sanitize the grade before emitting the result.
            try:
                calificacion = detec_calification(ListNumFirstPage[j-1], exam_model, device=runtime_device)
            except Exception as grade_ex:
                print(f"Grade detection failed on page {ListNumFirstPage[j-1]}: {grade_ex}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                calificacion = 0.0
            if calificacion == "":
                calificacion = 0.0
            else:
                calificacion = float(calificacion)
                # Grades outside the expected range are treated as invalid OCR noise.
                if calificacion < 0 or calificacion > 10:
                    calificacion = 0.0

            print(Line)
            emitter.emit_student(Alumno(asignatura_ID, examen_ID, Line[0], Line[1], Line[2], Line[3], Line[4], calificacion))
        except Exception as ex:
            print(f"Student processing failed for copy {j}: {ex}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            numErrorsGlobal += 1
            # Even on failure, try to salvage the grade and emit a placeholder student entry.
            try:
                calificacion = detec_calification(ListNumFirstPage[j-1], exam_model, device=runtime_device)
            except Exception as grade_ex:
                print(f"Fallback grade detection failed on page {ListNumFirstPage[j-1]}: {grade_ex}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                calificacion = 0.0
            if calificacion == "":
                calificacion = 0.0
            else: 
                calificacion = float(calificacion)
                if calificacion < 0 or calificacion > 10:
                    calificacion = 0.0
            if j < nbStudent :
                fin_pag = ListNumFirstPage[j]-1
            else :
                fin_pag = nbp
            if Line is not None:
                emitter.emit_student(Alumno(asignatura_ID, examen_ID, Line[0], Line[1], Line[2], Line[3], Line[4], calificacion))
            else:
                emitter.emit_student(Alumno(asignatura_ID, examen_ID, "Err"+str(numErrorsGlobal),"Err"+str(numErrorsGlobal), "Err"+str(numErrorsGlobal), ListNumFirstPage[j-1], fin_pag, calificacion))
        
if __name__ == "__main__":
    main()
    emitter.emit_done(datetime.now() - initial_time)
    # Remove the temporary working directory created for intermediate images.
    shutil.rmtree(output_folder)
