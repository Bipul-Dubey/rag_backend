# app/db/document_crud.py
import app.database.mongo as mongo
from datetime import datetime
from bson import ObjectId


def get_document_collection():
    if mongo.db is None:
        raise RuntimeError("Database not initialized. Ensure connect_to_mongo() is called.")
    return mongo.db["documents"]

def get_chunk_collection():
    if mongo.db is None:
        raise RuntimeError("Database not initialized. Ensure connect_to_mongo() is called.")
    return mongo.db["document_chunks"]

def get_chat_collection():
    if mongo.db is None:
        raise RuntimeError("Database not initialized. Ensure connect_to_mongo() is called.")
    return mongo.db["chats"]

async def create_document(doc: dict):
    collection = get_document_collection()
    doc["created_at"] = datetime.utcnow()
    doc["status"] = "pending"
    result = await collection.insert_one(doc)
    return str(result.inserted_id)

async def get_documents_by_user(user_id: str):
    collection = get_document_collection()
    docs = await collection.find({"user_id": user_id}).to_list(length=100)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs

async def get_document_by_id(doc_id: str):
    collection = get_document_collection()
    doc = await collection.find_one({"_id": ObjectId(doc_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc

async def delete_document_by_id(doc_id: str):
    collection = get_document_collection()
    result = await collection.delete_one({"_id": ObjectId(doc_id)})
    return result.deleted_count > 0

async def update_status(doc_id: str, status: str):
    collection = get_document_collection()
    await collection.update_one(
        {"_id": ObjectId(doc_id)},
        {"$set": {"status": status}}
    )

async def store_chunks(doc_id: str, user_id: str, chunks: list[str], embeddings: list[list[float]]):
    chunks_collection = get_chunk_collection()
    documents = [
        {
            "document_id": doc_id,
            "user_id": user_id,
            "chunk": chunk,
            "embedding": embedding
        }
        for chunk, embedding in zip(chunks, embeddings)
    ]
    await chunks_collection.insert_many(documents)

async def ensure_indexes():
    # Ensure compound index on user_id and document_id in document_chunks
    collection = get_document_collection()
    await collection.create_index([("user_id", 1), ("document_id", 1)])
    # Ensure compound index on user_id and document_id in document_chunks
    chunk_collection = get_chunk_collection()
    await chunk_collection.create_index([("user_id", 1), ("document_id", 1)])