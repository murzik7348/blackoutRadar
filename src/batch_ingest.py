import argparse, os, json
from ocr_service.extract import extract_from_image

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Папка з зображеннями")
    ap.add_argument("--out", required=True, help="Папка для JSON")
    ap.add_argument("--hint_city", default=None)
    ap.add_argument("--hint_oblast", default=None)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    exts = {".png",".jpg",".jpeg",".webp",".bmp",".tif",".tiff"}
    for root,_,files in os.walk(args.input):
        for name in files:
            if os.path.splitext(name.lower())[1] in exts:
                p = os.path.join(root,name)
                with open(p, "rb") as fh:
                    data = fh.read()
                res = extract_from_image(data, hint_city=args.hint_city, hint_oblast=args.hint_oblast)
                out_name = os.path.splitext(name)[0] + ".json"
                with open(os.path.join(args.out, out_name), "w", encoding="utf-8") as out:
                    json.dump(res, out, ensure_ascii=False, indent=2)
                print(f"[OK] {name} -> {out_name}")

if __name__ == "__main__":
    main()
