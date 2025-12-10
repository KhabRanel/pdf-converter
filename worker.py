import time
import os
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import UploadedFile, FileStatus
from PIL import Image, ImageFile
import traceback

ImageFile.LOAD_TRUNCATED_IMAGES = True

PDF_DIR = "pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

SUPPORTED_INPUT = {".png", ".bmp", ".jpg", ".jpeg", ".eps"}

def convert_to_pdf(input_path: str, output_path: str):
    # Открываем через Pillow, делаем RGB (EPS may require ghosts)
    with Image.open(input_path) as img:
        # Для EPS Pillow может вернуть a single-frame image.
        # Убедимся, что изображение в RGB
        if img.mode in ("RGBA", "LA") or (img.mode == "P"):
            # flatten alpha onto white
            bg = Image.new("RGB", img.size, (255,255,255))
            bg.paste(img, mask=img.split()[-1] if "A" in img.getbands() else None)
            img = bg
        else:
            img = img.convert("RGB")
        # Save single-page PDF
        img.save(output_path, "PDF", resolution=100.0)

def process_one(db: Session, rec: UploadedFile):
    try:
        rec.status = FileStatus.processing
        db.add(rec)
        db.commit()
        db.refresh(rec)

        input_path = rec.stored_path
        if not os.path.exists(input_path):
            raise FileNotFoundError("Input file not found")

        ext = os.path.splitext(input_path)[1].lower()
        if ext not in SUPPORTED_INPUT:
            raise ValueError(f"Unsupported extension: {ext}")

        pdf_name = f"{rec.id}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_name)

        convert_to_pdf(input_path, pdf_path)

        rec.pdf_path = pdf_path
        rec.status = FileStatus.done
        rec.error_message = None
        db.add(rec)
        db.commit()
        print(f"[worker] Converted {rec.id} -> {pdf_path}")
    except Exception as e:
        rec.status = FileStatus.failed
        rec.error_message = (str(e) + "\n" + traceback.format_exc())[:2000]
        db.add(rec)
        db.commit()
        print(f"[worker] Failed {rec.id}: {e}")

def main_loop(poll_interval=3):
    print("Worker started, polling DB for pending files...")
    while True:
        db = SessionLocal()
        try:
            pending = db.query(UploadedFile).filter(UploadedFile.status == FileStatus.pending).order_by(UploadedFile.created_at.asc()).limit(5).all()
            if not pending:
                time.sleep(poll_interval)
                continue
            for rec in pending:
                process_one(db, rec)
        finally:
            db.close()

if __name__ == "__main__":
    main_loop()
