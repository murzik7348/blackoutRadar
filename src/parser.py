import cv2
import numpy as np
import json
import os

def process_schedule_image(image_path, output_json_path='schedule.json'):
    img = cv2.imread(image_path)
    if img is None: return False, "Не вдалося відкрити файл."

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Координати таблиці
    y_start, y_end = 120, 680   
    x_start, x_end = 100, 1900  
    
    crop = gray[y_start:y_end, x_start:x_end] if gray.shape[0] >= y_end else gray
    
    rows, cols = 12, 48
    cell_h, cell_w = crop.shape[0] // rows, crop.shape[1] // cols
    
    schedule = {}
    time_slots = [f"{i//2:02d}:{'00' if i%2==0 else '30'}" for i in range(48)]
    queues = ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2", "4.1", "4.2", "5.1", "5.2", "6.1", "6.2"]

    try:
        for r in range(rows):
            q_num = queues[r].split('.')[0]
            if q_num not in schedule: schedule[q_num] = {}
            
            outages, is_active, start_t = [], False, ""
            for c in range(cols):
                # Поріг яскравості 120
                if np.mean(crop[r*cell_h:(r+1)*cell_h, c*cell_w:(c+1)*cell_w]) < 120:
                    if not is_active: is_active, start_t = True, time_slots[c]
                elif is_active:
                    is_active = False
                    outages.append(f"{start_t}-{time_slots[c]}")
            if is_active: outages.append(f"{start_t}-00:00")
            schedule[q_num][queues[r]] = outages

        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, "..", "data", output_json_path)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({"schedule": schedule}, f, indent=4, ensure_ascii=False)

        return True, "Графік оновлено успішно!"
    except Exception as e: return False, str(e)