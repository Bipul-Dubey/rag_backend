# app/models/document.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class DocumentIn(BaseModel):
    user_id: str
    filename: str
    filetype: str
    size: int  # in bytes
    url: str
    s3_key: str
    status: Literal["pending", "processing", "ready", "failed"] = "pending"


class DocumentOut(DocumentIn):
    id: str = Field(alias="_id")
    created_at: datetime