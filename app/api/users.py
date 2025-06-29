from fastapi import APIRouter, HTTPException
from app.database.document_crud import get_user_collection, get_chat_collection, get_document_collection, get_chunk_collection
from datetime import datetime
from bson import ObjectId

router = APIRouter()

@router.get("/user/{user_id}/stats")
async def get_user_stats(user_id: str):
    user_collection = get_user_collection()
    user = await user_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    today = datetime.utcnow().date().isoformat()
    daily = user.get("daily_stats", {}).get(today, {"query_count": 0, "token_count": 0})
    return {
        "user_id": user_id,
        "total_query_count": user.get("total_query_count", 0),
        "total_token_count": user.get("total_token_count", 0),
        "today_query_count": daily.get("query_count", 0),
        "today_token_count": daily.get("token_count", 0)
    }

@router.delete("/user/{user_id}")
async def delete_user(user_id: str):
    user_collection = get_user_collection()
    chat_collection = get_chat_collection()
    doc_collection = get_document_collection()
    chunk_collection = get_chunk_collection()

    # Delete user
    user_result = await user_collection.delete_one({"user_id": user_id})
    # Delete all chats
    await chat_collection.delete_many({"user_id": user_id})
    # Find all document ids for this user
    docs = await doc_collection.find({"user_id": user_id}).to_list(length=1000)
    doc_ids = [str(doc["_id"]) for doc in docs]
    # Delete all documents
    await doc_collection.delete_many({"user_id": user_id})
    # Delete all chunks for these documents
    if doc_ids:
        await chunk_collection.delete_many({"document_id": {"$in": doc_ids}})
    return {"message": "User and all related data deleted successfully"}

@router.get("/user/{user_id}")
async def get_user_details(user_id: str):
    user_collection = get_user_collection()
    user = await user_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["_id"] = str(user["_id"])
    return user
