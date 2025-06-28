from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.models.documents import DocumentIn, DocumentOut
from app.database import document_crud
import os
from uuid import uuid4
import aiofiles
from bson import ObjectId

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=dict)
async def upload_document_file(
    user_id: str = Form(...),
    file: UploadFile = File(...)
):
    file_ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    try:
        async with aiofiles.open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # Read in 1MB chunks
                if not chunk:
                    break
                await buffer.write(chunk)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

    document_data = {
        "user_id": user_id,
        "filename": file.filename,
        "filetype": file.content_type,
        "size": os.path.getsize(file_path),
        "url": f"/uploads/{unique_name}"
    }

    try:
        doc_id = await document_crud.create_document(document_data)
    except Exception as e:
        # Clean up the uploaded file if DB insert fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return {"doc_id": str(doc_id), "url": f"/uploads/{unique_name}"}

@router.get("/user/{user_id}", response_model=list[DocumentOut])
async def get_documents(user_id: str):
    return await document_crud.get_documents_by_user(user_id)

@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(doc_id: str):
    if not ObjectId.is_valid(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    doc = await document_crud.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.delete("/{doc_id}", response_model=dict)
async def delete_document(doc_id: str):
    if not ObjectId.is_valid(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    deleted = await document_crud.delete_document_by_id(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found or already deleted")
    return {"message": "Document deleted successfully"}
