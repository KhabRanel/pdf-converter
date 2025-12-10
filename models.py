import enum
import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Enum, Text
from sqlalchemy.dialects.sqlite import BLOB
from database import Base

class FileStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"

class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)   # path on disk
    pdf_path = Column(String, nullable=True)
    content_type = Column(String, nullable=True)
    status = Column(Enum(FileStatus), default=FileStatus.pending, nullable=False)
    session_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    error_message = Column(Text, nullable=True)
