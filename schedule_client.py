import requests
from typing import Optional, Dict, Any

class ScheduleExtractorClient:
    def __init__(self, base_url: str="http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def extract_schedule(self, image_path: str, hint_city: Optional[str]=None, hint_oblast: Optional[str]=None) -> Dict[str, Any]:
        url = f"{self.base_url}/extract"
        params = {}
        if hint_city: params["hint_city"] = hint_city
        if hint_oblast: params["hint_oblast"] = hint_oblast
        with open(image_path, "rb") as f:
            files = {"image": (image_path, f, "application/octet-stream")}
            r = requests.post(url, params=params, files=files, timeout=120)
        r.raise_for_status()
        return r.json()
