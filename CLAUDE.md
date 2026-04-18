# CLAUDE.md — Sales Call Analyzer

This is the primary reference file for Claude (AI assistant) when working on this project.
Read this file completely before writing any code, suggesting changes, or generating files.

---

## What Is This Project?

An AI-powered sales call analysis platform. Sales managers manually upload outbound call
recordings from 3CX Phone System. The app transcribes them and produces dual-layer quality
scores, summaries, and dispositions — all accessible via a searchable web dashboard.

---

## Current Phase

**Phase:** LOCAL DEVELOPMENT — Localhost only
**Stage:** Initial setup. Building one feature at a time.

> ⚠️ We are building this step by step.
> Do NOT scaffold the entire project at once.
> Wait for explicit instruction before creating each new file or module.
> Always confirm with the user before starting the next step.

---

## Hosting Plan

| Phase | Environment |
|---|---|
| Now (MVP build & testing) | Localhost — Docker Compose |
| Later (after full build) | Windows Server — same Docker Compose |

Do NOT add production configs, SSL certificates, or domain routing until explicitly asked.

---

## Tech Stack — Follow This Exactly

### Frontend
- **React 18** with **Vite** — NOT Next.js
- **TypeScript**
- **Tailwind CSS** + **shadcn/ui** components
- **TanStack Query** — server state management
- **Zustand** — auth and global client state
- **React Router v6** — routing
- **Recharts** — radar charts, trends, leaderboard charts
- **WaveSurfer.js** — audio waveform player with timestamps
- **React Hook Form + Zod** — forms and validation
- **Axios** — HTTP calls to backend API
- **Lucide React** — icons

### Backend (Primary API)
- **FastAPI** (Python 3.11+)
- **SQLAlchemy 2.0** + **Alembic** — ORM and migrations
- **Pydantic v2** — request/response validation
- **python-jose + bcrypt** — JWT authentication
- **Celery + Redis** — async background job queue
- **httpx** — internal HTTP calls to ML service and Ollama
- **MinIO Python SDK** — audio file object storage
- **opensearch-py** — full-text search indexing

### ML Service (Internal Python Microservice — port 8001)
- **FastAPI** — internal REST endpoints only, not exposed to browser
- **faster-whisper** — audio transcription
- **WhisperX or Pyannote.audio** — speaker diarization (Agent vs Customer)
- **librosa + parselmouth (Praat)** — acoustic feature extraction
- **spaCy + NLTK** — NLP and vocabulary metrics
- **LanguageTool** (self-hosted Java, port 8010) — grammar checking
- **sentence-transformers** — text embeddings for semantic search
- **FFmpeg + pydub** — audio format conversion and processing

### LLM Layer
- **Ollama** (port 11434) with **llama3.1:8b** as default model
- Backend calls Ollama directly via HTTP — no extra library needed
- Optional premium path: Claude API or OpenAI API (configured via .env)

### Data Storage
- **PostgreSQL 16 + pgvector extension** — primary relational database
- **Redis** — Celery broker, result backend, and cache
- **MinIO** — S3-compatible self-hosted audio file storage
- **OpenSearch** — full-text and semantic transcript search

### Infrastructure
- **Docker + Docker Compose** — orchestrates all services locally
- **Nginx** — reverse proxy (plain HTTP on localhost)
- Monitoring (Prometheus + Grafana) — Phase 2 only, skip for now

---

## Service Ports (Localhost)

| Service | Port |
|---|---|
| React Frontend | 5173 |
| FastAPI Backend API | 3000 |
| FastAPI ML Service | 8001 |
| Ollama LLM | 11434 |
| LanguageTool | 8010 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| MinIO API | 9000 |
| MinIO Web Console | 9001 |
| OpenSearch | 9200 |

---

## Project Folder Structure (Build Gradually — Do Not Create All at Once)

```
sales-call-analyzer/
├── CLAUDE.md                  ← This file — always read first
├── PLAN.md                    ← Phased build plan and task checklist
├── README.md                  ← Setup and run instructions (create in Phase 1)
├── .env.example               ← All environment variables with descriptions
├── .gitignore
├── docker-compose.yml         ← All services for localhost
│
├── frontend/                  ← React + Vite (scaffold in Phase 1)
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── store/
│   │   ├── api/
│   │   ├── types/
│   │   └── utils/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── tsconfig.json
│
├── backend/                   ← FastAPI + Celery (scaffold in Phase 1)
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   ├── services/
│   │   └── workers/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
│
├── ml-service/                ← ML microservice (scaffold in Phase 2)
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/
│   │   └── utils/
│   ├── requirements.txt
│   └── Dockerfile
│
└── docs/                      ← Reference documents
    ├── scoring-rubric.md
    └── disposition-taxonomy.md
```

---

## Core Features (What We Are Building)

### 1. Manual Call Upload
- Drag-and-drop audio file (`.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`)
- Assign to an agent, set call date
- Stores file in MinIO, triggers background processing pipeline

### 2. Transcription with Speaker Separation
- faster-whisper transcribes audio
- Pyannote/WhisperX diarizes: labels each segment as AGENT or CUSTOMER
- Output: timestamped, speaker-labeled transcript segments

### 3. Call Summary
- LLM (Ollama llama3.1:8b) generates:
  - 3–4 sentence executive summary
  - Key moments (bulleted)
  - Top 3 coaching suggestions for the agent

### 4. Disposition Classification
- LLM classifies the call outcome into one of 18 categories
- See full taxonomy in `docs/disposition-taxonomy.md`

### 5. Speech Quality Score (Layer 1) — 0 to 100
Automated from audio signal and transcript. No LLM needed.

| Dimension | Measurement Tool | Weight |
|---|---|---|
| Pronunciation | Whisper word-level confidence | 15% |
| Intonation | parselmouth — F0 pitch variance | 15% |
| Fluency | librosa — pause frequency + WPM consistency | 15% |
| Grammar | LanguageTool — errors per 100 words | 15% |
| Vocabulary | spaCy — type-token ratio | 10% |
| Pace | transcript timestamps — words per minute | 10% |
| Clarity | Whisper — % low-confidence words | 10% |
| Filler Words | Regex — "um", "uh", "like", "basically" per min | 10% |

### 6. Sales Quality Score (Layer 2) — 0 to 100
LLM-scored. Each dimension returns score (0–10) + justification + quote from transcript.

| Dimension | Weight |
|---|---|
| Greeting & Introduction | 10% |
| Rapport Building | 10% |
| Discovery Questions | 15% |
| Value Explanation | 20% |
| Objection Handling | 20% |
| Script Adherence | 10% |
| Closing & Next Step | 10% |
| Compliance | 5% |

### 7. Searchable Dashboard
- Full-text search across all transcript text (OpenSearch)
- Semantic search via embeddings (pgvector)
- Filters: agent, date range, disposition, score range

---

## Disposition Categories (18 total)

```
CONVERTED              Prospect agreed to buy
INTERESTED_FOLLOWUP    Positive, next step scheduled
INTERESTED_NO_NEXTSTEP Warm but no commitment made
OBJECTION_PRICE        Concerned about cost
OBJECTION_TIMING       Not right now
OBJECTION_AUTHORITY    Need to check with others
OBJECTION_NEED         Does not see the value
OBJECTION_COMPETITOR   Evaluating a competitor
NOT_INTERESTED         Flat rejection
CALLBACK_REQUESTED     Asked to be called back later
VOICEMAIL              Left a voicemail
NO_ANSWER              Nobody picked up
WRONG_NUMBER           Incorrect contact
GATEKEEPER             Did not reach decision maker
DNC                    Do Not Call requested
PARTIAL_CALL           Call dropped or cut short
LANGUAGE_BARRIER       Communication not possible
OTHER                  None of the above
```

---

## Dashboard Pages

| Page | Route | Who Can Access |
|---|---|---|
| Login | `/login` | Everyone |
| Upload | `/upload` | Admin, Manager, Agent |
| Calls List | `/calls` | Admin: all calls. Manager: team. Agent: own only |
| Call Detail | `/calls/:id` | Based on call ownership |
| Agent Scorecard | `/agents/:id` | Admin, Manager (any agent), Agent (own only) |
| Team Dashboard | `/dashboard` | Admin, Manager |
| Search | `/search` | Admin, Manager, Agent (scoped) |
| Settings | `/settings` | Admin, Manager (scripts only) |

---

## User Roles & Permissions

| Role | Access |
|---|---|
| ADMIN | Full access — user management, all teams, all calls |
| MANAGER | All team calls, scores, reports, manage scripts/rubrics |
| AGENT | Own calls only — cannot see other agents |

---

## API Conventions

- Base URL: `http://localhost:3000/api/v1`
- Auth: `Authorization: Bearer <jwt>` header on all protected routes
- Format: JSON for all requests and responses
- File uploads: `multipart/form-data`
- IDs: UUID v4
- Dates: ISO 8601 strings in UTC
- Error format: `{ "error": "Human readable message", "code": "SNAKE_CASE_CODE" }`
- Pagination: `?page=1&limit=20` → `{ "data": [], "total": 0, "page": 1, "pages": 1 }`

---

## Database Rules

- SQLAlchemy 2.0 declarative style
- Every table has: `id` (UUID PK), `created_at`, `updated_at`
- Soft deletes where relevant: `deleted_at` nullable timestamp
- All schema changes via Alembic — never manually ALTER tables
- Every migration file must have both `upgrade()` and `downgrade()`

---

## Code Style

**Python (backend + ml-service):**
- Python 3.11+
- Black formatter, line length 88
- isort for import ordering
- Type hints on every function
- Async/await throughout all FastAPI route handlers
- Pydantic models for every request body and response
- Never use bare `except:` — always catch specific exception types

**TypeScript/React (frontend):**
- Strict TypeScript mode enabled
- Functional components only — no class components
- No `any` types — define proper interfaces in `src/types/`
- Custom hooks for all API calls
- Absolute imports using `@/` alias pointing to `src/`
- ESLint + Prettier enforced

**Git:**
- Branch naming: `feature/`, `fix/`, `chore/`
- Commit style: conventional commits (`feat:`, `fix:`, `docs:`, `chore:`)
- Never commit `.env` files, model weights, or audio recordings

---

## Security Rules (Even on Localhost)

- All credentials in `.env` — never hardcoded anywhere
- JWT access tokens expire in 24 hours; refresh tokens in 7 days
- Accepted upload formats only: `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`
- Max upload size: 500 MB per file
- RBAC enforced on every API route — check role in route handler
- Audit log every sensitive action (upload, delete, config change)

---

## Things to Never Do

- ❌ Do not use Next.js — use React + Vite
- ❌ Do not use Express or Node.js backend — use FastAPI
- ❌ Do not put ML logic inside the main backend — use ml-service
- ❌ Do not skip Alembic — never manually alter the database
- ❌ Do not commit `.env` files
- ❌ Do not build everything at once — one step, one confirmation at a time
- ❌ Do not add Windows Server or production configs until told to

---

## Open Questions (Confirm Before Phase 2)

- [ ] What is the exact filename format 3CX uses for recordings?
- [ ] Which CRM is currently in use?
- [ ] Do agents speak English only, or Tamil-English mix?
- [ ] Is there an existing sales script document to use as rubric?
- [ ] How many agents are on the sales team?
- [ ] What is the expected call volume per day?
- [ ] Does the Windows Server have an NVIDIA GPU? If yes, which model?
- [ ] Any regulatory/compliance requirements for call recordings?

---

*Stack: React 18 + Vite | FastAPI (Python) | PostgreSQL | Redis | MinIO | OpenSearch | Ollama | Docker Compose*
*Current environment: Localhost only — Windows Server migration is a later phase*
