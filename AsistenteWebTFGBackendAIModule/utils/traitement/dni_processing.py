
from __future__ import annotations

try:
    import pandas as pd
except ModuleNotFoundError:
    pd = None


DNI_LETTERS = ['T', 'R', 'W', 'A', 'G', 'M', 'Y', 'F', 'P', 'D', 'X', 'B', 'N', 'J', 'Z', 'S', 'Q', 'V', 'H', 'L', 'C', 'K', 'E']
NIF_PREFIX_VALUES = {'X': 0, 'Y': 1, 'Z': 2, 'N': 3, 'P': 4}


def clean_identifier(value):
    if value is None:
        return ""
    if pd is not None and pd.isna(value):
        return ""
    return str(value).strip().upper().replace(" ", "").replace("-", "")


def require_pandas():
    if pd is None:
        raise ModuleNotFoundError("pandas is required to use DNIProcessor with CSV files")


def detect_identifier_type(value):
    identifier = clean_identifier(value)

    if len(identifier) == 0 or identifier == "NAN":
        raise ValueError("DNI/NIF cannot be empty")

    if len(identifier) > 9 and identifier[0].isalpha():
        return "ERASMUS"
    if identifier[0].isalpha():
        return "NIF"
    if identifier[0].isdigit():
        return "DNI"

    raise ValueError("Invalid DNI/NIF format")


def calculate_expected_letter(numeric_part):
    return DNI_LETTERS[int(numeric_part) % 23]


def build_expected_identifier(value):
    identifier = clean_identifier(value)
    identifier_type = detect_identifier_type(identifier)

    if identifier_type == "ERASMUS":
        return identifier

    if identifier_type == "DNI":
        if identifier.isdigit():
            numeric_part = identifier
        elif identifier[:-1].isdigit() and identifier[-1].isalpha():
            numeric_part = identifier[:-1]
        else:
            raise ValueError("Invalid DNI format")
        return numeric_part + calculate_expected_letter(int(numeric_part))

    first_letter = identifier[0]
    if first_letter not in NIF_PREFIX_VALUES:
        raise ValueError("Invalid NIF first letter")

    if identifier[-1].isalpha():
        numeric_part_str = identifier[1:-1]
    else:
        numeric_part_str = identifier[1:]

    if not numeric_part_str.isdigit():
        raise ValueError("Invalid NIF numeric part")

    numeric_part = NIF_PREFIX_VALUES[first_letter] * 10 ** len(numeric_part_str) + int(numeric_part_str)
    return first_letter + numeric_part_str + calculate_expected_letter(numeric_part)


def identifier_match_candidates(value):
    candidates = []

    def add(candidate):
        candidate = clean_identifier(candidate)
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    add(value)

    try:
        add(build_expected_identifier(value))
    except Exception:
        pass

    for candidate in list(candidates):
        if candidate[:-1].isdigit() and candidate[-1].isalpha():
            add(candidate[:-1])
        numeric_only = "".join(char for char in candidate if char.isdigit())
        if numeric_only:
            add(numeric_only)
            add(numeric_only.lstrip("0") or "0")

        if candidate and candidate[0].isdigit():
            add(candidate.lstrip("0") or "0")

    return candidates


class DNIProcessor:
    def __init__(self, students_csv_path):
        require_pandas()
        self.df = pd.read_csv(
            students_csv_path,
            encoding="latin-1",
            sep=";",
            dtype={"DNI": str}
        )

        # Drop the last row if it is a spurious footer added by the export tool.
        self.df.drop(self.df.index[-1], inplace=True)

        self.dictionary = {
            "Reste": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
            "Lettre": DNI_LETTERS
        }

        self.NIF_detection_dict = {
            "Lettre": list(NIF_PREFIX_VALUES.keys()),
            "Valeur": list(NIF_PREFIX_VALUES.values())
        }

    # ============================================================
    # Identifier normalisation
    # ============================================================
    def clean_identifier(self, value):
        """Normalizes a DNI/NIF: strips whitespace and dashes, converts to uppercase."""

        return clean_identifier(value)

    # ============================================================
    # DNI / NIF / ERASMUS detection
    # ============================================================
    def detect_nif(self, dni_nif):
        """Returns 'DNI', 'NIF', or 'ERASMUS' for the given identifier."""

        return detect_identifier_type(dni_nif)

    # ============================================================
    # DNI check-letter calculation
    # ============================================================
    def calculate_expected_letter(self, numeric_part):
        """Returns the expected check letter using the DNI algorithm: table[numeric_part % 23]."""

        return calculate_expected_letter(numeric_part)

    # ============================================================
    # NIF prefix letter to numeric value
    # ============================================================
    def transform_nif_first_letter_to_number(self, first_letter):
        """
        Converts the NIF prefix letter to its numeric equivalent:
        X -> 0, Y -> 1, Z -> 2, N -> 3, P -> 4
        """

        first_letter = first_letter.upper()

        if first_letter not in self.NIF_detection_dict["Lettre"]:
            raise ValueError("Invalid NIF first letter")

        index = self.NIF_detection_dict["Lettre"].index(first_letter)
        return self.NIF_detection_dict["Valeur"][index]

    # ============================================================
    # NIF part extraction
    # ============================================================
    def extract_nif_parts(self, nif):
        """
        Splits a NIF into (first_letter, numeric_part_str, check_letter_or_None).

        Examples:
          X7470664B -> X, 7470664, B
          X7470664  -> X, 7470664, None
        """

        nif = self.clean_identifier(nif)

        if len(nif) < 2:
            raise ValueError("Invalid NIF format")

        first_letter = nif[0]

        if first_letter not in self.NIF_detection_dict["Lettre"]:
            raise ValueError("Invalid NIF first letter")

        # NIF with check letter: X7470664B
        if nif[-1].isalpha():
            numeric_part_str = nif[1:-1]
            current_letter = nif[-1]

        # NIF without check letter: X7470664
        else:
            numeric_part_str = nif[1:]
            current_letter = None

        if not numeric_part_str.isdigit():
            raise ValueError("Invalid NIF numeric part")

        return first_letter, numeric_part_str, current_letter

    # ============================================================
    # NIF numeric part calculation
    # ============================================================
    def calculate_nif_numeric_part(self, nif):
        """
        Computes the combined numeric part used for NIF check-letter calculation:

        NIF = prefix_letter + numeric_part + check_letter
        X -> 0, Y -> 1, Z -> 2, N -> 3, P -> 4

        Numeric_Part = prefix_value * 10^len(numeric_part) + numeric_part
        """

        first_letter, numeric_part_str, current_letter = self.extract_nif_parts(nif)

        first_letter_number = self.transform_nif_first_letter_to_number(first_letter)

        numeric_part = first_letter_number * 10**len(numeric_part_str) + int(numeric_part_str)

        return numeric_part

    # ============================================================
    # DNI processing
    # ============================================================
    def process_dni(self, dni):
        """
        Validates and enriches a DNI (with or without check letter).

        Examples:
          12345678Z
          12345678
        """

        dni = self.clean_identifier(dni)

        # DNI without check letter: 12345678
        if dni.isdigit():
            numeric_part = int(dni)
            current_letter = None
            expected_letter = self.calculate_expected_letter(numeric_part)
            expected_id = dni + expected_letter
            is_valid = None

        # DNI with check letter: 12345678Z
        elif dni[:-1].isdigit() and dni[-1].isalpha():
            numeric_part = int(dni[:-1])
            current_letter = dni[-1]
            expected_letter = self.calculate_expected_letter(numeric_part)
            expected_id = dni[:-1] + expected_letter
            is_valid = current_letter == expected_letter

        else:
            raise ValueError("Invalid DNI format")

        return {
            "Numeric_Part": numeric_part,
            "Current_Letter": current_letter,
            "Expected_Letter": expected_letter,
            "Expected_ID": expected_id,
            "Is_Valid": is_valid
        }

    # ============================================================
    # NIF processing
    # ============================================================
    def process_nif(self, nif):
        """
        Validates and enriches a NIF (with or without check letter).

        Logic:
          Numeric_Part = prefix_value * 10^len(numeric_part) + numeric_part
          Expected_Letter = DNI_LETTERS[Numeric_Part % 23]
        """

        nif = self.clean_identifier(nif)

        first_letter, numeric_part_str, current_letter = self.extract_nif_parts(nif)

        numeric_part = self.calculate_nif_numeric_part(nif)

        expected_letter = self.calculate_expected_letter(numeric_part)

        expected_id = first_letter + numeric_part_str + expected_letter

        if current_letter is None:
            is_valid = None
        else:
            is_valid = current_letter == expected_letter

        return {
            "Numeric_Part": numeric_part,
            "Current_Letter": current_letter,
            "Expected_Letter": expected_letter,
            "Expected_ID": expected_id,
            "Is_Valid": is_valid
        }

    # ============================================================
    # Filter rows by DNI / NIF / ERASMUS type
    # ============================================================
    def find_rows_DNI_or_NIF(self, id_type: str):
        id_type = str(id_type).strip().upper()

        if id_type not in {"DNI", "NIF", "ERASMUS"}:
            raise ValueError("id_type must be 'DNI', 'NIF', or 'ERASMUS'")

        ids = self.df["DNI"].apply(self.detect_nif)

        return self.df[ids == id_type]

    # ============================================================
    # Check-letter algorithm for DNI rows only
    # ============================================================
    def get_the_alphabatic_caracters_algorithm(self):
        """Returns a DataFrame with (DNI, Numeric_Part, Expected_Letter) for all DNI rows."""

        results = []

        for raw_id in self.df["DNI"]:
            try:
                clean_id = self.clean_identifier(raw_id)

                if self.detect_nif(clean_id) != "DNI":
                    continue

                dni_result = self.process_dni(clean_id)

                results.append({
                    "DNI": clean_id,
                    "Numeric_Part": dni_result["Numeric_Part"],
                    "Expected_Letter": dni_result["Expected_Letter"]
                })

            except Exception:
                continue

        return pd.DataFrame(results)

    # ============================================================
    # Check-letter algorithm for NIF rows only
    # ============================================================
    def get_the_alphabatic_caracters_algorithm_for_nif(self):
        """Returns a DataFrame with (DNI, Numeric_Part, Expected_Letter) for all NIF rows."""

        results = []

        for raw_id in self.df["DNI"]:
            try:
                clean_id = self.clean_identifier(raw_id)

                if self.detect_nif(clean_id) != "NIF":
                    continue

                numeric_part = self.calculate_nif_numeric_part(clean_id)
                expected_letter = self.calculate_expected_letter(numeric_part)

                results.append({
                    "DNI": clean_id,
                    "Numeric_Part": numeric_part,
                    "Expected_Letter": expected_letter
                })

            except Exception:
                results.append({
                    "DNI": self.clean_identifier(raw_id),
                    "Numeric_Part": None,
                    "Expected_Letter": None
                })

        return pd.DataFrame(results)[["DNI", "Numeric_Part", "Expected_Letter"]]

    # ============================================================
    # Main processing entry point
    # ============================================================
    def dni_processing(self):
        """
        Processes the full student CSV and returns an enriched DataFrame.

        Calls detect_nif(), process_dni(), process_nif(), etc. and adds columns:
          Original_ID, ID_Type, Normalized_ID, Numeric_Part, Current_Letter,
          Expected_Letter, Expected_ID, Is_Valid, Error
        """

        results = []

        for index, raw_id in self.df["DNI"].items():
            row_result = {
                "Original_ID": raw_id,
                "ID_Type": None,
                "Normalized_ID": None,
                "Numeric_Part": None,
                "Current_Letter": None,
                "Expected_Letter": None,
                "Expected_ID": None,
                "Is_Valid": None,
                "Error": None
            }

            try:
                clean_id = self.clean_identifier(raw_id)

                if len(clean_id) == 0:
                    raise ValueError("Empty DNI/NIF")

                id_type = self.detect_nif(clean_id)

                row_result["ID_Type"] = id_type
                row_result["Normalized_ID"] = clean_id

                # =========================
                # ERASMUS
                # =========================
                if id_type == "ERASMUS":
                    row_result["Expected_ID"] = clean_id
                    row_result["Is_Valid"] = None

                # =========================
                # DNI
                # =========================
                elif id_type == "DNI":
                    dni_result = self.process_dni(clean_id)

                    row_result["Numeric_Part"] = dni_result["Numeric_Part"]
                    row_result["Current_Letter"] = dni_result["Current_Letter"]
                    row_result["Expected_Letter"] = dni_result["Expected_Letter"]
                    row_result["Expected_ID"] = dni_result["Expected_ID"]
                    row_result["Is_Valid"] = dni_result["Is_Valid"]

                # =========================
                # NIF
                # =========================
                elif id_type == "NIF":
                    nif_result = self.process_nif(clean_id)

                    row_result["Numeric_Part"] = nif_result["Numeric_Part"]
                    row_result["Current_Letter"] = nif_result["Current_Letter"]
                    row_result["Expected_Letter"] = nif_result["Expected_Letter"]
                    row_result["Expected_ID"] = nif_result["Expected_ID"]
                    row_result["Is_Valid"] = nif_result["Is_Valid"]

            except Exception as e:
                row_result["Error"] = str(e)

            results.append(row_result)

        processed_df = pd.DataFrame(results, index=self.df.index)

        columns_to_remove = [
            "Original_ID",
            "ID_Type",
            "Normalized_ID",
            "Numeric_Part",
            "Current_Letter",
            "Expected_Letter",
            "Expected_ID",
            "Is_Valid",
            "Error"
        ]

        clean_df = self.df.drop(
            columns=[col for col in columns_to_remove if col in self.df.columns],
            errors="ignore"
        )

        return pd.concat([clean_df, processed_df], axis=1)
