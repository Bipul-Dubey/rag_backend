import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn
from rag import rag_router

# Load environment variables
load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag_router, prefix="/rag", tags=["RAG"])

@app.get("/")
def read_root():
  return {"message": "App is running"}

if __name__ == "__main__":
  port = int(os.getenv("PORT", 8000))
  debug = os.getenv("DEBUG", "True").lower() == "true"
    
  uvicorn.run("main:app", host="0.0.0.0", port=port, reload=debug)