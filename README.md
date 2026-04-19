# Sales Call Analyzer

AI-powered sales call analysis platform. Upload call recordings, get transcriptions, speech quality scores, sales quality scores, and coaching suggestions.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows)
- [Node.js 20+](https://nodejs.org/) (for frontend dev)
- [Python 3.11+](https://www.python.org/) (for backend dev)
- 16 GB RAM minimum (OpenSearch + Ollama are memory-heavy)
- 20 GB free disk space (Ollama model weights)

---

## Quick Start (Infrastructure Only)

```bash
# 1. Clone the repo
git clone <repo-url>
cd sales-call-analyzer

# 2. Create your local .env
cp .env.example .env
# Edit .env and update passwords / secrets

# 3. Start all infrastructure services
docker compose up -d

# 4. Verify all services are healthy
docker compose ps
```

Services started by default:

| Service      | URL                            | Notes                      |
|---|---|---|
| PostgreSQL   | `localhost:5432`               | pgvector extension enabled |
| Redis        | `localhost:6379`               | Celery broker + cache      |
| MinIO API    | `http://localhost:9000`        | S3-compatible storage      |
| MinIO UI     | `http://localhost:9001`        | Admin: see .env for creds  |
| OpenSearch   | `http://localhost:9200`        | Full-text search           |
| LanguageTool | `http://localhost:8010`        | Grammar checking API       |
| Ollama       | `http://localhost:11434`       | Local LLM runtime          |

---

## Pull the LLM Model

After Ollama starts, pull the default model (one-time, ~4 GB):

```bash
docker exec sca-ollama ollama pull llama3.1:8b
```

---

## Run the Backend (Development)

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Seed default users
python scripts/seed_users.py

# Start FastAPI dev server
uvicorn app.main:app --reload --port 3000
```

Backend API: `http://localhost:3000`
Swagger docs: `http://localhost:3000/docs`

---

## Run the Celery Worker (Development)

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

---

## Run the ML Service (Development)

The ML service handles transcription, speaker diarization, speech analysis, and embedding generation.

```bash
cd ml-service
python -m venv .venv
source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Download spaCy English model (one-time)
python -m spacy download en_core_web_sm

# Start the ML service
uvicorn app.main:app --reload --port 8001
```

ML Service health: `http://localhost:8001/health`

**First-run model downloads** (happens automatically on first request):
- `faster-whisper` transcription model (~1.5 GB for `base.en`, ~3 GB for `large-v3`)
- `all-MiniLM-L6-v2` sentence transformer for embeddings (~90 MB)
- Pyannote diarization (requires `HUGGINGFACE_TOKEN` in `.env`)

Set `WHISPER_MODEL_SIZE` in `.env`:
- `base.en` — fast, lower accuracy, CPU-friendly
- `medium.en` — balanced
- `large-v3` — best accuracy, requires 8 GB+ RAM

---

## Run the Frontend (Development)

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

---

## Run Everything with Docker (Phase 1.3+)

Once backend and frontend Dockerfiles are built:

```bash
docker compose --profile app up -d
```

---

## Default Login Credentials

> Change these immediately after first login.

| Role    | Email                    | Password     |
|---|---|---|
| Admin   | admin@company.com        | Admin@1234   |
| Manager | manager@company.com      | Manager@1234 |
| Agent   | agent@company.com        | Agent@1234   |

---

## Service Ports Reference

| Service          | Port  |
|---|---|
| React Frontend   | 5173  |
| FastAPI Backend  | 3000  |
| FastAPI ML Svc   | 8001  |
| Ollama           | 11434 |
| LanguageTool     | 8010  |
| PostgreSQL       | 5432  |
| Redis            | 6379  |
| MinIO API        | 9000  |
| MinIO Console    | 9001  |
| OpenSearch       | 9200  |

---

## Stop All Services

```bash
docker compose down

# To also remove all data volumes (full reset):
docker compose down -v
```

---

## Troubleshooting

### OpenSearch won't start (vm.max_map_count error)
On WSL2 / Linux, run:
```bash
sudo sysctl -w vm.max_map_count=262144
```

### Ollama is slow (no GPU)
Switch to a smaller model in `.env`:
```
OLLAMA_MODEL=mistral:7b
```
Then pull: `docker exec sca-ollama ollama pull mistral:7b`

### Whisper transcription errors
- Check ML service logs: `docker compose logs ml-service`
- Confirm FFmpeg is in the ML container (it is installed via Dockerfile)
- Try a smaller model: set `WHISPER_MODEL_SIZE=base.en` in `.env`

### Pyannote diarization not running
Pyannote requires a HuggingFace token and model access:
1. Accept the model license at [huggingface.co/pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
2. Set `HUGGINGFACE_TOKEN=hf_...` in your `.env`
3. Without a token, the system falls back to a heuristic speaker split (still functional)

### Database migration fails
```bash
cd backend
alembic history    # show migration chain
alembic current    # show applied version
alembic upgrade head   # apply all pending
```

---

## Project Structure

```
sales-call-analyzer/
├── CLAUDE.md          ← AI assistant instructions
├── PLAN.md            ← Phased build plan
├── README.md          ← This file
├── .env.example       ← Environment variable template
├── .gitignore
├── docker-compose.yml
├── backend/           ← FastAPI + Celery
├── frontend/          ← React + Vite
├── ml-service/        ← Transcription, diarization, scoring, embeddings
└── docs/
    ├── scoring-rubric.md        ← Score thresholds and dimension details
    ├── disposition-taxonomy.md  ← 18 disposition categories with examples
    └── deployment-windows.md   ← Windows Server migration guide (Phase 7)
```
