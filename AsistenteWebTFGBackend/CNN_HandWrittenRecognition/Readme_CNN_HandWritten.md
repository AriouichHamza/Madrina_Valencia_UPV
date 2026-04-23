### Alumno.__init__
- **Inputs**: asignatura (str), examen (str), dni (str), nombre (str), apellidos (str), ini (int), fin (int), nota (float)
- **Outputs**: None (initializes object attributes)
- **Dimensions**: N/A
- **Description**: Initializes an Alumno object with student details including subject, exam, DNI, name, surname, start page, end page, and grade.

### Alumno.to_json
- **Inputs**: self (Alumno instance)
- **Outputs**: str (JSON string representation of the object)
- **Dimensions**: N/A
- **Description**: Converts the Alumno object's attributes to a JSON-formatted string.

### Emitter.emit_progress
- **Inputs**: self (Emitter instance), progress (int, 0-100), state (str)
- **Outputs**: None (writes to stdout)
- **Dimensions**: N/A
- **Description**: Emits progress updates to stdout in a specific format for the parent process.

### Emitter.emit_done
- **Inputs**: self (Emitter instance), time_elapsed (datetime.timedelta)
- **Outputs**: None (writes to stdout)
- **Dimensions**: N/A
- **Description**: Emits completion signal with elapsed time to stdout.

### Emitter.emit_student
- **Inputs**: self (Emitter instance), alumno (Alumno object)
- **Outputs**: None (writes to stdout)
- **Dimensions**: N/A
- **Description**: Emits a student's graded data as JSON to stdout.

### normalize_DNI
- **Inputs**: dni (str)
- **Outputs**: str (normalized DNI)
- **Dimensions**: N/A
- **Description**: Removes leading zeros from a DNI string for reliable comparison.

### convert_pdf_to_images
- **Inputs**: start_page (int), end_page (int), input_pdf (str, path), output_folder (str, path), total_pages (int)
- **Outputs**: None (runs subprocess, emits progress)
- **Dimensions**: N/A
- **Description**: Converts specified PDF pages to PNG images focusing on DNI header areas using pdftoppm.

### convert_pdf_to_images_calification
- **Inputs**: start_page (int), end_page (int), input_pdf (str, path), output_folder (str, path)
- **Outputs**: None (runs subprocess)
- **Dimensions**: N/A
- **Description**: Converts specified PDF pages to PNG images focusing on grade areas using pdftoppm.

### remove_margin_all
- **Inputs**: img (numpy array, image), margin (float, default 0.05)
- **Outputs**: numpy array (cropped image)
- **Dimensions**: Input: (H, W, C) or (H, W); Output: smaller (H', W', C) or (H', W')
- **Description**: Trims a percentage margin from image borders to reduce noise.

### is_square
- **Inputs**: contour (OpenCV contour), tolerance (float, default 0.05)
- **Outputs**: bool
- **Dimensions**: N/A
- **Description**: Checks if a contour is approximately square and large enough for digit detection.

### normalize_img
- **Inputs**: img (numpy array or PIL image)
- **Outputs**: torch.Tensor
- **Dimensions**: Input: (28, 28) or similar; Output: (1, 1, 28, 28)
- **Description**: Applies transforms to normalize an image for CNN input.

### detec_calification
- **Inputs**: numPage (int)
- **Outputs**: str (grade as string, e.g., "8.5" or "")
- **Dimensions**: N/A
- **Description**: Detects and classifies handwritten grade digits from a page image, returning a formatted grade string.

### buscar_inicio_copias
- **Inputs**: pages (list of int, page numbers), nbp (int, total pages)
- **Outputs**: list of tuples (coordinates and page number for DNI areas)
- **Dimensions**: N/A
- **Description**: Scans pages to detect DNI template boxes and identifies first pages of student copies.

### split_in_num_cpu
- **Inputs**: nbp (int, total pages)
- **Outputs**: list of lists (page numbers distributed across CPU cores)
- **Dimensions**: N/A
- **Description**: Distributes page numbers into buckets for parallel processing based on CPU count.

### main
- **Inputs**: None (uses global args and variables)
- **Outputs**: None (emits results via Emitter, cleans up)
- **Dimensions**: N/A
- **Description**: Orchestrates the full OCR pipeline: detects student pages, extracts DNIs, matches students, reads grades, and emits results.

### CNN.__init__
- **Inputs**: self (CNN instance)
- **Outputs**: None (initializes layers)
- **Dimensions**: N/A
- **Description**: Defines convolutional and fully-connected layers for digit classification.

### CNN.forward
- **Inputs**: self (CNN instance), x (torch.Tensor, batch of images)
- **Outputs**: torch.Tensor (logits for 10 classes)
- **Dimensions**: Input: (batch_size, 1, 28, 28); Output: (batch_size, 10)
- **Description**: Performs forward pass through the CNN to classify digit images.