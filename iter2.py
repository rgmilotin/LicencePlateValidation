import cv2
import imutils
import numpy as np
import pytesseract
import re

# =============================
# CONFIGURARE
# =============================

# Path catre executabilul Tesseract OCR instalat pe Windows
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Imaginea pe care o testam
IMAGE_PATH = r"D:\Poli\LigaAC\LABS2026\Magna\Lab2\LicencePlateValidation\masina8.png"

# Lista codurilor de judete acceptate pentru numere romanesti
JUDETE = [
    "AB", "AG", "AR", "BC", "BH", "BN", "BR", "BT", "BV", "BZ",
    "CJ", "CL", "CS", "CT", "CV", "DB", "DJ", "GJ", "GL", "GR",
    "HD", "HR", "IF", "IL", "IS", "MH", "MM", "MS", "NT", "OT",
    "PH", "SB", "SJ", "SM", "SV", "TL", "TM", "TR", "VL", "VN",
    "VS"
]


# =============================
# FUNCTII DE AFISARE
# =============================

def imshow_scaled(title, image, max_width=900):
    # Afiseaza o imagine redimensionata doar pentru debug/vizualizare
    h, w = image.shape[:2]

    if w > max_width:
        scale = max_width / w
        image = cv2.resize(
            image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_AREA
        )

    cv2.imshow(title, image)


# =============================
# VALIDARE NUMAR ROMANESC
# =============================

def curata_text(text):
    # Pastreaza doar litere mari si cifre
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def este_numar_valid(text):
    # Verifica daca textul respecta formatul unui numar romanesc clasic
    text = curata_text(text)

    # Bucuresti: B 12 ABC sau B 123 ABC
    if re.fullmatch(r"B[0-9]{2,3}[A-Z]{3}", text):
        return True

    # Judete: TM 11 ABC sau TM 111 ABC
    if len(text) >= 7:
        judet = text[:2]

        if judet in JUDETE:
            if re.fullmatch(r"[A-Z]{2}[0-9]{2,3}[A-Z]{3}", text):
                return True

    return False


def repara_confuzie_ocr(text):
    # Corecteaza confuzii frecvente intre litere si cifre produse de OCR
    text = curata_text(text)

    conversii_cifre = {
        "O": "0",
        "Q": "0",
        "D": "0",
        "I": "1",
        "L": "1",
        "T": "1",
        "Z": "2",
        "S": "5",
        "B": "8",
        "G": "6"
    }

    conversii_litere = {
        "0": "O",
        "1": "I",
        "2": "Z",
        "5": "S",
        "6": "G",
        "8": "B"
    }

    variante = set()
    variante.add(text)

    # Incercam si stergerea unui caracter parazit, de exemplu o bulina citita gresit
    for i in range(len(text)):
        variante.add(text[:i] + text[i + 1:])

    for varianta in variante:
        # Caz Bucuresti: B + 2/3 cifre + 3 litere
        if varianta.startswith("B"):
            for nr_cifre in [2, 3]:
                lungime = 1 + nr_cifre + 3

                if len(varianta) == lungime:
                    prefix = varianta[0]
                    cifre = varianta[1:1 + nr_cifre]
                    litere = varianta[1 + nr_cifre:]

                    cifre_corectate = "".join(conversii_cifre.get(c, c) for c in cifre)
                    litere_corectate = "".join(conversii_litere.get(c, c) for c in litere)

                    rezultat = prefix + cifre_corectate + litere_corectate

                    if este_numar_valid(rezultat):
                        return rezultat

        # Caz judet: cod judet + 2/3 cifre + 3 litere
        if len(varianta) >= 7:
            judet = varianta[:2]

            if judet in JUDETE:
                for nr_cifre in [2, 3]:
                    lungime = 2 + nr_cifre + 3

                    if len(varianta) == lungime:
                        prefix = varianta[:2]
                        cifre = varianta[2:2 + nr_cifre]
                        litere = varianta[2 + nr_cifre:]

                        cifre_corectate = "".join(conversii_cifre.get(c, c) for c in cifre)
                        litere_corectate = "".join(conversii_litere.get(c, c) for c in litere)

                        rezultat = prefix + cifre_corectate + litere_corectate

                        if este_numar_valid(rezultat):
                            return rezultat

    return None


def extrage_numar_valid(text):
    # Extrage un numar valid din textul OCR, inclusiv din subsecvente
    text = curata_text(text)

    if este_numar_valid(text):
        return text

    reparat = repara_confuzie_ocr(text)

    if reparat is not None:
        return reparat

    # Cautam subsecvente valide in caz ca OCR a citit zgomot in plus
    for lungime in range(6, 9):
        for i in range(0, len(text) - lungime + 1):
            subtext = text[i:i + lungime]

            if este_numar_valid(subtext):
                return subtext

            reparat = repara_confuzie_ocr(subtext)

            if reparat is not None:
                return reparat

    return None


# =============================
# DETECTARE PLACUTA
# =============================

def detecteaza_placuta(img, gray):
    # Detecteaza placuta folosind intai contururi, apoi fallback morfologic
    gray_filtrat = cv2.bilateralFilter(gray, 11, 17, 17)
    edged = cv2.Canny(gray_filtrat, 30, 200)

    cnts = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:30]

    H, W = gray.shape

    # Metoda 1: cautam un contur dreptunghiular asemanator cu o placuta
    for c in cnts:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.018 * peri, True)

        x, y, w, h = cv2.boundingRect(approx)

        if h == 0:
            continue

        aspect_ratio = w / float(h)

        conditie_colturi = len(approx) == 4
        conditie_aspect = 2.0 <= aspect_ratio <= 7.5
        conditie_marime = w > 0.10 * W and h > 0.02 * H
        conditie_pozitie = y > 0.20 * H

        if conditie_colturi and conditie_aspect and conditie_marime and conditie_pozitie:
            mask = np.zeros(gray.shape, np.uint8)
            cv2.drawContours(mask, [approx], 0, 255, -1)

            rows, cols = np.where(mask == 255)

            top_row, left_col = np.min(rows), np.min(cols)
            bottom_row, right_col = np.max(rows), np.max(cols)

            cropped = gray[top_row:bottom_row + 1, left_col:right_col + 1]
            masked = cv2.bitwise_and(gray, gray, mask=mask)

            return cropped, masked, "contur cu 4 colturi"

    # Metoda 2: fallback pentru cazurile in care placuta nu are contur clar
    rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))

    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect_kernel)

    grad_x = cv2.Sobel(blackhat, cv2.CV_32F, 1, 0, ksize=-1)
    grad_x = np.absolute(grad_x)

    min_val, max_val = np.min(grad_x), np.max(grad_x)

    if max_val - min_val != 0:
        grad_x = 255 * ((grad_x - min_val) / (max_val - min_val))

    grad_x = grad_x.astype("uint8")
    grad_x = cv2.GaussianBlur(grad_x, (5, 5), 0)

    closed = cv2.morphologyEx(grad_x, cv2.MORPH_CLOSE, rect_kernel)

    thresh = cv2.threshold(
        closed,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1]

    thresh = cv2.erode(thresh, None, iterations=1)
    thresh = cv2.dilate(thresh, None, iterations=2)

    cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)

    best = None
    best_score = 0

    # Alegem cea mai probabila zona a placutei dupa forma, marime si pozitie
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)

        if h == 0:
            continue

        aspect_ratio = w / float(h)
        area = w * h

        conditie_aspect = 2.0 <= aspect_ratio <= 8.0
        conditie_marime = 0.12 * W <= w <= 0.95 * W and 0.02 * H <= h <= 0.25 * H
        conditie_pozitie = y > 0.20 * H

        if conditie_aspect and conditie_marime and conditie_pozitie:
            score = area + y * 2

            if score > best_score:
                best_score = score
                best = (x, y, w, h)

    if best is None:
        return None, None, "nimic detectat"

    x, y, w, h = best

    # Adaugam padding ca sa nu taiem caracterele de pe margini
    pad_x = int(0.05 * w)
    pad_y = int(0.30 * h)

    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(W, x + w + pad_x)
    y2 = min(H, y + h + pad_y)

    cropped = gray[y1:y2, x1:x2]

    detected_area = gray.copy()
    cv2.rectangle(detected_area, (x1, y1), (x2, y2), 255, 3)

    return cropped, detected_area, "fallback morfologic"


# =============================
# PREPROCESARE OCR
# =============================

def elimina_componente_mici(binary_image):
    # Elimina obiecte mici/pete/rame dintr-o imagine binara
    inv = 255 - binary_image

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inv, 8)

    H, W = inv.shape

    char_heights = []

    # Estimam inaltimea tipica a caracterelor reale
    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]

        if area > 40 and 0.30 * H <= h <= 0.95 * H:
            char_heights.append(h)

    if len(char_heights) > 0:
        median_char_height = np.median(char_heights)
    else:
        median_char_height = 0.50 * H

    cleaned = np.zeros_like(inv)

    # Pastram doar componentele care seamana cu litere/cifre
    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]

        if area < 20:
            continue

        too_small = h < 0.60 * median_char_height and w < 0.75 * median_char_height
        bottom_small_text = y > 0.72 * H and h < 0.50 * median_char_height
        horizontal_line = w > 0.65 * W and h < 0.25 * median_char_height

        if not too_small and not bottom_small_text and not horizontal_line:
            cleaned[labels == i] = 255

    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=1)

    return 255 - cleaned


def pregateste_variante_ocr(cropped):
    # Creeaza mai multe variante preprocesate pentru OCR
    variante = []

    H, W = cropped.shape

    # Taiem putin din rama placutei si textul mic de jos
    y1 = int(0.04 * H)
    y2 = int(0.90 * H)
    x1 = int(0.02 * W)
    x2 = int(0.98 * W)

    plate = cropped[y1:y2, x1:x2]

    if plate.size == 0:
        plate = cropped

    # Normalizam dimensiunea placutei pentru OCR
    target_height = 120
    scale = target_height / plate.shape[0]

    plate = cv2.resize(
        plate,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC
    )

    # Crestere de contrast si reducere de zgomot
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(plate)

    contrast = cv2.bilateralFilter(contrast, 5, 30, 30)

    # Varianta 1: grayscale cu contrast
    variante.append(("contrast_gray", contrast))

    # Varianta 2: threshold Otsu
    otsu = cv2.threshold(
        contrast,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1]

    if np.mean(otsu) < 127:
        otsu = 255 - otsu

    # Umplem mici intreruperi din caractere
    inv = 255 - otsu
    kernel = np.ones((2, 2), np.uint8)
    inv = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, kernel, iterations=1)
    otsu_filled = 255 - inv

    variante.append(("otsu_filled", otsu_filled))

    # Varianta 3: Otsu curatat de componente mici
    otsu_cleaned = elimina_componente_mici(otsu_filled)
    variante.append(("otsu_cleaned", otsu_cleaned))

    # Varianta 4: threshold adaptiv mai bland
    adaptive = cv2.adaptiveThreshold(
        contrast,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        61,
        7
    )

    if np.mean(adaptive) < 127:
        adaptive = 255 - adaptive

    variante.append(("adaptive_soft", adaptive))

    return variante


# =============================
# OCR
# =============================

def citeste_numar(cropped):
    # Ruleaza OCR pe mai multe variante si returneaza primul rezultat valid
    variante = pregateste_variante_ocr(cropped)

    configuri = [
        "--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        "--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ]

    rezultate_debug = []

    best_text = ""
    best_image = variante[0][1]

    for nume_varianta, imagine_ocr in variante:
        for config in configuri:
            text = pytesseract.image_to_string(imagine_ocr, config=config)
            text_curatat = curata_text(text)

            if len(text_curatat) > len(best_text):
                best_text = text_curatat
                best_image = imagine_ocr

            rezultat_valid = extrage_numar_valid(text_curatat)

            rezultate_debug.append((nume_varianta, text_curatat, rezultat_valid))

            if rezultat_valid is not None:
                return rezultat_valid, imagine_ocr, rezultate_debug

    return None, best_image, rezultate_debug


# =============================
# MAIN
# =============================

# Citim imaginea de intrare
img = cv2.imread(IMAGE_PATH)

if img is None:
    raise FileNotFoundError("Image not found. Please check the path and filename.")

# Convertim imaginea in grayscale pentru procesare
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Detectam zona placutei
cropped, detected_area, metoda_detectie = detecteaza_placuta(img, gray)

if cropped is None:
    raise Exception("Nu s-a detectat nicio plăcuță de înmatriculare.")

# Rulam OCR si validarea numarului
numar_detectat, ocr_processed, rezultate_debug = citeste_numar(cropped)

# Afisam imaginile utile pentru debug
imshow_scaled("Original image", img)
imshow_scaled("Detected plate area", detected_area)
imshow_scaled("Cropped plate", cropped)
imshow_scaled("OCR processed", ocr_processed)

cv2.waitKey(0)
cv2.destroyAllWindows()

# Afisam metoda de detectie folosita
print("Metoda detectie:", metoda_detectie)

# Afisam toate incercarile OCR
print("\nRezultate OCR testate:")
for varianta, text_ocr, rezultat_valid in rezultate_debug:
    print(f"{varianta}: {text_ocr} -> {rezultat_valid}")

# Afisam rezultatul final
if numar_detectat is not None:
    print("\nDetected license plate Number is:", numar_detectat)
else:
    print("\nNu s-a putut extrage un numar valid.")