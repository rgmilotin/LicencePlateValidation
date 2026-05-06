import cv2
import imutils
import numpy as np
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

img = cv2.imread(r'D:\Poli\LigaAC\LABS2026\Magna\Lab2\LicencePlateValidation\masina2.jpg')

if img is None:
    raise FileNotFoundError("Image not found. Please check the path and filename.")

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
gray = cv2.bilateralFilter(gray, 11, 17, 17)
edged = cv2.Canny(gray, 30, 200)

cnts = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
cnts = imutils.grab_contours(cnts)
cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:10]

screenCnt = None

for c in cnts:
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.018 * peri, True)

    if len(approx) == 4:
        screenCnt = approx
        break

if screenCnt is None:
    raise Exception("Nu s-a detectat nicio plăcuță de înmatriculare.")

detected_img = img.copy()
cv2.drawContours(detected_img, [screenCnt], -1, (0, 255, 0), 3)

mask = np.zeros(gray.shape, np.uint8)
cv2.drawContours(mask, [screenCnt], 0, 255, -1)

masked = cv2.bitwise_and(gray, gray, mask=mask)

(x, y) = np.where(mask == 255)
(topx, topy) = (np.min(x), np.min(y))
(bottomx, bottomy) = (np.max(x), np.max(y))

cropped = gray[topx:bottomx + 1, topy:bottomy + 1]

cv2.imshow("Original image", img)
cv2.imshow("Masked plate", masked)
cv2.imshow("Cropped plate", cropped)

cv2.waitKey(0)
cv2.destroyAllWindows()


text = pytesseract.image_to_string(cropped, config='--psm 11')

print("Detected license plate Number is:", text)