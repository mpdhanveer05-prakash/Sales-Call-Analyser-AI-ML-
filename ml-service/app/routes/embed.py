import logging
import os

from fastapi import APIRouter
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["embed"])

# BAAI/bge-large-en-v1.5 — 1024-dim, top-tier semantic search quality (MTEB ~64).
# Override via EMBEDDING_MODEL env var if needed.
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading sentence-transformers model (%s)...", EMBEDDING_MODEL_NAME)
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info("sentence-transformers model loaded (dim=%d)", EMBEDDING_DIMENSIONS)
    return _model


class EmbedRequest(BaseModel):
    text: str
    # BGE models distinguish documents from queries. Documents (transcripts) need no prefix;
    # queries need "Represent this sentence for searching relevant passages: " prefix.
    is_query: bool = False


class EmbedResponse(BaseModel):
    embedding: list[float]


@router.post("/embed", response_model=EmbedResponse)
async def embed(body: EmbedRequest) -> EmbedResponse:
    """Encode text into an embedding vector using the configured embedding model."""
    model = get_model()
    text = body.text
    if body.is_query and EMBEDDING_MODEL_NAME.startswith("BAAI/bge"):
        text = f"Represent this sentence for searching relevant passages: {text}"
    vec = model.encode(text, normalize_embeddings=True).tolist()
    return EmbedResponse(embedding=vec)
