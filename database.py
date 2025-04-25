import os
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI.replace('<MONGO_DB>','rag_db'))
db = client["rag_db"]  
collection = db["documents"]

    