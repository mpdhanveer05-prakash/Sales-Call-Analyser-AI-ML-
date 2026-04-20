# Sales Call Analyzer — User Guide

## Table of Contents
1. [Accessing the Application](#1-accessing-the-application)
2. [User Roles](#2-user-roles)
3. [Logging In](#3-logging-in)
4. [Uploading a Call Recording](#4-uploading-a-call-recording)
5. [Calls List Page](#5-calls-list-page)
6. [Call Detail Page](#6-call-detail-page)
7. [Understanding the Scores](#7-understanding-the-scores)
8. [Team Dashboard](#8-team-dashboard)
9. [Agent Scorecard](#9-agent-scorecard)
10. [Search](#10-search)
11. [Settings — Script Editor](#11-settings--script-editor)
12. [Default Login Credentials](#12-default-login-credentials)

---

## 1. Accessing the Application

Open your browser and go to:

```
http://localhost:5173
```

The application runs entirely on your local machine. No internet connection is required after initial setup.

---

## 2. User Roles

There are three roles in the system. Each role controls what you can see and do.

| Role | What they can access |
|---|---|
| **Admin** | Everything — all calls, all agents, all teams, user management, settings |
| **Manager** | All calls within their team, team dashboard, leaderboard, script settings |
| **Agent** | Their own calls only, their own scorecard |

---

## 3. Logging In

1. Open `http://localhost:5173` — you will be taken to the login page automatically.
2. Enter your **email address** and **password**.
3. Click **Sign in**.
4. You will be redirected to the Calls List page after successful login.

To log out, click your name or the logout button in the navigation bar.

---

## 4. Uploading a Call Recording

> **Who can upload:** Admin, Manager, and Agent roles.

### Steps

1. Click **Upload** in the left navigation sidebar.
2. **Drag and drop** your audio file onto the upload area, or click the area to browse for a file.
3. **Supported formats:** `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`
4. **Maximum file size:** 500 MB
5. Select the **Agent** this call belongs to from the dropdown.
6. Set the **Call Date** (the date the call actually took place).
7. Click **Upload**.

### What happens after upload

The system processes the call automatically in the background through these stages:

| Stage | What is happening |
|---|---|
| **Queued** | File uploaded, waiting to be processed |
| **Transcribing** | AI is converting speech to text with speaker labels |
| **Analyzing** | Extracting acoustic features (pace, pitch, pauses) |
| **Scoring** | Calculating Speech Score and Sales Score |
| **Completed** | All analysis done — results are ready |
| **Failed** | Something went wrong — check the call detail for the error |

Processing typically takes 2–5 minutes depending on call length. The status updates automatically on the Calls List page.

---

## 5. Calls List Page

> **Route:** `/calls`

This is the main page you land on after login. It shows all calls you have access to.

### What you can see

- **Agent name** and call date
- **Duration** of the call
- **Status badge** (Queued / Transcribing / Analyzing / Scoring / Completed / Failed)
- **Disposition** — the outcome of the call (e.g., Converted, Interested Follow-up, Voicemail)
- **Speech Score** — automated quality score out of 100
- **Sales Score** — LLM-evaluated sales technique score out of 100

### Filtering calls

Use the filter bar at the top to narrow down results:

- **Agent** — filter by a specific agent
- **Status** — show only calls in a particular stage
- **Date From / Date To** — filter by call date range

### Navigating

- Click any row to open the **Call Detail page** for that call.
- Use the **pagination controls** at the bottom to move between pages (20 calls per page).
- Click the **refresh icon** to reload the latest data.

---

## 6. Call Detail Page

> **Route:** `/calls/:id`

Click on any call from the Calls List to open this page. It has five tabs.

### Tab 1 — Overview

Shows key information at a glance:

- **Call metadata** — agent name, call date, file name, duration
- **Disposition badge** — the classified outcome of the call
- **Speech Score** and **Sales Score** summary cards
- **Waveform player** — listen to the call recording with a visual waveform. Click anywhere on the waveform to jump to that moment.

### Tab 2 — Transcript

Shows the full conversation with:

- **Speaker labels** — each line is labelled AGENT or CUSTOMER
- **Timestamps** — click any segment to jump to that moment in the audio player
- **Active highlight** — the current segment playing is highlighted automatically as the audio plays

If the call has not finished transcribing yet, this tab shows a loading state.

### Tab 3 — Scores

Two radar charts side by side:

**Speech Quality Score (0–100)** — Automated, no LLM needed:

| Dimension | What it measures |
|---|---|
| Pronunciation | Whisper word-confidence |
| Intonation | Pitch variance (F0) |
| Fluency | Pause frequency and WPM consistency |
| Grammar | Grammar errors per 100 words |
| Vocabulary | Type-token ratio (word variety) |
| Pace | Words per minute |
| Clarity | Percentage of low-confidence words |
| Filler Words | "um", "uh", "like", "basically" per minute |

**Sales Quality Score (0–100)** — LLM evaluated, each dimension returns a score + quote from the transcript:

| Dimension | What it measures |
|---|---|
| Greeting | Professional opening and introduction |
| Rapport | Building connection with the prospect |
| Discovery | Quality of qualifying questions |
| Value | How well the product/service benefit was explained |
| Objection Handling | Response to customer concerns |
| Script Adherence | Following the approved sales script |
| Closing | Whether a clear next step was established |
| Compliance | Regulatory and compliance adherence |

Each Sales dimension also shows a **direct quote** from the transcript that justified the score.

### Tab 4 — Summary

Three sections generated by the AI:

- **Executive Summary** — 3–4 sentence overview of what happened on the call
- **Key Moments** — bulleted list of the most important moments in the call
- **Coaching Suggestions** — top 3 specific, actionable suggestions for the agent to improve

### Tab 5 — Coaching

Highlights specific moments requiring attention:

- **Coaching Clips** — timestamped segments where improvement is recommended. Click the timestamp to jump to that exact moment in the audio player.
- **Objections Raised** — list of objections the customer raised, with the agent's response and a suggestion on how to handle it better next time.

---

## 7. Understanding the Scores

### Score Grades

| Score | Grade | Meaning |
|---|---|---|
| 90–100 | Excellent | Top performance |
| 75–89 | Good | Above average |
| 60–74 | Average | Room for improvement |
| 40–59 | Below Average | Needs coaching |
| 0–39 | Poor | Significant issues |

### Overall Score

The final score shown on the Calls List is a weighted average of all individual dimensions. A low score on a high-weight dimension (e.g., Value Explanation at 20%, Objection Handling at 20%) will pull the overall score down significantly.

---

## 8. Team Dashboard

> **Route:** `/dashboard`
> **Who can access:** Admin and Manager only

An overview of the whole team's performance.

### What you can see

- **Total calls** processed in the selected period
- **Average Speech Score** and **Average Sales Score** across the team
- **Score trend chart** — how scores have changed over time (line chart)
- **Leaderboard** — agents ranked by their average sales score

### Using the date filter

Use the **date range selector** at the top right to change the reporting period (e.g., last 7 days, last 30 days, custom range).

---

## 9. Agent Scorecard

> **Route:** `/agents/:id`
> **Who can access:** Admin and Manager (any agent). Agents can only view their own scorecard.

A detailed performance profile for a single agent.

### What you can see

- **Average scores** over time
- **Total calls** reviewed
- **Score breakdown** by dimension — identify specific strengths and weaknesses
- **Recent calls** list for that agent

To access an agent's scorecard, click the agent's name on the Team Dashboard leaderboard, or navigate from the Calls List.

---

## 10. Search

> **Route:** `/search`

Search across all transcripts to find specific calls.

### How to search

1. Click **Search** in the left navigation.
2. Type any word or phrase into the search box.
3. Results show matching calls with the matched text highlighted.

### Search types

- **Full-text search** — finds exact words and phrases anywhere in the transcript
- **Semantic search** — finds calls with similar meaning even if different words were used (powered by sentence embeddings)

### Filters

You can combine the search query with:

- **Agent** filter
- **Date range** filter
- **Score range** filter
- **Disposition** filter

---

## 11. Settings — Script Editor

> **Route:** `/settings`
> **Who can access:** Admin and Manager only

Manage the sales scripts that agents are expected to follow.

### What you can do

- **View** all active scripts
- **Create** a new script — give it a name, paste the script content, and optionally define a scoring rubric (JSON format) for customising how LLM evaluates script adherence
- **Edit** an existing script
- **Deactivate** a script (soft delete — data is preserved)

The active script is used by the AI when scoring the **Script Adherence** dimension in the Sales Quality Score.

---

## 12. Default Login Credentials

These credentials are created when you first seed the database. **Change them after first login in a production environment.**

| Role | Email | Password |
|---|---|---|
| Admin | admin@company.com | Admin@1234 |
| Manager | manager@company.com | Manager@1234 |
| Agent | agent@company.com | Agent@1234 |

---

## Processing Pipeline Summary

When you upload a call, this is the full pipeline that runs automatically:

```
Upload audio file
       ↓
Store in MinIO (object storage)
       ↓
Celery worker picks up the job
       ↓
ML Service transcribes audio (faster-whisper)
       ↓
Speaker diarization — labels each segment AGENT / CUSTOMER
       ↓
Acoustic feature extraction (librosa + parselmouth)
       ↓
NLP analysis (spaCy + NLTK) + Grammar check (LanguageTool)
       ↓
Speech Quality Score calculated (8 dimensions, automated)
       ↓
Ollama LLM evaluates Sales Quality (8 dimensions + justifications)
       ↓
LLM generates Summary, Key Moments, Coaching Suggestions
       ↓
LLM classifies Disposition (18 categories)
       ↓
Coaching clips and objections extracted
       ↓
Transcript indexed in OpenSearch for full-text search
       ↓
Embeddings stored in PostgreSQL (pgvector) for semantic search
       ↓
Status set to COMPLETED — results visible in the UI
```

---

*Sales Call Analyzer — Internal tool for sales team quality management*
*Running on: localhost | Stack: React + FastAPI + PostgreSQL + Ollama*
