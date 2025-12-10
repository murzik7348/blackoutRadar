import cv2
import numpy as np
import json
import os

# Додай цей рядок до інших імпортів
from .parser import process_schedule_image 

# Твій ID адміністратора
ADMIN_ID = 6311296495

def process_schedule_image(image_path, output_json_path='schedule.json'):
    # Завантаження зображення
    img = cv2.imread(image_path)
    if img is None:
        return False, "Не вдалося відкрити файл зображення."

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # --- НАЛАШТУВАННЯ КООРДИНАТ (обрізка графіку) ---
    # Координати підібрані під стандартний скріншот
    y_start, y_end = 120, 680   
    x_start, x_end = 100, 1900  
    
    crop = gray[y_start:y_end, x_start:x_end]
    
    # Розміри сітки
    rows = 12  # 6 черг по 2 підчерги
    cols = 48  # 24 години по 30 хв
    
    h, w = crop.shape
    cell_h = h // rows
    cell_w = w // cols

    schedule_data = {}
    
    # Формування часу: 00:00, 00:30...
    time_slots = [f"{i//2:02d}:{'00' if i%2==0 else '30'}" for i in range(48)]
    queue_names = ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2", "4.1", "4.2", "5.1", "5.2", "6.1", "6.2"]

    try:
        for r in range(rows):
            q_full = queue_names[r]
            q_num = q_full.split('.')[0]
            
            if q_num not in schedule_data:
                schedule_data[q_num] = {}

            outages = []
            is_active = False
            start_t = ""

            for c in range(cols):
                cell = crop[r*cell_h:(r+1)*cell_h, c*cell_w:(c+1)*cell_w]
                
                # Якщо середня яскравість < 120 (темний) -> це відключення
                if np.mean(cell) < 120:
                    if not is_active:
                        is_active = True
                        start_t = time_slots[c]
                else:
                    if is_active:
                        is_active = False
                        end_t = time_slots[c]
                        outages.append(f"{start_t}-{end_t}")
            
            # Якщо графік закінчився, а відключення триває
            if is_active:
                outages.append(f"{start_t}-00:00")

            schedule_data[q_num][q_full] = outages

        # Зберігаємо JSON
        final_json = {"schedule": schedule_data}
        
        # Визначаємо шлях для збереження (в папку проекту)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, output_json_path)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, indent=4, ensure_ascii=False)

        return True, "Графік успішно оновлено! JSON збережено."

    except Exception as e:
        return False, f"Помилка парсингу: {str(e)}"