from __future__ import annotations

import re
from typing import Dict, Any
from datetime import datetime
from PIL import Image, ImageOps, ImageFilter
import pytesseract


DATE_RX = re.compile(r"(\d{2})[\./-](\d{2})[\./-](\d{4})")


def _norm_date(text: str) -> str | None:
    m = DATE_RX.search(text)
    if not m:
        return None
    d, mth, y = m.groups()
    try:
        return datetime(int(y), int(mth), int(d)).strftime("%d/%m/%Y")
    except Exception:
        return None


def _preprocess(img: Image.Image) -> Image.Image:
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g)
    g = g.filter(ImageFilter.SHARPEN)
    w, h = g.size
    if max(w, h) < 1400:
        g = g.resize((int(w * 1.5), int(h * 1.5)), Image.LANCZOS)
    return g


def read_morocco_front(image_path: str) -> Dict[str, Any]:
    """Very simple OCR fallback for Moroccan ID front side.

    Extracts:
      - date_of_birth_formatted via pattern like 13.09.1984 near "Né le"
      - expiration_date_formatted via the largest future-looking date (e.g., 01.12.2031)
      - number heuristically (e.g., JA118202)
      - names/surname heuristically (best-effort, may be empty)
    """
    img = Image.open(image_path)
    proc = _preprocess(img)
    # General OCR for full text (labels, words)
    text_general = pytesseract.image_to_string(proc, config="--psm 6 --oem 1", lang="eng+fra")
    # Digits-focused OCR to capture dates robustly
    text_digits = pytesseract.image_to_string(
        proc,
        config="--psm 6 --oem 0 -c tessedit_char_whitelist=0123456789./-",
        lang="eng",
    )
    # Alnum pass for CIN number
    text_alnum = pytesseract.image_to_string(
        proc,
        config="--psm 6 --oem 0 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        lang="eng",
    )
    lines = [ln.strip() for ln in text_general.splitlines() if ln.strip()]
    full = " \n".join(lines)

    # Dates
    dob = None
    exp = None
    # Look for a line containing 'Ne' or 'Né' and a date
    for ln in lines:
        if any(k in ln.lower() for k in ["ne le", "né le", "nele", "ne", "né"]):
            dob = _norm_date(ln)
            if dob:
                break
    # If not found, choose the earliest date from combined texts
    all_dates = DATE_RX.findall(" \n".join([full, text_digits]))
    parsed = []
    for d, mth, y in all_dates:
        try:
            parsed.append(datetime(int(y), int(mth), int(d)))
        except Exception:
            pass
    if not dob and parsed:
        dob = min(parsed).strftime("%d/%m/%Y")

    # Expiration: look for "Valable" line, else last date in text
    for ln in lines[::-1]:
        if "valable" in ln.lower():
            exp = _norm_date(ln)
            break
    if not exp and parsed:
        exp = max(parsed).strftime("%d/%m/%Y")

    # Number heuristic: typical Moroccan CIN like JA118202
    num_match = re.search(r"\b[A-Z]{1,3}\d{5,8}\b", text_alnum + "\n" + full)
    number = num_match.group(0) if num_match else ""

    # Names heuristic: prioritize uppercase lines, otherwise fallback to best tokens
    upper_lines = [ln for ln in lines if ln.isupper() and 2 <= len(ln) <= 30 and ln.replace(' ', '').isalpha()]
    surname = ""
    names = ""
    if upper_lines:
        # Per user preference: first line -> surname, second -> names
        if len(upper_lines) >= 2:
            surname = upper_lines[0].title()
            names = upper_lines[1].title()
        else:
            surname = upper_lines[0].title()

    # Try to find locality (e.g., GUELMIM)
    locality = None
    m_loc = re.search(r"\bGUELMIM\b", full, re.IGNORECASE)
    if m_loc:
        locality = m_loc.group(0).upper()

    # Heuristic region OCR for Moroccan front layout (fallback if still missing)
    W, H = proc.size

    def _roi(box):
        x1, y1, x2, y2 = box
        return proc.crop((int(x1*W), int(y1*H), int(x2*W), int(y2*H)))

    def _ocr_clean(im, cfg):
        g = ImageOps.grayscale(im)
        g = ImageOps.autocontrast(g)
        g = g.filter(ImageFilter.SHARPEN)
        return pytesseract.image_to_string(g, config=cfg, lang="eng+fra").strip()

    # DOB near middle-right
    if not (dob):
        dob_roi = _roi((0.56, 0.40, 0.82, 0.54))
        s = _ocr_clean(dob_roi, "--psm 7 --oem 0 -c tessedit_char_whitelist=0123456789./-")
        nd = _norm_date(s)
        if nd:
            dob = nd

    # Expiry at bottom-right
    if not (exp):
        exp_roi = _roi((0.60, 0.88, 0.98, 0.98))
        s = _ocr_clean(exp_roi, "--psm 7 --oem 0 -c tessedit_char_whitelist=0123456789./-")
        ne = _norm_date(s)
        if ne:
            exp = ne

    # CIN number bottom-left after N°
    if not number:
        num_roi = _roi((0.06, 0.86, 0.38, 0.95))
        s = _ocr_clean(num_roi, "--psm 7 --oem 0 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        m_num = re.search(r"[A-Z]{1,3}\s*\d{5,8}", s)
        if m_num:
            number = m_num.group(0).replace(" ", "")

    # Names block mid-left (two lines)
    if not (surname and names):
        nm_roi = _roi((0.38, 0.22, 0.70, 0.42))
        s = _ocr_clean(nm_roi, "--psm 6 --oem 1")
        nm_lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
        up = [ln for ln in nm_lines if ln.isupper() and ln.replace(' ', '').isalpha()]
        if len(up) >= 2:
            surname = surname or up[0].title()
            names = names or up[1].title()
        elif len(up) == 1:
            surname = surname or up[0].title()

    return {
        "mrz_type": "FRONT_FALLBACK",
        "country": locality or "MAR",
        "nationality": "MAR",
        "number": number,
        "surname": surname,
        "names": names,
        "date_of_birth_formatted": dob or "",
        "expiration_date_formatted": exp or "",
        "raw_ocr": full,
    }


