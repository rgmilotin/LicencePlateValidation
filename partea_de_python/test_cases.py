DATA = [

    # 8. Heavy OCR distortion
    ("AROlA8C", "LLDDLLL"),   # l vs 1, 8 vs B/C
    ("8R01A8C", "LLDDLLL"),
    ("AR0IABG", "LLDDLLL"),
    # ================= VALID =================
    ("AR01ABC", "LLDDLLL"),
    ("TM23XYZ", "LLDDLLL"),
    ("CJ99QWE", "LLDDLLL"),
    ("BH45RTY", "LLDDLLL"),
    ("IS10AAA", "LLDDLLL"),
    ("MM88BBB", "LLDDLLL"),
    ("SV12CCC", "LLDDLLL"),
    ("GL34DDD", "LLDDLLL"),
    ("BR56EEE", "LLDDLLL"),
    ("PH78FFF", "LLDDLLL"),

    ("B123ABC", "LDDDLLL"),
    ("B999XYZ", "LDDDLLL"),
    ("B045QWE", "LDDDLLL"),
    ("B678RTY", "LDDDLLL"),
    ("B001AAA", "LDDDLLL"),

    ("MAI12345", "LLLDDDDD"),
    ("MAI54321", "LLLDDDDD"),
    ("MAI00001", "LLLDDDDD"),

    ("CD123ABC", "LLDDDLLL"),
    ("TC456DEF", "LLDDDLLL"),
    ("CD999ZZZ", "LLDDDLLL"),

    ("AR123ABC", "LLDDDLLL"),
    ("TM456DEF", "LLDDDLLL"),
    ("CJ789GHI", "LLDDDLLL"),

    ("AR123456", "LLDDDDDD"),
    ("BH654321", "LLDDDDDD"),
    ("SV000123", "LLDDDDDD"),

    ("A12345", "LDDDDD"),
    ("A54321", "LDDDDD"),


    # ================= OCR EDGE ERRORS =================

    # 1. Edge garbage (your earlier "I" issue)
    ("IAR01ABC", "LLDDLLL"),
    ("AR01ABCI", "LLDDLLL"),
    ("|AR01ABC", "LLDDLLL"),
    ("AR01ABC|", "LLDDLLL"),

    # 2. Symbol corruption
    ("AR0!ABC", "LLDDLLL"),
    ("AR@1ABC", "LLDDLLL"),
    ("A#01ABC", "LLDDLLL"),
    ("AR01A$C", "LLDDLLL"),

    # 3. OCR confusion digits/letters
    ("ARO1ABC", "LLDDLLL"),   # O instead of 0
    ("AR1ABC", "LLDDLLL"),    # missing char
    ("AR01AB8", "LLDDLLL"),   # 8 instead of C-ish confusion

    # 4. Broken segmentation
    ("AR 01 ABC", "LLDDLLL"),
    ("A R 0 1 A B C", "LLDDLLL"),

    # 5. Too short / too long
    ("AR01AB", "LLDDLLL"),
    ("AR01ABCDE", "LLDDLLL"),
    ("A1B2C3D4E5", "LLDDLLL"),

    # 6. Random junk (false positives from contour detection)
    ("XXXX", "INVALID"),
    ("1234", "INVALID"),
    ("!!!!!!", "INVALID"),
    ("-_-_-_-", "INVALID"),

    # 7. Mixed garbage + real plate
    ("XXAR01ABCXX", "LLDDLLL"),
    ("###AR01ABC###", "LLDDLLL"),


    # 9. Wrong plate structures (real-world false detections)
    ("ABCD12345", "INVALID"),
    ("123ABCDE", "INVALID"),
    ("ABCDE123", "INVALID"),

    # 10. Partial crops
    ("01ABC", "LLDDLLL"),
    ("AR01", "LLDDLLL"),
]