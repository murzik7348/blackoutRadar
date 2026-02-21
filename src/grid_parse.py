import io, os, re
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import cv2
import pytesseract
from PIL import Image

def _img_from_bytes(data: bytes):
    pil = Image.open(io.BytesIO(data)).convert("RGB")
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

def _detect_subqueue_rows(img_bgr) -> List[Tuple[str, int, int]]:
    """Знаходимо підчерги типу '1-1','2-2' зліва (label, y_center, right_edge)."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.convertScaleAbs(gray, alpha=1.2, beta=10)
    data = pytesseract.image_to_data(
        gray, lang=os.getenv("OCR_LANGS", "ukr+eng"),
        config="--psm 6", output_type=pytesseract.Output.DICT
    )
    rows = []
    for i, text in enumerate(data["text"]):
        t = text.strip()
        if re.fullmatch(r"\d+\s*[-–—]\s*\d+", t):
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            t_norm = re.sub(r"\s*", "", t).replace("—","-").replace("–","-")
            rows.append((t_norm, y + h//2, x + w))
    rows.sort(key=lambda r: r[1])
    return rows

def _grid_roi(img_bgr, left_hint: Optional[int]=None) -> Tuple[int,int,int,int]:
    """Орієнтовно виділяємо область таблиці з часами."""
    h, w = img_bgr.shape[:2]
    x1 = max(int((left_hint or w*0.15) + 10), 0)
    y1 = int(h*0.12); x2 = int(w*0.985); y2 = int(h*0.95)
    roi = img_bgr[y1:y2, x1:x2]
    edges = cv2.Canny(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), 60, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100,
                            minLineLength=int((y2-y1)*0.6), maxLineGap=10)
    if lines is not None:
        xs = []
        for l in lines:
            x1l,y1l,x2l,y2l = l[0]
            if abs(x1l-x2l) < 3 and abs(y2l-y1l) > (y2-y1)*0.6:
                xs.extend([x1l, x2l])
        if xs:
            rx1 = max(0, min(xs)-5); rx2 = min(roi.shape[1]-1, max(xs)+5)
            return (x1+rx1, y1, x1+rx2, y2)
    return (x1, y1, x2, y2)

def _mask_colored(img_bgr):
    """Маска кольорових блоків (відсікаємо сірі/білі клітинки та сітку)."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    H,S,V = cv2.split(hsv)
    mask = (S > 40) & (V > 120)
    mask = (mask.astype(np.uint8))*255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return mask

def _slots_from_row(mask_row: np.ndarray, slots: int=48, thresh_ratio: float=0.08):
    """Бінаримо по 30-хв слотах і зливаємо у проміжки."""
    h, w = mask_row.shape[:2]
    slot_w = w / slots
    on = []
    for i in range(slots):
        xs = int(round(i*slot_w)); xe = int(round((i+1)*slot_w))
        xs = max(0,xs); xe = min(w,xe)
        cell = mask_row[:, xs:xe]
        ratio = float(cell.mean())/255.0 if cell.size else 0.0
        on.append(ratio >= thresh_ratio)
    spans = []
    i = 0
    while i < slots:
        if on[i]:
            j = i+1
            while j < slots and on[j]: j += 1
            spans.append((i, j))
            i = j
        else:
            i += 1
    return spans

def extract_grid(data: bytes) -> Dict[str, Any]:
    img = _img_from_bytes(data)
    subrows = _detect_subqueue_rows(img)
    if not subrows:
        return {"queues": [], "mode_used": "grid"}

    left_hint = max(r[2] for r in subrows)
    x1,y1,x2,y2 = _grid_roi(img, left_hint=left_hint)
    grid = img[y1:y2, x1:x2]
    mask = _mask_colored(grid)

    h = grid.shape[0]
    # межі рядків за y — по середині між сусідніми підчергами
    rows_bounds = []
    for idx,(label,yc,_) in enumerate(subrows):
        yc_rel = int(np.clip(yc - y1, 0, h-1))
        y_prev = int(np.clip((subrows[idx-1][1]-y1) if idx>0 else yc_rel - h*0.05, 0, h-1))
        y_next = int(np.clip((subrows[idx+1][1]-y1) if idx+1<len(subrows) else yc_rel + h*0.05, 0, h-1))
        y_top = int((y_prev + yc_rel)/2)
        y_bot = int((yc_rel + y_next)/2)
        if y_bot - y_top < 6:
            y_top = max(0, yc_rel-5); y_bot = min(h, yc_rel+5)
        rows_bounds.append((label, y_top, y_bot))

    result = []
    for label, yt, yb in rows_bounds:
        spans = _slots_from_row(mask[yt:yb, :], slots=48, thresh_ratio=0.08)
        m = re.match(r"(\d+)-(\d+)", label)
        qnum = int(m.group(1)) if m else None
        intervals = []
        for s,e in spans:
            st_min = s*30; en_min = e*30
            sh, sm = divmod(st_min, 60); eh, em = divmod(en_min, 60)
            intervals.append([f"{sh:02d}:{sm:02d}", f"{eh:02d}:{em:02d}"])
        if intervals:
            result.append({"queue": qnum, "subqueue": label, "intervals": intervals})
    return {"queues": result, "mode_used": "grid"}
