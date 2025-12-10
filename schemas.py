from pydantic import BaseModel
from typing import Optional
import datetime
from models import FileStatus

class FileOut(BaseModel):
    id: str
    original_filename: str
    content_type: Optional[str]
    status: FileStatus
    session_id: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    pdf_ready: bool

    class Config:
        orm_mode = True
