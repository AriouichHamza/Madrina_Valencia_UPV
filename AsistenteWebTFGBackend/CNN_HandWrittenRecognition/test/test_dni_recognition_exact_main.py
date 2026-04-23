#!/usr/bin/env python3
import argparse
import csv
import json
import os
import shutil

import main_exact_dni_lib as exact


def load_ground_truth_csv(path):
    mapping = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        lower_fields = {name.lower(): name for name in reader.fieldnames}
        page_key = lower_fields.get("page")
        dni_key = lower_fields.get("dni")
        if not page_key or not dni_key:
            raise ValueError("Le CSV ground truth doit contenir les colonnes 'page' et 'dni'.")
        for row in reader:
            mapping[int(row[page_key])] = str(row[dni_key]).strip()
    return mapping


def load_students_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Le JSON students doit être une liste d'objets.")
    result = []
    for item in data:
        result.append({
            "dni": str(item["dni"]),
            "nombre": item.get("nombre", ""),
            "apellidos": item.get("apellidos", ""),
        })
    return result


def best_student_match(prediction_str, students):
    max_ratio = 0
    best_match = None
    for student in students:
        dni_str = exact.normalize_DNI(student["dni"])
        distance = exact.Levenshtein.distance(dni_str, prediction_str)
        ratio = 1 - (distance / max(len(dni_str), len(prediction_str)))
        if ratio > max_ratio:
            max_ratio = ratio
            best_match = student
    return best_match, max_ratio


def main():
    parser = argparse.ArgumentParser(description="Test exact OCR DNI avec les blocs de main.py sans modifier leur corps.")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ground-truth")
    parser.add_argument("--students")
    parser.add_argument("--keep-workdir", action="store_true")
    args = parser.parse_args()

    if not args.ground_truth and not args.students:
        raise SystemExit("Tu dois fournir --ground-truth ou --students")

    pdf_path = os.path.abspath(args.pdf)
    model_path = os.path.abspath(args.model)
    output_dir = os.path.abspath(args.output)
    work_dir = os.path.join(output_dir, "workdir")
    os.makedirs(output_dir, exist_ok=True)

    exact.setup_globals(pdf_path=pdf_path, output_dir=work_dir, model_path=model_path, examen_name=os.path.splitext(os.path.basename(pdf_path))[0])

    nbp = exact.convert_pdf_like_main()
    coordsDNI, ListNumFirstPage = exact.detect_first_pages_like_main(nbp)

    gt = load_ground_truth_csv(args.ground_truth) if args.ground_truth else None
    students = load_students_json(args.students) if args.students else None

    results = []
    exact_match_count = 0

    for j in range(1, len(ListNumFirstPage) + 1):
        page = ListNumFirstPage[j - 1]
        pred = exact.predict_dni_from_main_block(j, coordsDNI, ListNumFirstPage, model_path=model_path)

        row = {
            "page": page,
            "predicted_dni": pred["prediction_str"],
            "prediction_digits": "".join(str(x) for x in pred["prediction_digits"]),
            "exception_occurred": pred["exception_occurred"],
            "ground_truth_dni": "",
            "exact_match": "",
            "best_student_dni": "",
            "best_student_nombre": "",
            "best_student_apellidos": "",
            "best_student_ratio": "",
        }

        if gt is not None:
            truth = exact.normalize_DNI(str(gt.get(page, "")))
            row["ground_truth_dni"] = truth
            if truth != "":
                is_match = pred["prediction_str"] == truth
                row["exact_match"] = is_match
                if is_match:
                    exact_match_count += 1

        if students is not None:
            best_match, ratio = best_student_match(pred["prediction_str"], students)
            if best_match is not None:
                row["best_student_dni"] = best_match["dni"]
                row["best_student_nombre"] = best_match["nombre"]
                row["best_student_apellidos"] = best_match["apellidos"]
                row["best_student_ratio"] = ratio

        results.append(row)

    results_csv = os.path.join(output_dir, "ocr_results.csv")
    with open(results_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()) if results else [
            "page", "predicted_dni", "prediction_digits", "exception_occurred", "ground_truth_dni",
            "exact_match", "best_student_dni", "best_student_nombre", "best_student_apellidos", "best_student_ratio"
        ])
        writer.writeheader()
        writer.writerows(results)

    metrics_path = os.path.join(output_dir, "metrics.txt")
    with open(metrics_path, "w", encoding="utf-8") as f:
        f.write(f"pages_total={nbp}\n")
        f.write(f"first_pages_detected={len(ListNumFirstPage)}\n")
        if gt is not None:
            comparable = sum(1 for row in results if row["ground_truth_dni"] != "")
            f.write(f"ground_truth_rows={comparable}\n")
            f.write(f"exact_match_count={exact_match_count}\n")
            f.write(f"exact_match_accuracy={(exact_match_count / comparable) if comparable else 0.0}\n")

    print(f"Pages totales: {nbp}")
    print(f"Premières pages détectées: {len(ListNumFirstPage)}")
    print(f"Résultats OCR: {results_csv}")
    print(f"Metrics: {metrics_path}")

    if not args.keep_workdir:
        shutil.rmtree(work_dir, ignore_errors=True)
        print("Workdir temporaire supprimé.")
    else:
        print(f"Workdir conservé: {work_dir}")


if __name__ == "__main__":
    main()
