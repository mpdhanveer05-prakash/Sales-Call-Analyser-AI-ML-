import logging

from fastapi import APIRouter
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["embed"])

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("sentence-transformers model loaded")
    return _model


class EmbedRequest(BaseModel):
    text: str


class EmbedResponse(BaseModel):
    embedding: list[float]


@router.post("/embed", response_model=EmbedResponse)
async def embed(body: EmbedRequest) -> EmbedResponse:
    """Encode text into a 384-dimensional embedding vector (all-MiniLM-L6-v2)."""
    model = get_model()
    vec = model.encode(body.text, normalize_embeddings=True).tolist()
    return EmbedResponse(embedding=vec)
