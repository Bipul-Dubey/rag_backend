# app/models/document.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class DocumentIn(BaseModel):
    user_id: str
    filename: str
    filetype: str
    size: int  # in bytes
    url: str

class DocumentOut(DocumentIn):
    id: str = Field(alias="_id")
    created_at: datetime