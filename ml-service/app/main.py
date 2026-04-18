import logging
import os

from fastapi import FastAPI

from app.routes import transcribe, speech_analysis

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sales Call Analyzer — ML Service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(transcribe.router)
app.include_router(speech_analysis.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "sales-call-analyzer-ml"}


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("ML Service starting up — Whisper model will load on first request")
