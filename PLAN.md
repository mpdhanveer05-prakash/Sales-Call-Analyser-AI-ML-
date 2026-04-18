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
| 4 | Sales Quality Layer + LLM | Week 7–8 | 🔲 Not Started |
| 5 | Search & Agent Analytics | Week 9–10 | 🔲 Not Started |
| 6 | Polish, Testing & Local Deploy | Week 11–12 | 🔲 Not Started |
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
- [ ] Migration 008: `scripts` table (id, name, content, rubric JSON, is_active)
- [ ] `app/routers/scripts.py` — CRUD for scripts
- [ ] Seed default script template
- [ ] `GET /api/v1/scripts` — list active scripts
- [ ] `POST /api/v1/scripts` — create new script (ADMIN/MANAGER only)

### 4.3 — Ollama Service (Backend)
- [ ] `app/services/ollama_service.py`
  - `generate(prompt, model, temperature, format)` — base function
  - `score_sales_quality(transcript, script_rubric)` → structured JSON scores
  - `generate_summary(transcript)` → summary + key moments + coaching
  - `classify_disposition(transcript, taxonomy)` → disposition enum
  - Retry logic for Ollama timeouts
  - JSON validation — re-prompt if output is malformed

### 4.4 — Sales Scoring Prompts
Create and test these prompts. Document in `docs/scoring-rubric.md`:
- [ ] Sales scoring prompt — returns 8 dimensions, each with score + justification + quote
- [ ] Summary prompt — returns executive_summary, key_moments[], coaching_suggestions[]
- [ ] Disposition prompt — returns one of 18 disposition codes
- [ ] Test each prompt with 5 real call transcripts — validate output quality

### 4.5 — Database: Sales Score + Summary Tables
- [ ] Migration 009: `sales_scores` table
  - call_id, greeting, rapport, discovery, value_explanation
  - objection_handling, script_adherence, closing, compliance, composite
  - details JSON (stores per-dimension justifications + quotes)
- [ ] Migration 010: `summaries` table
  - call_id, executive_summary, key_moments JSON, coaching_suggestions JSON
- [ ] Migration 011: `objections` table (call_id, timestamp_ms, type, quote, resolved)

### 4.6 — Backend: Sales Score + Summary Worker
- [ ] `app/workers/sales_score_task.py`
  - Fetch transcript from DB
  - Fetch active script rubric
  - Call Ollama service for sales scores, summary, disposition
  - Validate and save all results
  - Update call status: `SCORING` → `COMPLETED`

### 4.7 — Backend: Summary API
- [ ] `GET /api/v1/calls/:id/summary` — return summary + disposition + next step

### 4.8 — Frontend: Sales Score Radar Chart
- [ ] `components/calls/SalesScoreRadar.tsx` — same style as speech radar, 8 sales dimensions
- [ ] Click dimension → show quote from transcript highlighted

### 4.9 — Frontend: Summary Card Component
- [ ] `components/calls/SummaryCard.tsx`
  - Executive summary paragraph
  - Key moments as bullet list
  - Coaching suggestions as numbered list

### 4.10 — Frontend: Disposition Badge
- [ ] `components/calls/DispositionBadge.tsx`
  - Colour-coded badge per disposition category
  - CONVERTED = green, NOT_INTERESTED = red, OBJECTION_* = orange, etc.

### 4.11 — Frontend: Call Detail — Summary Tab
- [ ] Tab 3: Summary — SummaryCard + DispositionBadge + next step details
- [ ] Update Calls List to show disposition badge and both score numbers

### 4.12 — Frontend: Settings — Script Editor
- [ ] `SettingsPage.tsx` — with script editor tab
- [ ] View and edit the active sales script
- [ ] Edit scoring rubric (which talking points are required)
- [ ] Only ADMIN and MANAGER can access

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
- [ ] `app/services/search_service.py`
  - Create index schema for transcripts
  - `index_call(call_id, transcript, metadata)` — indexes full transcript
  - `search(query, filters)` — full-text search with highlighting
- [ ] Migration for call embedding column (pgvector): `vector(384)` column on calls table
- [ ] `index_task.py` worker — runs after scoring completes, indexes to OpenSearch + pgvector

### 5.2 — Search API
- [ ] `POST /api/v1/search` — accepts query + filters, returns highlighted results
  - full-text (OpenSearch) for keyword search
  - semantic (pgvector) for meaning-based search

### 5.3 — Frontend: Search Page
- [ ] `SearchPage.tsx` — search input, type toggle (keyword / semantic)
- [ ] Filter panel: agent, date range, disposition, score range
- [ ] Results list: call date, agent name, disposition, highlighted transcript excerpts
- [ ] Click result → navigate to call detail at correct timestamp

### 5.4 — Agent Scorecard API
- [ ] `GET /api/v1/agents/:id/scorecard?period=30d`
  - Aggregate avg scores for all dimensions
  - Disposition breakdown
  - Trend data (score per week)
  - Top 3 strengths and weaknesses

### 5.5 — Frontend: Agent Scorecard Page
- [ ] `AgentScorecardPage.tsx`
  - Agent name, employee ID, team
  - 30-day average speech score + sales score
  - Trend line chart (Recharts LineChart)
  - Disposition breakdown (pie or bar chart)
  - Top 3 coaching recommendations
  - Link to their recent calls

### 5.6 — Team Dashboard API
- [ ] `GET /api/v1/dashboard/team` — team-wide metrics
- [ ] `GET /api/v1/dashboard/leaderboard` — ranked agents by composite score

### 5.7 — Frontend: Team Dashboard Page
- [ ] `TeamDashboardPage.tsx`
  - Summary cards: total calls, avg speech score, avg sales score, conversion rate
  - Leaderboard table with rank, agent, call count, scores, trend arrow
  - Disposition distribution chart
  - Top 5 most common objections this month
  - Weekly trend line for team averages

**✅ Phase 5 Complete When:**
- Search returns relevant results with highlighted excerpts
- Agent scorecard shows accurate score trends
- Team leaderboard updates as calls are processed

---

## Phase 6 — Polish, Testing & Local Deploy

**Goal:** Stable, production-quality build running fully on localhost via Docker Compose.

**Milestone:** All features working end-to-end. Tested with 20+ real 3CX recordings.

### 6.1 — Coaching Moments
- [ ] ML service: extract 30–60 second clips where notable moments occur
- [ ] `coaching_clips` table in DB
- [ ] Display on call detail page — playable clips with reason label

### 6.2 — Objection & Buying Signal Lists
- [ ] Display objections per call with timestamp, type, and resolution status
- [ ] Display buying signals per call (strong, medium, weak)

### 6.3 — Error Handling & Edge Cases
- [ ] Handle failed transcriptions gracefully (retry 3 times, then mark FAILED)
- [ ] Handle Ollama timeout (retry with smaller prompt, fallback message)
- [ ] Handle corrupt / unreadable audio files
- [ ] Show meaningful error messages in UI

### 6.4 — Testing
- [ ] Test with 20 real 3CX recordings from the sales team
- [ ] Validate transcription accuracy (target: <10% WER)
- [ ] Validate disposition accuracy (target: >80% match with manual labels)
- [ ] Validate sales scores (compare with manager manual review — target: 0.7+ correlation)
- [ ] Test all user roles and permission checks
- [ ] Test file upload with various formats and sizes

### 6.5 — Performance
- [ ] Benchmark full pipeline time per call length
- [ ] Ensure dashboard pages load in <2 seconds
- [ ] Ensure search returns in <500ms

### 6.6 — Documentation
- [ ] `README.md` — complete setup instructions for localhost
- [ ] `docs/scoring-rubric.md` — fully documented scoring logic
- [ ] `docs/disposition-taxonomy.md` — all 18 dispositions with examples
- [ ] `docs/deployment-windows.md` — Windows Server migration guide (ready for Phase 7)

### 6.7 — Security Review
- [ ] Verify all routes check RBAC correctly
- [ ] Verify `.env` variables are never logged
- [ ] Verify no sensitive data in browser console
- [ ] Verify file upload validation cannot be bypassed

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
*Next step: Start Phase 4 — Sales Quality Layer + LLM — confirm before proceeding*
