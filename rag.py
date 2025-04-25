from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
import os
import tempfile
import fitz  # PyMuPDF
import docx2txt
import numpy as np
from sentence_transformers import SentenceTransformer
from google.generativeai import configure, GenerativeModel
from database import collection
from datetime import datetime
from bson import ObjectId

rag_router = APIRouter()

# Configure Gemini
api_key = os.getenv("GEN_AI_API_KEY")
if not api_key:
    raise RuntimeError("Missing GEN_AI_API_KEY in environment variables.")
configure(api_key=api_key)
gemini_model = GenerativeModel(model_name="models/gemini-1.5-pro", generation_config={"temperature": 0.7})

# models = list_models()
# for model in models:
#     print(model.name, model.supported_generation_methods)

# Embedding model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Pydantic Schemas
class QueryRequest(BaseModel):
    user_id: str
    query: str

class DocumentResponse(BaseModel):
    uploaded_at: datetime
    filename: str
    mongo_id: str

# Helper function to convert MongoDB ObjectId to string
def str_objectid(object_id: ObjectId) -> str:
    return str(object_id)        

# Text Extraction
def extract_text(file_path, file_ext):
    if file_ext == ".pdf":
        return "\n".join([p.get_text() for p in fitz.open(file_path)])
    elif file_ext == ".docx":
        return docx2txt.process(file_path)
    else:
        raise ValueError("Unsupported file type")

# Chunking
def chunk_text(text, chunk_size=500, overlap=100):
    return [
        text[i:i + chunk_size].strip()
        for i in range(0, len(text), chunk_size - overlap)
        if text[i:i + chunk_size].strip()
    ]

# Upload Endpoint (create/replace doc per user)
@rag_router.post("/upload")
async def upload_file(user_id: str = Form(...), file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[-1].lower()
    if ext not in [".pdf", ".docx"]:
        raise HTTPException(status_code=400, detail="Only .pdf and .docx supported")

    # Save and extract
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tmp.write(await file.read())
    tmp.close()

    try:
        text = extract_text(tmp.name, ext)
    finally:
        os.remove(tmp.name)

    # Chunk and embed
    chunks = chunk_text(text)
    embeddings = embedding_model.encode(chunks)
    uploaded_at = datetime.utcnow()

    # Delete previous document for the user
    collection.delete_many({"user_id": user_id})

    # Insert new document chunks
    docs = [{
        "user_id": user_id,
        "chunk": chunk,
        "embedding": emb.tolist(),
        "filename": file.filename,
        "uploaded_at": uploaded_at
    } for chunk, emb in zip(chunks, embeddings)]

    collection.insert_many(docs)

    return {
        "message": f"Uploaded and embedded {len(chunks)} chunks.",
        "filename": file.filename
    }

# Query Endpoint
@rag_router.post("/query")
async def query_doc(request: QueryRequest):
    query_embedding = embedding_model.encode([request.query])[0]
    user_docs = list(collection.find({"user_id": request.user_id}))

    if not user_docs:
        raise HTTPException(status_code=404, detail="No documents found for this user.")

    doc_embeddings = np.array([doc["embedding"] for doc in user_docs])
    similarities = np.dot(doc_embeddings, query_embedding)
    top_chunks = [user_docs[i]["chunk"] for i in np.argsort(similarities)[-5:][::-1]]

    context = "\n".join(top_chunks)
    prompt = f"Use only this context:\n{context}\n\nQ: {request.query}\nA:"

    response = gemini_model.generate_content(prompt)
    return {"answer": response.text.strip()}


@rag_router.get("/users/{user_id}", response_model=DocumentResponse)
async def get_user_document(user_id: str):
    # Query MongoDB to find the document based on user_id
    document = collection.find_one({"user_id": user_id})

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Return the required data with MongoDB _id renamed to mongo_id
    return DocumentResponse(
        filename=document["filename"],
        uploaded_at=document["uploaded_at"],
        mongo_id=str_objectid(document["_id"])
    )