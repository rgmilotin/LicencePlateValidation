# Licence Plate Validation & OCR Preprocessing

Acest modul face parte dintr-un sistem mai amplu de tip Smart Parking System și are rolul de a detecta, preprocesa și valida numere de înmatriculare românești pe baza imaginilor capturate de cameră.

Codul folosește OpenCV pentru procesarea imaginilor, Pytesseract pentru OCR și expresii regulate pentru validarea formatului final al numărului de înmatriculare.

## Funcționalități principale

- Citește o imagine de intrare care conține un autovehicul sau o plăcuță de înmatriculare.
- Convertește imaginea în grayscale pentru procesare mai stabilă.
- Detectează zona plăcuței folosind două metode:
  - detecție prin contur dreptunghiular;
  - fallback morfologic pentru imagini unde conturul plăcuței nu este clar.
- Realizează crop automat pe zona plăcuței.
- Aplică mai multe variante de preprocesare OCR:
  - contrast local;
  - threshold Otsu;
  - eliminare componente mici;
  - threshold adaptiv.
- Rulează OCR cu Tesseract pe mai multe versiuni procesate ale imaginii.
- Curăță textul detectat și elimină caracterele nerelevante.
- Corectează confuzii OCR frecvente, precum:
  - `O` ↔ `0`;
  - `I` ↔ `1`;
  - `B` ↔ `8`;
  - `S` ↔ `5`.
- Validează rezultatul final pe baza formatelor clasice românești:
  - `B 12 ABC`;
  - `B 123 ABC`;
  - `TM 11 ABC`;
  - `TM 111 ABC`.
- Respinge rezultatele OCR invalide sau halucinate, pentru a evita verificarea greșită în baza de date.

## Scop

Scopul acestui modul este să ofere o etapă intermediară robustă între imaginea capturată de cameră și validarea numărului în baza de date a sistemului de parcare.

În loc să accepte direct orice text returnat de OCR, codul verifică dacă textul detectat respectă structura unui număr de înmatriculare românesc. Astfel, sistemul devine mai sigur în situații reale, unde pot apărea zgomot, lumină slabă, reflexii, buline/stickere pe plăcuță sau caractere citite greșit.

## Tehnologii folosite

- Python
- OpenCV
- NumPy
- imutils
- Pytesseract
- Regex

## Observații

Modulul este gândit ca o componentă de testare și validare pentru partea de recunoaștere automată a numerelor de înmatriculare. Într-o versiune finală, rezultatul validat va putea fi trimis mai departe către o bază de date pentru verificarea accesului în parcare.
