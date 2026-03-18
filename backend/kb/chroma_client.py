import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from backend.config import settings

# The embedding model is a lazy singleton — it's stateless and expensive to load,
# so sharing one instance per process is safe and intentional.
_model = None

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def get_chroma_client(path: str | None = None) -> chromadb.Client:
    return chromadb.PersistentClient(
        path=path or settings.chroma_db_path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

KB_COLLECTION = "wealth_planning_kb"

def get_kb_collection(client: chromadb.Client):
    return client.get_or_create_collection(
        name=KB_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

def get_case_collection(client: chromadb.Client, case_id: str):
    return client.get_or_create_collection(
        name=f"case_{case_id}",
        metadata={"hnsw:space": "cosine"},
    )
