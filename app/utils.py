import os
from typing import List
from sentence_transformers import SentenceTransformer

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def embed_chunks(chunks: list[str]) -> list[list[float]]:
    return embedding_model.encode(chunks).tolist()
