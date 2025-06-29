from pydantic import BaseModel
from typing import List, Optional

class QueryRequest(BaseModel):
    user_id: str
    query: str
    chat_id: str
    doc_ids: Optional[List[str]] = None
