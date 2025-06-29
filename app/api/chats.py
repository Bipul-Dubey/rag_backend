from fastapi import APIRouter, HTTPException
from app.utils import embed_chunks
from app.database.document_crud import get_chunk_collection, get_document_collection, get_chat_collection, get_user_collection
from bson import ObjectId
import numpy as np
from app.models.chats import QueryRequest
from google.generativeai import GenerativeModel, configure
import os
from datetime import datetime
from uuid import uuid4

# Configure Gemini
api_key = os.getenv("GEN_AI_API_KEY")
if not api_key:
    raise RuntimeError("Missing GEN_AI_API_KEY in environment variables.")
configure(api_key=api_key)
gemini_model = GenerativeModel(model_name="models/gemini-1.5-flash")

# models = list_models()
# for model in models:
#     print(model.name, model.supported_generation_methods)


# Create the API router
router = APIRouter()

@router.delete("/chat/{chat_id}")
async def delete_chat(chat_id: str):
    chat_collection = get_chat_collection()
    result = await chat_collection.delete_one({"_id": ObjectId(chat_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Chat not found or already deleted")
    return {"message": "Chat deleted successfully"}

@router.post("/query")
async def query_documents(request: QueryRequest):
    # Step 1: Embed the query
    query_embedding = embed_chunks([request.query])[0]

    # Step 2: Build filter for chunks
    chunk_collection = get_chunk_collection()
    chunk_filter = {"user_id": request.user_id}
    if request.doc_ids:
        valid_ids = [ObjectId(doc_id) for doc_id in request.doc_ids if ObjectId.is_valid(doc_id)]
        if not valid_ids:
            raise HTTPException(status_code=400, detail="No valid document IDs provided.")
        chunk_filter["document_id"] = {"$in": [str(oid) for oid in valid_ids]}

    # Step 3: Fetch all relevant chunks
    chunks_cursor = chunk_collection.find(chunk_filter)
    chunks = await chunks_cursor.to_list(length=1000)
    if not chunks:
        raise HTTPException(status_code=404, detail="No chunks found for the given user and documents.")

    # Step 4: Compute similarities
    doc_embeddings = np.array([chunk["embedding"] for chunk in chunks])
    similarities = np.dot(doc_embeddings, query_embedding)
    top_indices = np.argsort(similarities)[-5:][::-1]
    top_chunks = [chunks[i] for i in top_indices]

    # Step 5: Get document info for references
    doc_ids_set = set(chunk["document_id"] for chunk in top_chunks)
    doc_collection = get_document_collection()
    docs_info = {str(doc["_id"]): doc for doc in await doc_collection.find({"_id": {"$in": [ObjectId(did) for did in doc_ids_set]}}).to_list(length=100)}

    # Step 6: Build context and unique references
    context = "\n".join(chunk["chunk"] for chunk in top_chunks)
    references = [
    {
        "doc_id": chunk["document_id"],
        "doc_name": docs_info.get(chunk["document_id"], {}).get("filename", ""),
        "doc_url": docs_info.get(chunk["document_id"], {}).get("url", ""),
        "s3_key":  docs_info.get(chunk["document_id"], {}).get("s3_key", "")
    }
    for chunk in top_chunks
    ]

    # Step 7: Generate answer using Gemini
    prompt = f"Use only this context to answer the question.\nContext:\n{context}\n\nQuestion: {request.query}\nAnswer:"
    response = gemini_model.generate_content(prompt)
    answer = response.text.strip() if hasattr(response, 'text') else str(response)
    token_count = getattr(response, "usage", {}).get("total_tokens", None)
    if token_count is None:
        token_count = len(context.split()) + len(request.query.split()) + len(answer.split())

    # Step 8: Save to chat history
    chat_collection = get_chat_collection()
    chat_id = getattr(request, 'chat_id', None)
    now = datetime.utcnow()
    # --- User stats update ---
    user_collection = get_user_collection()
    today = datetime.utcnow().date().isoformat()
    # Try to update today's stats, or create if not exists
    await user_collection.update_one(
        {"user_id": request.user_id},
        {
            "$inc": {"total_query_count": 1, "total_token_count": token_count, f"daily_stats.{today}.query_count": 1, f"daily_stats.{today}.token_count": token_count},
            "$setOnInsert": {"created_at": now}
        },
        upsert=True
    )
    # --- End user stats update ---
    if not chat_id:
        # Create new chat
        title_prompt = f"Suggest a short, descriptive chat title for this conversation under 10 words.\nQuestion: {request.query}\nAnswer: {answer}\nTitle:"
        title_response = gemini_model.generate_content(title_prompt)
        chat_name = title_response.text.strip() if hasattr(title_response, 'text') else str(title_response)
        chat_doc = {
            "user_id": request.user_id,
            "created_at": now,
            "chat_name": chat_name,
            "messages": [
                {"message_id": str(uuid4()), "role": "user", "content": request.query, "timestamp": now},
                {"message_id": str(uuid4()), "role": "assistant", "content": answer, "timestamp": now, "references": references}
            ]
        }
        result = await chat_collection.insert_one(chat_doc)
        chat_id = str(result.inserted_id)
    else:
        # Append to existing chat
        await chat_collection.update_one(
            {"_id": ObjectId(chat_id)},
            {"$push": {"messages": {"message_id": str(uuid4()), "role": "user", "content": request.query, "timestamp": now}}}
        )
        await chat_collection.update_one(
            {"_id": ObjectId(chat_id)},
            {"$push": {"messages": {"message_id": str(uuid4()), "role": "assistant", "content": answer, "timestamp": now, "references": references}}}
        )

    return{
        "message_id": str(uuid4()),
        "role": "assistant",
        "timestamp": now,
        "content": answer,
        "references": references,
        "chat_id": chat_id
    }

@router.get("/chats/{user_id}")
async def list_chats(user_id: str):
    chat_collection = get_chat_collection()
    chats = await chat_collection.find({"user_id": user_id}).to_list(length=100)
    return [
        {"chat_id": str(chat["_id"]), "created_at": chat["created_at"], "chat_name": chat.get("chat_name", "")}
        for chat in chats
    ]

@router.get("/chat/{chat_id}")
async def get_chat_history(chat_id: str):
    chat_collection = get_chat_collection()
    chat = await chat_collection.find_one({"_id": ObjectId(chat_id)})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat["chat_id"] = str(chat["_id"])
    del chat["_id"]
    return chat
