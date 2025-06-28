# app/db/document_crud.py

import app.database.mongo as mongo
from datetime import datetime
from bson import ObjectId

def get_collection():
    if mongo.db is None:
        raise RuntimeError("Database not initialized. Ensure connect_to_mongo() is called.")
    return mongo.db["documents"]

async def create_document(doc: dict):
    collection = get_collection()
    doc["created_at"] = datetime.utcnow()
    result = await collection.insert_one(doc)
    return str(result.inserted_id)

async def get_documents_by_user(user_id: str):
    collection = get_collection()
    docs = await collection.find({"user_id": user_id}).to_list(length=100)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs

async def get_document_by_id(doc_id: str):
    collection = get_collection()
    doc = await collection.find_one({"_id": ObjectId(doc_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc

async def delete_document_by_id(doc_id: str):
    collection = get_collection()
    result = await collection.delete_one({"_id": ObjectId(doc_id)})
    return result.deleted_count > 0
