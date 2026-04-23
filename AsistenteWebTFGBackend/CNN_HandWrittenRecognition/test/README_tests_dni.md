# Tests DNI basés sur `main.py`

Je t'ai préparé deux scripts.

## 1) `test_dni_zone.py`

But: vérifier **visuellement** si la logique de ton `main.py` détecte bien la zone du DNI.

### Commande

```bash
python test_dni_zone.py --pdf /chemin/vers/examen.pdf --output ./debug_dni_zone
```

### Sorties

- `annotated/` : image annotée par page
  - rectangle rouge = ancre détectée
  - rectangles verts = 9 cases DNI estimées
- `digit_crops/` : crops des cases détectées
- `summary.csv` : résumé page par page

### Interprétation

- si les rectangles verts tombent bien sur les 9 cases du DNI, ta détection de zone est correcte
- si l’ancre rouge est absente ou décalée, le problème vient avant le modèle

---

## 2) `test_dni_recognition.py`

But: vérifier si le **modèle** lit correctement le DNI.

### Mode A — vraie évaluation OCR avec ground truth

Tu fournis un CSV ou JSON qui contient la vérité terrain.

#### Format CSV

```csv
page,dni
1,12345678
5,87654321
9,11223344
```

#### Commande

```bash
python test_dni_recognition.py \
  --pdf /chemin/vers/examen.pdf \
  --model /chemin/vers/exammodel4.pt \
  --ground-truth /chemin/vers/page_to_dni.csv \
  --output ./debug_dni_ocr
```

### Mode B — matching avec ta liste d’étudiants

Si tu n’as pas de ground truth page par page, tu peux au moins voir quel étudiant le script matche.

#### Format JSON possible

```json
[
  {"dni": "12345678", "nombre": "Alice", "apellidos": "Dupont"},
  {"dni": "87654321", "nombre": "Bob", "apellidos": "Martin"}
]
```

#### Commande

```bash
python test_dni_recognition.py \
  --pdf /chemin/vers/examen.pdf \
  --model /chemin/vers/exammodel4.pt \
  --students /chemin/vers/alumnos.json \
  --output ./debug_dni_ocr
```

### Sorties

- `ocr_results.csv` : prédiction par page
- `metrics.txt` : métriques globales
- `ocr_debug/` : images annotées avec les 9 cases utilisées
- `digit_crops/` : crops de chaque chiffre

### Colonnes utiles dans `ocr_results.csv`

- `predicted_raw` : DNI brut prédit par le modèle
- `predicted_normalized` : DNI sans zéros initiaux
- `expected_dni` : vérité terrain ou meilleur match
- `exact_match` : 1 si match exact avec la vérité terrain
- `digit_accuracy` : précision chiffre par chiffre
- `best_match_similarity` : similarité Levenshtein avec le meilleur étudiant

---

## Conseils de validation

1. Lance d'abord `test_dni_zone.py`.
2. Vérifie visuellement que les 9 cases sont bien cadrées.
3. Ensuite lance `test_dni_recognition.py`.
4. Si la zone est bonne mais le DNI est faux, le problème vient plutôt du modèle ou du prétraitement.
5. Si la zone est mauvaise, inutile de conclure trop vite sur le modèle.

---

## Remarque importante

Ces scripts reprennent volontairement la logique de ton `main.py`, y compris ses hypothèses géométriques. Donc ils servent à tester **ce pipeline précis**, pas une version plus robuste ou généralisée.
