import os
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
import shutil
from typing import List, Optional
import uuid

from database import SessionLocal, engine, Base
from models import UploadedFile, FileStatus
from schemas import FileOut

UPLOAD_DIR = "uploads"
PDF_DIR = "pdfs"
ALLOWED_EXT = {".png", ".bmp", ".jpg", ".jpeg", ".eps"}

# create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Image -> PDF converter (deferred)")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ensure dirs
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

@app.post("/upload", response_model=List[FileOut])
async def upload_files(files: List[UploadFile] = File(...),
                       session_id: Optional[str] = Query(None),
                       db: Session = Depends(get_db)):
    """
    Загружает один или несколько файлов. Возвращает записи (status=pending).
    session_id можно передавать, чтобы привязать загрузку к сессии.
    """
    created = []
    for upload in files:
        ext = os.path.splitext(upload.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=400, detail=f"Extension not allowed: {ext}")

        stored_filename = f"{uuid.uuid4().hex}_{upload.filename}"
        session_folder = os.path.join(UPLOAD_DIR, session_id if session_id else "default")
        os.makedirs(session_folder, exist_ok=True)
        stored_path = os.path.join(session_folder, stored_filename)

        # save file to disk
        with open(stored_path, "wb") as out_file:
            shutil.copyfileobj(upload.file, out_file)

        # create DB record
        record = UploadedFile(
            original_filename=upload.filename,
            stored_path=stored_path,
            content_type=upload.content_type,
            status=FileStatus.pending,
            session_id=session_id
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        created.append(record)
    return [FileOut(
                id=r.id,
                original_filename=r.original_filename,
                content_type=r.content_type,
                status=r.status,
                session_id=r.session_id,
                created_at=r.created_at,
                updated_at=r.updated_at,
                pdf_ready=bool(r.pdf_path)
            ) for r in created]


@app.get("/files", response_model=List[FileOut])
def list_files(session_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Список всех файлов или для конкретной session_id.
    """
    q = db.query(UploadedFile)
    if session_id:
        q = q.filter(UploadedFile.session_id == session_id)
    q = q.order_by(UploadedFile.created_at.desc())
    results = q.all()
    return [FileOut(
                id=r.id,
                original_filename=r.original_filename,
                content_type=r.content_type,
                status=r.status,
                session_id=r.session_id,
                created_at=r.created_at,
                updated_at=r.updated_at,
                pdf_ready=bool(r.pdf_path)
            ) for r in results]

@app.get("/files/{file_id}/original")
def download_original(file_id: str, db: Session = Depends(get_db)):
    rec = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not rec:
        raise HTTPException(404, "File not found")
    if not os.path.exists(rec.stored_path):
        raise HTTPException(404, "Stored file not found on disk")
    return FileResponse(path=rec.stored_path, filename=rec.original_filename, media_type=rec.content_type or "application/octet-stream")

@app.get("/files/{file_id}/pdf")
def download_pdf(file_id: str, db: Session = Depends(get_db)):
    rec = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not rec:
        raise HTTPException(404, "File not found")
    if rec.status != FileStatus.done or not rec.pdf_path:
        # PDF ещё не готов
        return JSONResponse(status_code=202, content={"detail": "PDF not ready", "status": rec.status})
    if not os.path.exists(rec.pdf_path):
        raise HTTPException(404, "PDF file missing on disk")
    return FileResponse(path=rec.pdf_path, filename=os.path.splitext(rec.original_filename)[0] + ".pdf", media_type="application/pdf")
