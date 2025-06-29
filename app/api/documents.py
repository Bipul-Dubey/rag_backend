from fastapi import APIRouter, HTTPException, UploadFile, File, Form,Query
from app.models.documents import  DocumentOut
from app.database import document_crud
from app.database.document_crud import store_chunks, get_document_collection
# import aiofiles
from bson import ObjectId
from app.utils import embed_chunks, upload_file_to_s3, generate_presigned_url
from fastapi import UploadFile, File, Form, HTTPException
import tempfile
import boto3
import os
from unstructured.partition.auto import partition

s3_client = boto3.client("s3")

router = APIRouter()

# UPLOAD_DIR = "uploads"
# os.makedirs(UPLOAD_DIR, exist_ok=True)

def extract_text_from_s3(bucket: str, s3_key: str) -> str:
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tmp_file:
            # Download file from S3 to temp path
            s3_client.download_file(bucket, s3_key, tmp_file.name)
            
            # Partition using unstructured
            elements = partition(filename=tmp_file.name)
            text = "\n".join([el.text for el in elements if el.text])
            return text

    except Exception as e:
        raise RuntimeError(f"Failed to extract text from S3 file: {str(e)}")


def chunk_text(text: str, max_tokens: int = 500) -> list[str]:
    import re
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        token_count = len(sentence.split())
        if current_length + token_count > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_length = token_count
        else:
            current_chunk.append(sentence)
            current_length += token_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


@router.post("/upload", response_model=dict)
async def upload_document_file(
    user_id: str = Form(...),
    file: UploadFile = File(...),
):
    file_data = await file.read()

    try:
        s3_result = await upload_file_to_s3(
            user_id=user_id,
            file_data=file_data,
            original_filename=file.filename,
            content_type=file.content_type,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    document_data = {
        "user_id": user_id,
        "filename": s3_result["filename"],
        "filetype": s3_result["content_type"],
        "size": s3_result["size"],
        "s3_key": s3_result["s3_key"],
        "url": s3_result["url"]
    }

    try:
        doc_id = await document_crud.create_document(document_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {"doc_id": str(doc_id), "s3_key": s3_result["s3_key"]}

# @router.post("/upload", response_model=dict)
# async def upload_document_file(
#     user_id: str = Form(...),
#     file: UploadFile = File(...)
# ):
#     file_ext = os.path.splitext(file.filename)[1]
#     unique_name = f"{uuid4()}{file_ext}"
#     file_path = os.path.join(UPLOAD_DIR, unique_name)

#     try:
#         async with aiofiles.open(file_path, "wb") as buffer:
#             while True:
#                 chunk = await file.read(1024 * 1024)  # Read in 1MB chunks
#                 if not chunk:
#                     break
#                 await buffer.write(chunk)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

#     document_data = {
#         "user_id": user_id,
#         "filename": file.filename,
#         "filetype": file.content_type,
#         "size": os.path.getsize(file_path),
#         "url": f"/uploads/{unique_name}"
#     }

#     try:
#         doc_id = await document_crud.create_document(document_data)
#     except Exception as e:
#         # Clean up the uploaded file if DB insert fails
#         if os.path.exists(file_path):
#             os.remove(file_path)
#         raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
#     return {"doc_id": str(doc_id), "url": f"/uploads/{unique_name}"}

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



@router.post("/{doc_id}/embed")
async def embed_document(doc_id: str):
    doc = await document_crud.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.get("status") == "ready":
        return {"message": "Document already embedded"}

    # Mark status as processing
    await document_crud.update_status(doc_id, "processing")

    try:
        text = extract_text_from_s3(bucket=os.getenv("AWS_S3_BUCKET_NAME"), s3_key=doc["s3_key"])

        # Step 2: Chunk and embed
        chunks = chunk_text(text)                 # You need to implement this
        embeddings = embed_chunks(chunks)   # You need to implement this
        if not embeddings:
            raise RuntimeError("No embeddings generated")

        # Step 3: Save chunks + embeddings
        await store_chunks(doc_id, doc["user_id"], chunks, embeddings)

        # Step 4: Mark as ready
        await document_crud.update_status(doc_id, "ready")
        return {"message": "Embedding complete"}

    except Exception as e:
        await document_crud.update_status(doc_id, "failed")
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")


@router.get("/preview-url", response_model=dict)
async def get_preview_url(document_id: str = Query(...)):
    print("Received document_id:", repr(document_id))  # log with repr to catch quotes
    document_id = document_id.strip('"')  # just in case

    if not ObjectId.is_valid(document_id):
        raise HTTPException(status_code=400, detail="Invalid document ID format hkjhkjh")

    collection = get_document_collection()
    document = await collection.find_one({"_id": ObjectId(document_id)})

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if "s3_key" not in document:
        raise HTTPException(status_code=400, detail="Document is missing S3 key")

    presigned_url = generate_presigned_url(document["s3_key"])

    if not presigned_url:
        raise HTTPException(status_code=500, detail="Failed to generate preview URL")

    return {"preview_url": presigned_url}
