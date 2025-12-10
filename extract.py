import io, os, re, datetime
from typing import Dict, Any, List, Optional
import numpy as np
from PIL import Image
import pytesseract
import cv2
from dateutil import parser as dateparser
from grid_parse import extract_grid

TESSERACT_CMD = os.getenv("TESSERACT_CMD")
if TESSERACT_CMD and os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

UA_MONTHS = {"січня":1,"лютого":2,"березня":3,"квітня":4,"травня":5,"червня":6,
             "липня":7,"серпня":8,"вересня":9,"жовтня":10,"листопада":11,"грудня":12}

DATE_NUM = re.compile(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})")
DATE_UA  = re.compile(r"(\d{1,2})\s+(січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\s+(\d{4})", re.IGNORECASE)
TIME_RANGE   = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\s*[-–—]\s*([01]?\d|2[0-3]):[0-5]\d\b")
QUEUE_HEADER = re.compile(r"(?:черг[аи]|група)\s*(\d{1,2})", re.IGNORECASE)
CITY_HINT    = re.compile(r"(?:м\.|місто|смт|с\.)\s*([A-ЯІЇЄҐ][A-Яа-яІіЇїЄєҐґ\-\’ʼ'\s]+)")

def _img_from_bytes(data: bytes):
    pil = Image.open(io.BytesIO(data)).convert("RGB")
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

def _preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, 15, 7, 21)
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY, 35, 15)
    return cv2.resize(th, None, fx=1.3, fy=1.3, interpolation=cv2.INTER_CUBIC)

def _ocr_text(img_bin):
    return pytesseract.image_to_string(img_bin, lang=os.getenv("OCR_LANGS","ukr+rus+eng"), config="--psm 6")

def _norm(s: str) -> str:
    return re.sub(r"[ \t]+", " ", s.replace("\u2013","-").replace("\u2014","-")).strip()

def _parse_date_from_text(text: str) -> Optional[str]:
    for m in DATE_NUM.finditer(text):
        d,mn,y = m.groups(); y=int(y); y = y+2000 if y<100 else y
        try: return datetime.date(y, int(mn), int(d)).isoformat()
        except: pass
    for m in DATE_UA.finditer(text):
        d, mn_name, y = m.groups(); mn = UA_MONTHS.get(mn_name.lower())
        if mn:
            try: return datetime.date(int(y), mn, int(d)).isoformat()
            except: pass
    try:
        dt = dateparser.parse(text, dayfirst=True, fuzzy=True)
        if dt: return dt.date().isoformat()
    except: pass
    return None

def _parse_date_from_image(img) -> Optional[str]:
    h, w = img.shape[:2]
    top = cv2.cvtColor(img[0:int(h*0.18), :], cv2.COLOR_BGR2GRAY)
    top = cv2.convertScaleAbs(top, alpha=1.4, beta=15)
    t = pytesseract.image_to_string(top, lang="eng", config='--psm 6 -c tessedit_char_whitelist=0123456789./-')
    t = t.replace("\n"," ")
    m = DATE_NUM.search(t)
    if m:
        d,mn,y = m.groups(); y=int(y); y = y+2000 if y<100 else y
        try: return datetime.date(y, int(mn), int(d)).isoformat()
        except: pass
    return None

def _split_by_queues(text: str):
    blocks = {}
    matches = list(QUEUE_HEADER.finditer(text))
    if not matches: return blocks
    for i, m in enumerate(matches):
        q = m.group(1)
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        blocks[q] = text[start:end]
    return blocks

def _times_in_block(block: str):
    spans = []
    for m in TIME_RANGE.finditer(block):
        st, en = m.groups()
        z = lambda v: f"{int(v.split(':')[0]):02d}:{int(v.split(':')[1]):02d}"
        spans.append([z(st), z(en)])
    # унікалізація з порядком
    out, seen = [], set()
    for a,b in spans:
        k=(a,b)
        if k not in seen:
            seen.add(k); out.append([a,b])
    return out

def _guess_city(text: str, hint_city: Optional[str]):
    if hint_city: return hint_city.strip()
    m = CITY_HINT.search(text)
    if m:
        name = _norm(m.group(1))
        return re.sub(r"[.,;:]+$", "", name).strip()
    return None

def parse_schedule_text(text: str, hint_city: Optional[str]=None, hint_oblast: Optional[str]=None) -> Dict[str, Any]:
    t = _norm(text)
    date_iso = _parse_date_from_text(t)
    city = _guess_city(t, hint_city)
    blocks = _split_by_queues(t)
    queues = []
    if blocks:
        for q, block in blocks.items():
            intervals = _times_in_block(block)
            if intervals:
                queues.append({"queue": int(q), "intervals": intervals})
    else:
        intervals = _times_in_block(t)
        if intervals:
            queues.append({"queue": 1, "intervals": intervals})
    return {"city": city, "oblast": hint_oblast, "date": date_iso, "queues": queues, "raw_text": t}

def extract_from_image(image_bytes: bytes, hint_city: Optional[str]=None, hint_oblast: Optional[str]=None,
                       city_id: Optional[str]=None, mode: str="auto") -> Dict[str, Any]:
    img = _img_from_bytes(image_bytes)
    pre = _preprocess(img)
    text = _ocr_text(pre)

    result_text = parse_schedule_text(text, hint_city=hint_city, hint_oblast=hint_oblast)
    date_iso = result_text["date"] or _parse_date_from_image(img) or datetime.date.today().isoformat()

    queues = result_text["queues"]
    used = "ocr"

    if mode in ("auto","grid"):
        if not queues:
            grid_res = extract_grid(image_bytes)
            if grid_res.get("queues"):
                queues = grid_res["queues"]; used = "grid"
        elif mode == "grid":
            grid_res = extract_grid(image_bytes)
            if grid_res.get("queues"):
                queues = grid_res["queues"]; used = "grid"

    return {
        "city": result_text["city"] or hint_city,
        "city_id": city_id,
        "oblast": hint_oblast,
        "date": date_iso,
        "queues": queues,          # елементи можуть мати "subqueue": "1-2"
        "mode_used": used,
        "raw_text": result_text["raw_text"]
    }
