from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import documents,chats, users
from fastapi.staticfiles import StaticFiles
from app.database.mongo import connect_to_mongo, close_mongo_connection
from app.database.document_crud import ensure_indexes

app = FastAPI(title="Document Q&A Platform")

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ MongoDB Connection Hooks
@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()
    await ensure_indexes()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# Include routers
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(chats.router, prefix="/api/chats", tags=["Chats"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])

@app.get("/")
async def root():
    return {"message": "API is running."}

