from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, calls, agents, scripts, search, dashboard, keyword_alerts

app = FastAPI(
    title="Sales Call Analyzer API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(calls.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(scripts.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(keyword_alerts.router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "sales-call-analyzer-api"}
