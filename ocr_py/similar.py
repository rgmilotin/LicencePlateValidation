"""
plate_corrector.py
==================
Romanian licence plate OCR post-processing module.

Handles every plate type currently in use in Romania:
  - Standard civilian   (county & Bucharest, 2- and 3-digit variants)
  - Electric vehicle    (green plates — same format as standard)
  - Temporary short     (red, county + 0X[XX]  up to 6 digits)
  - Temporary long      (black, county + digits, no leading zero)
  - Test / probe        (county + 3 digits + PROBE)
  - Diplomatic          (CD / TC / CO + 6 digits)
  - MAI                 (Ministry of Internal Affairs, MAI + 5 digits)
  - Military            (A + 3-7 digits)
  - Government special  (POL / SRI / GUV / DEP / SNT + digits)

Public API
----------
    predict_plate(ocr_text, confidence=None) -> PlatePrediction

Optional dependency (graceful degradation without it):
    pip install rapidfuzz python-Levenshtein
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

try:
    from rapidfuzz import process as rf_process
    from rapidfuzz.distance import Levenshtein
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False


# ---------------------------------------------------------------------------
# User-configurable constants
# ---------------------------------------------------------------------------

# Fill this list with plates you expect to see (fleet, parking, access …).
# Leave empty to skip fuzzy-DB matching.
KNOWN_PLATES: list[str] = []

# Maximum Levenshtein edit distance for a DB hit to be accepted.
FUZZY_MATCH_MAX_EDITS: int = 1

# Characters stripped from raw OCR before any processing.
_STRIP_CHARS = " -\u2013_.,/\\|()[]{}<>"

# ---------------------------------------------------------------------------
# Romanian county codes (all 41 counties + Bucharest)
# ---------------------------------------------------------------------------
_COUNTY_CODES = {
    "AB", "AR", "AG", "BC", "BH", "BN", "BT", "BV", "BR", "B",
    "BZ", "CS", "CL", "CJ", "CT", "CV", "DB", "DJ", "GL", "GR",
    "GJ", "HR", "HD", "IL", "IS", "IF", "MM", "MH", "MS", "NT",
    "OT", "PH", "SM", "SJ", "SB", "SV", "TR", "TM", "TL", "VS",
    "VL", "VN",
}

# Letters explicitly forbidden in the 3-letter suffix by Romanian law
# (Q is never issued; combinations starting with I or O are forbidden)
_FORBIDDEN_SUFFIX_START = {"I", "O"}
_FORBIDDEN_LETTERS      = {"Q"}

# ---------------------------------------------------------------------------
# OCR confusion tables
# ---------------------------------------------------------------------------
_DIGIT_FIXES:  dict[str, str] = {
    "O": "0", "I": "1", "L": "1", "S": "5",
    "B": "8", "Z": "2", "G": "6", "Q": "0", "T": "1",
}
_LETTER_FIXES: dict[str, str] = {
    "0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G",
}

# ---------------------------------------------------------------------------
# Plate variant definitions
# ---------------------------------------------------------------------------
# Each entry:
#   name        — human-readable plate category
#   regex       — matches the *already-corrected* normalised string
#   mask        — positional hint string (L=letter, D=digit, *=either, _=skip)
#                 Applied speculatively before the regex check.
#                 Use "" for plates where positional fixing doesn't help.
#
# Variants are tried in ORDER — put the most common / most specific first.

@dataclass(frozen=True)
class _Variant:
    name:  str
    regex: str
    mask:  str = ""


_VARIANTS: list[_Variant] = [

    # -----------------------------------------------------------------------
    # 1. Standard civilian — Bucharest B + 2D + 3L  (6 chars)
    # -----------------------------------------------------------------------
    _Variant(
        name  = "standard_bucharest_2d",
        regex = r"^B[0-9]{2}[A-Z]{3}$",
        mask  = "LDDLLL",
    ),

    # -----------------------------------------------------------------------
    # 2. Standard civilian — Bucharest B + 3D + 3L  (7 chars)
    # -----------------------------------------------------------------------
    _Variant(
        name  = "standard_bucharest_3d",
        regex = r"^B[0-9]{3}[A-Z]{3}$",
        mask  = "LDDDLLL",
    ),

    # -----------------------------------------------------------------------
    # 3. Standard civilian — county 2L + 2D + 3L  (7 chars)
    # -----------------------------------------------------------------------
    _Variant(
        name  = "standard_county_2d",
        regex = r"^[A-Z]{2}[0-9]{2}[A-Z]{3}$",
        mask  = "LLDDLLL",
    ),

    # -----------------------------------------------------------------------
    # 4. Standard civilian — county 2L + 3D + 3L  (8 chars)
    # -----------------------------------------------------------------------
    _Variant(
        name  = "standard_county_3d",
        regex = r"^[A-Z]{2}[0-9]{3}[A-Z]{3}$",
        mask  = "LLDDDLLL",
    ),

    # -----------------------------------------------------------------------
    # 5. Diplomatic  CD/TC/CO + 3D + 3D  (8 chars)
    #    e.g. CD125001  TC166101  CO105101
    # -----------------------------------------------------------------------
    _Variant(
        name  = "diplomatic",
        regex = r"^(?:CD|TC|CO)[0-9]{3}[0-9]{3}$",
        mask  = "LLDDDDDD",
    ),

    # -----------------------------------------------------------------------
    # 6. MAI (Ministry of Internal Affairs)  MAI + 5D  (8 chars)
    #    e.g. MAI12345
    # -----------------------------------------------------------------------
    _Variant(
        name  = "mai",
        regex = r"^MAI[0-9]{5}$",
        mask  = "LLLDDDD",   # MAI is fixed; D fixes applied to digit zone only
    ),

    # -----------------------------------------------------------------------
    # 7. Military  A + 3-7D  (4-8 chars)
    #    e.g. A12345
    # -----------------------------------------------------------------------
    _Variant(
        name  = "military",
        regex = r"^A[0-9]{3,7}$",
        mask  = "LDDDDDDDD",
    ),

    # -----------------------------------------------------------------------
    # 8. Government special codes  POL/SRI/GUV/DEP/SNT + 2D + 3L  (8 chars)
    #    e.g. POL12ABC   (same civilian format with reserved suffix)
    # -----------------------------------------------------------------------
    _Variant(
        name  = "government_special",
        regex = r"^(?:POL|SRI|GUV|DEP|SNT)[0-9]{2}[A-Z]{3}$",
        mask  = "LLLDDLLL",
    ),

    # -----------------------------------------------------------------------
    # 9. Temporary short (red plates)
    #    county + 0X to 0XXXXX  (first digit always 0, second always non-zero)
    #    county can be 1 or 2 letters → total 4-9 chars
    # -----------------------------------------------------------------------
    _Variant(
        name  = "temporary_short",
        regex = r"^[A-Z]{1,2}0[1-9][0-9]{0,4}$",
        mask  = "",   # mixed structure — skip positional fixes
    ),

    # -----------------------------------------------------------------------
    # 10. Temporary long (black / leasing plates)
    #     county + digits (no leading zero) → total 4-8 chars
    #     Harder to distinguish from standard without context; listed last
    # -----------------------------------------------------------------------
    _Variant(
        name  = "temporary_long",
        regex = r"^[A-Z]{1,2}[1-9][0-9]{2,5}$",
        mask  = "",
    ),

    # -----------------------------------------------------------------------
    # 11. Test / probe plates   county + 3D + PROBE  (9-10 chars)
    #     e.g. CJ101PROBE  B101PROBE
    # -----------------------------------------------------------------------
    _Variant(
        name  = "probe",
        regex = r"^[A-Z]{1,2}[0-9]{3}PROBE$",
        mask  = "",
    ),
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PlatePrediction:
    """
    Returned by predict_plate().

    Fields
    ------
    plate        Corrected plate string (uppercase, no spaces/dashes).
                 Empty string when no prediction could be made.
    plate_type   Matched variant name (e.g. 'standard_county_2d', 'mai', …).
    valid        True when the corrected string passes a known variant regex.
    county_valid True when the county code prefix is a real Romanian county.
                 Always False for non-civilian plate types.
    confidence   Adjusted 0.0-1.0 score (input confidence ± heuristics).
    raw          Original OCR string, unchanged.
    corrections  Human-readable list of changes applied.
    partial      Plate with '?' at low-confidence positions.
                 Only populated when per_char_conf is supplied.
    db_match     Nearest plate from KNOWN_PLATES if a fuzzy match ran.
    """
    plate:        str           = ""
    plate_type:   str           = "unknown"
    valid:        bool          = False
    county_valid: bool          = False
    confidence:   float         = 0.0
    raw:          str           = ""
    corrections:  list[str]     = field(default_factory=list)
    partial:      str           = ""
    db_match:     Optional[str] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Unicode → ASCII → uppercase → strip separators."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", errors="ignore").decode("ascii")
    return text.upper().translate(str.maketrans("", "", _STRIP_CHARS))


def _apply_mask(text: str, mask: str,
                notes: Optional[list[str]] = None) -> str:
    """
    Apply positional confusion fixes.
    Pass notes=None for a speculative dry-run (no side effects).
    """
    if not mask:
        return text
    result = []
    for i, ch in enumerate(text):
        m = mask[i] if i < len(mask) else "*"
        if m == "D" and ch in _DIGIT_FIXES:
            fixed = _DIGIT_FIXES[ch]
            if notes is not None:
                notes.append(f"pos {i}: '{ch}'->'{fixed}' (letter->digit fix)")
            result.append(fixed)
        elif m == "L" and ch in _LETTER_FIXES:
            fixed = _LETTER_FIXES[ch]
            if notes is not None:
                notes.append(f"pos {i}: '{ch}'->'{fixed}' (digit->letter fix)")
            result.append(fixed)
        else:
            result.append(ch)
    return "".join(result)


def _match_variant(text: str, variant: _Variant) -> Optional[str]:
    """
    Speculatively apply variant mask, then test regex.
    Returns corrected text on success, None on failure.
    """
    candidate = _apply_mask(text, variant.mask)   # dry-run
    return candidate if re.fullmatch(variant.regex, candidate) else None


def _detect_and_correct(text: str) -> tuple[str, _Variant | None]:
    """
    Try all variants in order.  Returns (corrected_text, winning_variant).
    Returns (text, None) when nothing matches.
    """
    for variant in _VARIANTS:
        result = _match_variant(text, variant)
        if result is not None:
            return result, variant
    return text, None


def _county_prefix(plate: str, plate_type: str) -> Optional[str]:
    """Extract the county prefix from civilian plates for validation."""
    civilian = {
        "standard_bucharest_2d", "standard_bucharest_3d",
        "standard_county_2d", "standard_county_3d",
    }
    if plate_type not in civilian:
        return None
    # Bucharest: prefix is always "B" (single letter)
    if plate.startswith("B") and plate[1:2].isdigit():
        return "B"
    # County: first two letters
    return plate[:2] if len(plate) >= 2 else None


def _build_partial(text: str, per_char_conf: Optional[list[float]],
                   threshold: float = 0.65) -> str:
    if per_char_conf is None or len(per_char_conf) != len(text):
        return ""
    return "".join(
        ch if per_char_conf[i] >= threshold else "?"
        for i, ch in enumerate(text)
    )


def _fuzzy_db_match(text: str) -> Optional[tuple[str, int]]:
    if not KNOWN_PLATES or not _RAPIDFUZZ_AVAILABLE:
        return None
    result = rf_process.extractOne(
        text, KNOWN_PLATES, scorer=Levenshtein.normalized_distance
    )
    if result is None:
        return None
    best, norm_dist, _ = result
    edit_dist = round(norm_dist * max(len(text), len(best)))
    return (best, edit_dist) if edit_dist <= FUZZY_MATCH_MAX_EDITS else None


def _norm_conf(raw: Optional[float]) -> float:
    """Normalise Tesseract 0-100 or 0-1 float; treat None as 50%."""
    if raw is None:
        return 0.5
    v = float(raw)
    return v / 100.0 if v > 1.0 else v


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def predict_plate(
    ocr_text: str,
    confidence: Optional[float] = None,
    *,
    per_char_conf: Optional[list[float]] = None,
) -> PlatePrediction:
    """
    Post-process and validate a Romanian OCR licence-plate string.

    Parameters
    ----------
    ocr_text      Raw string from your OCR engine.
    confidence    Overall read confidence.
                  Accepts 0-1 float OR 0-100 int (Tesseract style).
                  Pass None to treat as 50%.
    per_char_conf Per-character confidence scores (0-1), same length as
                  the normalised text.  Low-confidence positions appear
                  as '?' in result.partial.

    Returns
    -------
    PlatePrediction  — see class docstring for field descriptions.
    """
    pred = PlatePrediction(raw=ocr_text)
    notes: list[str] = []

    # 1. Normalise
    text = _normalise(ocr_text)
    if not text:
        pred.corrections = ["empty input after normalisation"]
        return pred

    # 2. Confidence
    conf = _norm_conf(confidence)
    pred.confidence = conf
    if conf < 0.30:
        notes.append(f"low OCR confidence ({conf:.0%}) -- result may be unreliable")

    # 3. Detect plate type & apply confusion fixes speculatively
    corrected, winner = _detect_and_correct(text)

    if winner is not None:
        pred.plate_type = winner.name
        pred.valid = True
        notes.append(f"plate type: {winner.name}")
        # Replay mask application with notes to record what changed
        if winner.mask:
            _apply_mask(text, winner.mask, notes)
    else:
        pred.plate_type = "unknown"
        pred.valid = False
        notes.append("no Romanian plate format matched")

    # 4. County code validation (civilian plates only)
    prefix = _county_prefix(corrected, pred.plate_type)
    if prefix is not None:
        if prefix in _COUNTY_CODES:
            pred.county_valid = True
        else:
            pred.county_valid = False
            notes.append(f"county code '{prefix}' is not a valid Romanian county")

    # 5. Partial plate (per-character confidence)
    pred.partial = _build_partial(corrected, per_char_conf)

    # 6. Fuzzy DB match
    db_result = _fuzzy_db_match(corrected)
    if db_result:
        db_plate, edits = db_result
        pred.db_match = db_plate
        if edits == 0:
            notes.append("exact match in known-plate DB")
        else:
            notes.append(f"fuzzy DB match '{db_plate}' ({edits} edit(s))")
            if not pred.valid:
                corrected = db_plate
                pred.valid = True
                pred.confidence = min(pred.confidence + 0.15, 1.0)
                notes.append("plate replaced with DB match")

    # 7. Confidence adjustment heuristics
    fix_count = sum(1 for n in notes if "fix)" in n)
    if pred.valid:
        pred.confidence = min(pred.confidence + 0.10, 1.0)
    if pred.county_valid:
        pred.confidence = min(pred.confidence + 0.05, 1.0)
    if fix_count:
        pred.confidence = max(pred.confidence - 0.04 * fix_count, 0.0)

    pred.plate = corrected
    pred.corrections = notes
    return pred


# ---------------------------------------------------------------------------
# Smoke-test   python plate_corrector.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        # raw                   conf  expected       type                    description
        # ── Standard civilian ──────────────────────────────────────────────
        ("B 12 ABC",            92,   "B12ABC",      "standard_bucharest_2d", "Bucharest 2-digit"),
        ("B 123 ABC",           91,   "B123ABC",     "standard_bucharest_3d", "Bucharest 3-digit"),
        ("B 1Z ABC",            78,   "B12ABC",      "standard_bucharest_2d", "Bucharest Z->2 digit fix"),
        ("B 12 AB0",            80,   "B12ABO",      "standard_bucharest_2d", "Bucharest 0->O letter fix"),
        ("CJ 45 XYZ",           88,   "CJ45XYZ",     "standard_county_2d",   "County 2-digit"),
        ("TM 123 XYZ",          91,   "TM123XYZ",    "standard_county_3d",   "County 3-digit"),
        ("CJ 4S XYZ",           74,   "CJ45XYZ",     "standard_county_2d",   "County S->5 fix"),
        ("CJ 45 XY0",           83,   "CJ45XYO",     "standard_county_2d",   "County 0->O fix"),
        ("ABI2 CDE",            70,   "AB12CDE",     "standard_county_2d",   "I->1 digit fix"),
        ("ab12 cde",            90,   "AB12CDE",     "standard_county_2d",   "lowercase input"),
        # ── Diplomatic ─────────────────────────────────────────────────────
        ("CD 125 001",          88,   "CD125001",    "diplomatic",           "CD diplomatic"),
        ("TC 166 101",          85,   "TC166101",    "diplomatic",           "TC consular"),
        ("CO 105 101",          87,   "CO105101",    "diplomatic",           "CO consulate"),
        # ── MAI ────────────────────────────────────────────────────────────
        ("MAI 12345",           90,   "MAI12345",    "mai",                  "MAI standard"),
        ("MAI 1234S",           72,   "MAI12345",    "mai",                  "MAI S->5 digit fix"),
        # ── Military ───────────────────────────────────────────────────────
        ("A 12345",             86,   "A12345",      "military",             "Military 5-digit"),
        ("A 1234567",           84,   "A1234567",    "military",             "Military 7-digit"),
        # ── Government special ─────────────────────────────────────────────
        ("POL 12 ABC",          91,   "POL12ABC",    "government_special",   "Police"),
        ("SRI 45 XYZ",          89,   "SRI45XYZ",    "government_special",   "Intelligence service"),
        ("GUV 33 DEF",          93,   "GUV33DEF",    "government_special",   "Government"),
        # ── Temporary ──────────────────────────────────────────────────────
        ("CJ 012",              82,   "CJ012",       "temporary_short",      "Temp short 3-digit"),
        ("B 01234",             81,   "B01234",      "temporary_short",      "Temp short Bucharest"),
        ("CJ 12345",            80,   "CJ12345",     "temporary_long",       "Temp long"),
        # ── Probe ──────────────────────────────────────────────────────────
        ("CJ 101 PROBE",        85,   "CJ101PROBE",  "probe",                "Test/probe plate"),
        # ── Edge cases ─────────────────────────────────────────────────────
        ("",                    50,   "",            "unknown",              "Empty input"),
        ("RANDOMJUNK",          30,   "RANDOMJUNK",  "unknown",              "Unrecognised plate"),
    ]

    passed = 0
    print(f"\n  {'RAW':<18} {'C':>3}  {'GOT':<12} {'EXP':<12} "
          f"{'V':<5} {'TYPE':<24}  NOTES")
    print("-" * 105)
    for raw, conf, expected, exp_type, desc in tests:
        p = predict_plate(raw, confidence=conf)
        plate_ok = p.plate == expected
        type_ok  = p.plate_type == exp_type
        ok = plate_ok and type_ok
        passed += ok
        marker = "OK" if ok else ("P!" if plate_ok else "XX")
        note_str = "; ".join(p.corrections) or "--"
        print(f"  {marker}  {raw!r:<16} {conf:>3}%  {p.plate:<12} "
              f"{expected:<12} {str(p.valid):<5} {p.plate_type:<24}  {note_str}")

    total = len(tests)
    print(f"\n{passed}/{total} tests passed"
          + (" -- all good!" if passed == total else ""))
    print("\nQuick-start:")
    print("  from plate_corrector import predict_plate")
    print("  r = predict_plate('MAI 1234S', confidence=72)")
    print("  print(r.plate, r.plate_type, r.valid, r.confidence)")