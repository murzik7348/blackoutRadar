from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Literal
from extract import extract_from_image
import hashlib

app = FastAPI(title="uk-blackout-ai", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

@app.get("/")
def root():
    return {"ok": True, "use": ["/health", "/extract", "/docs"]}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/extract")
async def extract(
    image: UploadFile = File(...),
    hint_city: Optional[str] = Query(default=None),
    hint_oblast: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    oblast: Optional[str] = Query(default=None),
    city_id: Optional[str] = Query(default=None),
    mode: Literal["auto","ocr","grid"] = Query(default="auto")
):
    data = await image.read()
    h = hashlib.sha256(data).hexdigest()
    try:
        result = extract_from_image(
            data,
            hint_city=city or hint_city,
            hint_oblast=oblast or hint_oblast,
            city_id=city_id,
            mode=mode
        )
        result["source_hash"] = f"sha256:{h}"
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e), "source_hash": f"sha256:{h}"}, status_code=500)
