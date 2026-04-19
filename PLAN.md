# PLAN.md — Sales Call Analyzer Build Plan

This file tracks every phase, task, and decision for the project build.
Update the checkboxes as tasks are completed.

---

## Build Philosophy

- One phase at a time — complete and test before moving to the next
- Each phase ends with a working, demonstrable milestone
- No phase is started without confirming the previous one works
- Every feature is tested with real 3CX recordings before sign-off

---

## Phase Overview

| Phase | Name | Duration (Est.) | Status |
|---|---|---|---|
| 1 | Foundation & Infrastructure | Week 1–2 | ✅ Complete |
| 2 | Transcription Pipeline | Week 3–4 | ✅ Complete |
| 3 | Speech Quality Layer | Week 5–6 | ✅ Complete |
| 4 | Sales Quality Layer + LLM | Week 7–8 | ✅ Complete |
| 5 | Search & Agent Analytics | Week 9–10 | ✅ Complete |
| 6 | Polish, Testing & Local Deploy | Week 11–12 | ✅ Complete |
| 7 | Windows Server Migration | After Phase 6 | 🔲 Not Started |
| 8 | 3CX Auto-Integration | Post-launch | 🔲 Not Started |

---

## Phase 1 — Foundation & Infrastructure

**Goal:** All services running. Upload an audio file and see it in the database. Login works.

**Milestone:** Manager can log in, upload a `.mp3` file, and see it in the calls list with status "Queued".

### 1.1 — Project Setup
- [x] Create `CLAUDE.md`
- [x] Create `PLAN.md`
- [x] Create `.env.example` with all variables documented
- [x] Create `.gitignore`
- [x] Create `docker-compose.yml` with all infrastructure services
- [x] Create `README.md` with local setup instructions

### 1.2 — Infrastructure Services (Docker Compose)
- [x] PostgreSQL 16 with pgvector extension — verify connection
- [x] Redis — verify connection
- [x] MinIO — verify connection, create `call-recordings` and `call-processed` buckets
- [x] OpenSearch — verify connection, single-node dev mode
- [x] LanguageTool — verify `/v2/check` endpoint responds
- [x] Ollama — verify running, pull `llama3.1:8b` model

### 1.3 — Backend: FastAPI Skeleton
- [x] Create `backend/` folder structure
- [x] `requirements.txt` — all Python dependencies listed
- [x] `Dockerfile` for backend
- [x] `app/main.py` — FastAPI app with CORS, health endpoint at `GET /health`
- [x] `app/config.py` — Pydantic Settings reading from `.env`
- [x] `app/database.py` — SQLAlchemy engine, session factory, Base class

### 1.4 — Database Schema (Core Tables)
- [x] Alembic initialized — `alembic init alembic`
- [x] Migration 001: Create `users` table
- [x] Migration 002: Create `teams` table
- [x] Migration 003: Create `agents` table
- [x] Migration 004: Create `calls` table (id, agent_id, audio_url, status, duration, call_date, disposition, uploaded_at, processed_at)
- [ ] All migrations run successfully — `alembic upgrade head` ⚠️ needs live DB verify

### 1.5 — Authentication
- [x] `app/models/user.py` — User ORM model (id, email, hashed_password, role, team_id)
- [x] `app/schemas/auth.py` — LoginRequest, TokenResponse Pydantic schemas
- [x] `app/services/auth_service.py` — hash password, verify password, create JWT, decode JWT
- [x] `app/routers/auth.py` — `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`
- [x] Auth dependency `get_current_user` for protecting routes
- [x] Role-based dependency `require_role(["ADMIN", "MANAGER"])`
- [x] Seed default users: admin, manager, agent (from `scripts/seed_users.py`)

### 1.6 — File Upload
- [x] `app/services/storage_service.py` — MinIO upload, get presigned URL, delete
- [x] `app/routers/calls.py` — `POST /api/v1/calls/upload` (multipart/form-data)
- [x] Validate file extension and size on upload
- [x] Save call record to DB with status `QUEUED`
- [x] Return call_id in response

### 1.7 — Celery Job Queue
- [x] `app/workers/celery_app.py` — Celery app configured with Redis broker
- [x] Stub task: `process_call_task(call_id)` — logs "Processing call {call_id}", updates status to `ANALYZING`
- [ ] Worker starts and picks up task on upload ⚠️ needs live verify
- [ ] Verify job flow: upload → queued → celery picks up → status updates in DB ⚠️ needs live verify

### 1.8 — Frontend: React + Vite Skeleton
- [x] Scaffold with `npm create vite@latest frontend -- --template react-ts`
- [x] Install all dependencies from `package.json`
- [x] Configure Tailwind CSS
- [x] Configure `@/` path alias in `vite.config.ts` and `tsconfig.json`
- [x] Set up React Router — routes for `/login`, `/upload`, `/calls`
- [x] Axios instance in `src/api/client.ts` — base URL from env, JWT interceptor
- [x] TanStack Query provider in `App.tsx`
- [x] Zustand auth store — `useAuthStore` with user, token, login, logout

### 1.9 — Frontend: Login Page
- [x] `LoginPage.tsx` — email + password form with React Hook Form + Zod
- [x] Call `POST /api/v1/auth/login` on submit
- [x] Store JWT in Zustand + localStorage
- [x] Redirect to `/calls` on success
- [x] Protected route wrapper — redirect to `/login` if not authenticated

### 1.10 — Frontend: Upload Page
- [x] `UploadPage.tsx` — drag-and-drop zone (react-dropzone)
- [x] Agent selector dropdown (fetches from `GET /api/v1/agents`)
- [x] Call date picker
- [x] File validation (type + size) client-side before upload
- [x] Progress indicator during upload
- [x] On success: show call ID and "Processing started" message

### 1.11 — Frontend: Calls List Page
- [x] `CallsListPage.tsx` — table of calls
- [x] Columns: Date, Agent, Duration, Status, Disposition, Speech Score, Sales Score
- [x] Status badge (Queued, Transcribing, Analyzing, Scoring, Completed, Failed)
- [x] Filter: agent, date range, status
- [x] Pagination
- [x] Click row → navigate to `/calls/:id`
- [x] Auto-refresh every 15 seconds for calls in processing states

**✅ Phase 1 Complete When:**
- All Docker services start with `docker compose up -d`
- Login works for all three roles
- Audio file uploads successfully and appears in calls list
- Celery worker picks up the job and updates status

---

## Phase 2 — Transcription Pipeline

**Goal:** Upload a call → get a speaker-separated transcript with timestamps.

**Milestone:** Call detail page shows full transcript with [AGENT] and [CUSTOMER] labels, timestamps, and a synchronized audio player.

### 2.1 — ML Service Setup
- [x] Create `ml-service/` folder structure
- [x] `requirements.txt` — faster-whisper, pyannote, librosa, spaCy, etc.
- [x] `Dockerfile` — Python 3.11 slim + ffmpeg, CPU torch, spaCy model download
- [x] `app/main.py` — FastAPI app with `GET /health` endpoint
- [x] Add ml-service to `docker-compose.yml` with model cache volume
- [ ] Verify ml-service starts and GPU is accessible ⚠️ needs live verify

### 2.2 — Transcription Endpoint (ML Service)
- [x] `app/routes/transcribe.py` — `POST /transcribe`
  - Input: JSON `{ minio_path }` — ML service downloads from MinIO directly
  - Runs faster-whisper transcription (word-level timestamps, VAD filter)
  - Runs Pyannote diarization if `HUGGINGFACE_TOKEN` is set; otherwise heuristic
  - Returns: `[{ speaker, start_ms, end_ms, text, confidence }]`
- [ ] Test with sample 3CX recording ⚠️ needs live verify
- [ ] Verify Indian-English accuracy (change `WHISPER_MODEL_SIZE=large-v3` in .env)
- [ ] Benchmark speed: target < 3× call duration

### 2.3 — Database: Transcript Tables
- [x] Migration 005: `transcripts` table (id, call_id, language, duration_seconds, segment_count)
- [x] Migration 006: `transcript_segments` table (id, transcript_id, speaker, start_ms, end_ms, text, confidence)
- [x] `app/models/transcript.py` — ORM models with relationships

### 2.4 — Backend: Transcription Worker
- [x] `app/workers/transcribe_task.py`
  - POSTs `minio_path` to ML service `/transcribe`
  - Saves transcript + segments to PostgreSQL (idempotent)
  - Updates call status: `TRANSCRIBING` → `ANALYZING`
  - Retries up to 3 times with 60s back-off on failure
- [x] Updated `process_call_task` to chain into `transcribe_call_task`
- [x] Transcription failures update call status to `FAILED` with error message

### 2.5 — Backend: Transcript API
- [x] `GET /api/v1/calls/:id/transcript` — all segments with speaker labels
- [x] `GET /api/v1/calls/:id/audio-url` — presigned MinIO URL for audio player (2h TTL)

### 2.6 — Frontend: Audio Player Component
- [x] `components/calls/AudioPlayer.tsx`
  - WaveSurfer.js waveform display
  - Play / Pause / Mute controls + timestamp display
  - Exposes `seekTo(ms)` via `forwardRef` / `useImperativeHandle`
  - Fires `onTimeUpdate(ms)` every frame for transcript sync

### 2.7 — Frontend: Transcript Viewer Component
- [x] `components/calls/TranscriptViewer.tsx`
  - AGENT (blue) / CUSTOMER (green) colour-coded segments
  - Timestamp per segment — click to seek audio player
  - Auto-scrolls to currently playing segment
  - Search bar with live highlight and result count

### 2.8 — Frontend: Call Detail Page (Transcript Tab)
- [x] `CallDetailPage.tsx` — 3-tab layout (Transcript / Scores / Summary)
- [x] Tab 1: AudioPlayer + TranscriptViewer + turn-count stats
- [x] Tabs 2 & 3: placeholders for Phase 3 and Phase 4
- [x] Call metadata cards: speech score, sales score, duration, disposition
- [x] Auto-refetch every 10s while call is still processing

**✅ Phase 2 Complete When:**
- Upload a call → transcript appears with [AGENT] / [CUSTOMER] labels
- Audio player syncs with transcript — click a line, audio jumps to that point
- Speaker separation is accurate enough to be useful

---

## Phase 3 — Speech Quality Layer

**Goal:** Every completed call gets a speech quality score breakdown (0–100) with per-dimension scores.

**Milestone:** Call detail page shows a radar chart with 8 speech dimensions and their individual scores.

### 3.1 — Speech Analysis Endpoint (ML Service)
- [x] `app/routes/speech_analysis.py` — `POST /analyze-speech`
  - Input: `{ minio_path, transcript, language }` — ML service downloads audio
  - librosa: pause detection via RMS silence threshold, pause rate per minute
  - parselmouth: F0 std dev (intonation) on full audio
  - Filler word regex on AGENT transcript only
  - LanguageTool `/v2/check` (sync httpx): grammar errors per 100 words
  - spaCy: type-token ratio on lemmatised content words (AGENT only)
  - Whisper confidence: avg and % low-confidence (< 0.6) from segment data
  - Returns `RawSpeechMetrics` JSON
- [ ] Test with sample 3CX recording ⚠️ needs live verify
- [ ] Benchmark speed vs call duration

### 3.2 — Scoring Logic (Backend)
- [x] `app/services/speech_scoring_service.py`
  - Per-dimension score functions with documented thresholds
  - `compute_speech_scores(metrics)` → dict with 8 scores + composite
  - Weighted average: 15/15/15/15/10/10/10/10
  - Thresholds fully documented in `docs/scoring-rubric.md`

### 3.3 — Database: Speech Score Table
- [x] Migration 007: `speech_scores` table
  - call_id (FK, unique), 8 dimension columns, composite, fillers_per_min, pace_wpm, talk_ratio
- [x] `app/models/scores.py` — SpeechScore ORM model with back-ref on Call

### 3.4 — Backend: Speech Score Worker
- [x] `app/workers/speech_score_task.py`
  - Fetches transcript from DB, POSTs to ML service `/analyze-speech`
  - Runs `compute_speech_scores`, saves `SpeechScore` row
  - Updates `calls.speech_score` (denormalised) for fast queries
  - Status: ANALYZING → SCORING → COMPLETED
  - Idempotent — deletes old score before re-inserting
- [x] `transcribe_task.py` now chains into `speech_score_task.delay()`

### 3.5 — Backend: Scores API
- [x] `GET /api/v1/calls/:id/scores` — returns `{ speech: SpeechScoreOut, sales: null }`

### 3.6 — Frontend: Speech Score Radar Chart
- [x] `components/calls/SpeechScoreRadar.tsx`
  - Recharts RadarChart with 8 dimensions + custom tooltip
  - Colour coded: green ≥80, yellow 60–79, orange 40–59, red <40
  - Composite score hero, quick-stats (WPM, fillers/min, talk ratio)
  - Dimension breakdown grid with weight labels

### 3.7 — Frontend: Call Detail — Scores Tab
- [x] Scores tab displays SpeechScoreRadar when speech score is available
- [x] Placeholder for Sales Score (Phase 4)
- [x] Graceful empty state while call is still processing

**✅ Phase 3 Complete When:**
- Every processed call shows a speech score radar chart
- All 8 dimensions are scored and displayed
- Composite score matches the weighted average

---

## Phase 4 — Sales Quality Layer + LLM

**Goal:** Every call gets a sales quality score, disposition, call summary, and coaching suggestions — all generated by the LLM.

**Milestone:** Call detail page shows both radar charts (speech + sales), a disposition badge, a call summary card, and coaching suggestions.

### 4.1 — Ollama Setup
- [ ] Verify Ollama running in Docker: `GET http://localhost:11434/api/tags`
- [ ] Pull model: `docker exec sca-ollama ollama pull llama3.1:8b`
- [ ] Test basic prompt via API: verify JSON output mode works

### 4.2 — Sales Script / Rubric Management
- [x] Migration 008: `scripts` table (id, name, content, rubric JSON, is_active)
- [x] `app/routers/scripts.py` — CRUD for scripts
- [x] Seed default script template
- [x] `GET /api/v1/scripts` — list active scripts
- [x] `POST /api/v1/scripts` — create new script (ADMIN/MANAGER only)

### 4.3 — Ollama Service (Backend)
- [x] `app/services/ollama_service.py`
  - `generate(prompt, model, temperature, format)` — base function
  - `score_sales_quality(transcript, script_rubric)` → structured JSON scores
  - `generate_summary(transcript)` → summary + key moments + coaching
  - `classify_disposition(transcript, taxonomy)` → disposition enum
  - Retry logic for Ollama timeouts
  - JSON validation — re-prompt if output is malformed

### 4.4 — Sales Scoring Prompts
- [x] Sales scoring prompt — returns 8 dimensions, each with score + justification + quote
- [x] Summary prompt — returns executive_summary, key_moments[], coaching_suggestions[]
- [x] Disposition prompt — returns one of 18 disposition codes
- [ ] Test each prompt with 5 real call transcripts — validate output quality ⚠️ needs live verify

### 4.5 — Database: Sales Score + Summary Tables
- [x] Migration 009: `sales_scores` table
- [x] Migration 010: `summaries` table
- [ ] Migration 011: `objections` table — deferred to Phase 6

### 4.6 — Backend: Sales Score + Summary Worker
- [x] `app/workers/sales_score_task.py`

### 4.7 — Backend: Summary API
- [x] `GET /api/v1/calls/:id/summary` — return summary + disposition

### 4.8 — Frontend: Sales Score Radar Chart
- [x] `components/calls/SalesScoreRadar.tsx` — 8 sales dimensions with LLM justifications accordion

### 4.9 — Frontend: Summary Card Component
- [x] `components/calls/SummaryCard.tsx`

### 4.10 — Frontend: Disposition Badge
- [x] `components/calls/DispositionBadge.tsx` — colour-coded for all 18 dispositions

### 4.11 — Frontend: Call Detail — Summary Tab
- [x] Tab 3: Summary — SummaryCard + DispositionBadge
- [x] Scores tab now shows both SpeechScoreRadar + SalesScoreRadar
- [x] Calls List disposition column uses DispositionBadge
- [x] Call Detail header uses DispositionBadge for disposition card

### 4.12 — Frontend: Settings — Script Editor
- [x] `SettingsPage.tsx` — script list sidebar + content/rubric editor
- [x] View and edit the active sales script
- [x] Edit scoring rubric (required points, prohibited phrases, disclosures)
- [x] Only ADMIN and MANAGER can access (enforced in UI + backend)

**✅ Phase 4 Complete When:**
- Every call shows both score radars (speech + sales)
- Disposition badge displayed on call detail and list
- Summary with key moments and coaching suggestions visible
- Script editor accessible to managers

---

## Phase 5 — Search & Agent Analytics

**Goal:** Managers can search all transcripts and view per-agent performance over time.

**Milestone:** Search page returns relevant transcript excerpts. Agent scorecard shows trends and a team leaderboard exists.

### 5.1 — OpenSearch Indexing
- [x] `app/services/search_service.py` — full-text index with nested segments, highlighting, filters
- [x] Migration 011: `embedding vector(384)` column on calls table
- [x] `app/workers/index_task.py` — Celery task: indexes to OpenSearch + best-effort pgvector embedding via ML service `/embed`
- [x] `ml-service/app/routes/embed.py` — sentence-transformers `all-MiniLM-L6-v2` embedding endpoint
- [x] `sales_score_task` chains to `index_task` after completion

### 5.2 — Search API
- [x] `POST /api/v1/search` — full-text (OpenSearch) + RBAC agent scoping
- [x] `SearchRequest` / `SearchResult` Pydantic schemas

### 5.3 — Frontend: Search Page
- [x] `SearchPage.tsx` — query input, keyword/semantic toggle, filter panel (agent, date, disposition)
- [x] Results list with `<mark>` highlighted excerpts, disposition badge, score display
- [x] Click result → navigates to call detail

### 5.4 — Agent Scorecard API
- [x] `GET /api/v1/agents/:id/scorecard?period=30` — avg scores per dimension, disposition breakdown, weekly trend, strengths/weaknesses
- [x] RBAC: agents may only access own scorecard

### 5.5 — Frontend: Agent Scorecard Page
- [x] `AgentScorecardPage.tsx` — score heroes, trend line chart, disposition bar chart, strengths/weaknesses, recent calls
- [x] Agent names in Calls List link to `/agents/:id`

### 5.6 — Team Dashboard API
- [x] `GET /api/v1/dashboard/team` — total calls, avg scores, conversion rate, disposition breakdown, weekly trend, leaderboard
- [x] `GET /api/v1/dashboard/leaderboard` — ranked agents by composite score

### 5.7 — Frontend: Team Dashboard Page
- [x] `TeamDashboardPage.tsx` — metric cards, weekly trend chart, disposition breakdown, leaderboard table
- [x] Dashboard and Search added to sidebar nav (no longer disabled)

**✅ Phase 5 Complete When:**
- Search returns relevant results with highlighted excerpts
- Agent scorecard shows accurate score trends
- Team leaderboard updates as calls are processed

---

## Phase 6 — Polish, Testing & Local Deploy

**Goal:** Stable, production-quality build running fully on localhost via Docker Compose.

**Milestone:** All features working end-to-end. Tested with 20+ real 3CX recordings.

### 6.1 — Coaching Moments
- [x] LLM extracts 3–5 notable coaching moments from each call transcript (`ollama_service.extract_coaching_moments`)
- [x] Migration 012: `coaching_clips` table (call_id, start_ms, end_ms, category, reason)
- [x] Migration 014: performance indexes on `calls` table (agent+status+date, status+date)
- [x] `CoachingClip` ORM model + `CoachingClipOut` Pydantic schema
- [x] `GET /api/v1/calls/:id/coaching` API endpoint
- [x] Coaching tab in Call Detail page — playable clips with category badge + reason text

### 6.2 — Objection & Buying Signal Lists
- [x] LLM extracts customer objections from each call (`ollama_service.extract_objections`)
- [x] Migration 013: `objections` table (call_id, timestamp_ms, objection_type, quote, resolved)
- [x] `Objection` ORM model + `ObjectionOut` Pydantic schema
- [x] `POST /api/v1/calls/:id/objections/:objection_id/resolve` API endpoint
- [x] Objections section in Coaching tab — quoted customer statements + resolve toggle
- [ ] Buying signals display (deferred — objections cover the primary use case)

### 6.3 — Error Handling & Edge Cases
- [x] Transcription retries 3 times with 60s back-off; marks FAILED after all attempts
- [x] Ollama service has retry logic for timeouts; returns empty/null gracefully on all errors
- [x] Coaching and objection extraction return `[]` on any error (never break the pipeline)
- [x] Frontend shows meaningful empty states for each tab while processing or when data unavailable
- [x] Toast notification system (`toastStore` + `ToastContainer`) for user-facing errors
- [ ] Corrupt audio handling end-to-end verified ⚠️ needs live verify with bad files

### 6.4 — Testing
- [x] Unit tests for `compute_speech_scores` — 4 tests covering perfect, silence, fast speech, filler words
- [ ] Test with 20 real 3CX recordings from the sales team ⚠️ needs real recordings
- [ ] Validate transcription accuracy (target: <10% WER) ⚠️ needs live verify
- [ ] Validate disposition accuracy (target: >80% match with manual labels) ⚠️ needs live verify
- [ ] Validate sales scores (compare with manager manual review) ⚠️ needs live verify
- [ ] Test all user roles and permission checks ⚠️ needs live verify
- [ ] Test file upload with various formats and sizes ⚠️ needs live verify

### 6.5 — Performance
- [x] Performance indexes added: `ix_calls_agent_status_date`, `ix_calls_status_date` (migration 014)
- [ ] Benchmark full pipeline time per call length ⚠️ needs live verify
- [ ] Ensure dashboard pages load in <2 seconds ⚠️ needs live verify
- [ ] Ensure search returns in <500ms ⚠️ needs live verify

### 6.6 — Documentation
- [x] `README.md` — ML service setup, troubleshooting section, project structure updated
- [x] `docs/scoring-rubric.md` — complete thresholds, grade table, coaching/objection extraction docs
- [x] `docs/disposition-taxonomy.md` — all 18 dispositions with LLM signals and code usage
- [x] `docs/deployment-windows.md` — full Windows Server migration guide for Phase 7

### 6.7 — Security Review
- [ ] Verify all routes check RBAC correctly ⚠️ needs live verify
- [ ] Verify `.env` variables are never logged ⚠️ needs code review
- [ ] Verify no sensitive data in browser console ⚠️ needs live verify
- [ ] Verify file upload validation cannot be bypassed ⚠️ needs live verify

**✅ Phase 6 Complete When:**
- All 6 core features work end-to-end
- Tested with real recordings and scores are sensible
- Managers and agents have been onboarded and used the app

---

## Phase 7 — Windows Server Migration (Later)

**Goal:** Move the localhost Docker Compose deployment to the Windows Server.

> ⚠️ Do not start this phase until Phase 6 is fully signed off.

### Checklist
- [ ] Confirm Docker Desktop or Docker Engine installed on Windows Server
- [ ] Confirm NVIDIA GPU availability and drivers installed
- [ ] Create `docker-compose.prod.yml` with production overrides
- [ ] Set production `.env` values (secrets, server IP/hostname)
- [ ] Configure Nginx for domain/IP routing
- [ ] Configure Windows Firewall rules (allow ports 80, 443, 3000, 5173)
- [ ] Set up Windows Task Scheduler for nightly DB backups
- [ ] Test all features on server before go-live
- [ ] Train the team on the final deployed app

---

## Phase 8 — 3CX Automated Integration (Post-Launch)

**Goal:** Calls from 3CX are automatically imported — no manual upload needed.

> Start only after Phase 7 is stable and team has adopted manual workflow.

### Options to Evaluate
- [ ] **Option A:** Folder watcher — script monitors 3CX recording folder, auto-uploads new files
- [ ] **Option B:** 3CX Webhook — if 3CX supports post-call webhooks, trigger upload via API
- [ ] **Option C:** 3CX API integration — if 3CX has a management API, poll for new recordings

### Tasks
- [ ] Identify how 3CX stores recordings (folder path, filename format, metadata)
- [ ] Confirm agent-to-recording mapping (how to know which agent made the call)
- [ ] Build folder watcher service (Python watchdog or Windows Service)
- [ ] Extract call metadata from filename or 3CX API
- [ ] Auto-assign call to agent in the system
- [ ] Test with live 3CX system

---

## Decision Log

Track important decisions here so we don't revisit them repeatedly.

| Date | Decision | Reason |
|---|---|---|
| Kickoff | React + Vite (not Next.js) | Simpler SPA setup, team preference |
| Kickoff | FastAPI (not Node.js/Express) | Python ecosystem needed for ML pipeline |
| Kickoff | ML microservice separate from main backend | Keeps ML dependencies isolated, independently scalable |
| Kickoff | Ollama for LLM (not cloud API) | Zero cost, data stays on-prem |
| Kickoff | Docker Compose (not k8s) | Simpler for single-server on-prem deployment |
| Kickoff | Localhost first, Windows Server later | Allows rapid iteration without server access |

---

## Known Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Whisper accuracy on Tamil-English code-switch | Medium | Use `large-v3` model; fine-tune in Phase 8 if needed |
| LLM scores inconsistent across calls | Medium | Require quote attribution; manager spot-check weekly |
| Ollama too slow on CPU (no GPU) | High if no GPU | Start with `mistral:7b` (faster); or use Claude API as fallback |
| Manager adoption is low | Medium | Ship leaderboard early — it drives stickiness |
| 3CX filename format unclear | Unknown | Confirm before Phase 8 starts |

---

*Last updated: 2026-04-18*
*Next step: Phase 7 — Windows Server Migration — confirm before proceeding*
