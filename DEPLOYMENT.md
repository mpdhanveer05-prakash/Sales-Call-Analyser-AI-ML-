# Deployment Guide — Sales Call Analyzer

Reference for deploying on AWS EC2 or on-premises Windows/Linux servers.

---

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [First-Time Server Setup](#2-first-time-server-setup)
3. [NVIDIA GPU Setup (if GPU available)](#3-nvidia-gpu-setup)
4. [Application Deployment](#4-application-deployment)
5. [Environment Variables (.env)](#5-environment-variables)
6. [Post-Deploy Steps](#6-post-deploy-steps)
7. [Updating the Application](#7-updating-the-application)
8. [Useful Diagnostic Commands](#8-useful-diagnostic-commands)
9. [On-Premises Specific Notes](#9-on-premises-specific-notes)

---

## 1. Prerequisites

### AWS EC2
- Instance type: **t3.2xlarge** (CPU) or **g4dn.xlarge / g5.xlarge** (GPU recommended)
- OS: Ubuntu 22.04 LTS
- Storage: 50 GB root volume minimum (GPU: 80 GB — model weights are large)
- Security Group inbound rules:
  - Port 22 (SSH)
  - Port 80 (HTTP — frontend)
  - Port 3000 (optional — direct API access)

### On-Premises
- OS: Ubuntu 22.04 LTS or Windows Server 2019/2022
- RAM: 16 GB minimum (32 GB recommended for GPU + large-v3)
- Storage: 80 GB free minimum
- GPU: NVIDIA GPU with 8 GB VRAM minimum (for Whisper large-v3)

---

## 2. First-Time Server Setup

Run once on a fresh Ubuntu server (AWS or on-prem).

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Verify Docker
docker --version
docker compose version

# Install Git
sudo apt-get install -y git

# Clone the repository
git clone https://github.com/mpdhanveer05-prakash/Sales-Call-Analyser-AI-ML-.git
cd Sales-Call-Analyser-AI-ML-

# Create .env from example
cp .env.example .env
nano .env   # Fill in all required values (see Section 5)
```

---

## 3. NVIDIA GPU Setup

Run this section only if your server has an NVIDIA GPU.

### Step 1 — Install NVIDIA Driver (skip if already installed)

```bash
# Check if driver is already installed
nvidia-smi

# If not installed, install the driver
sudo apt-get install -y ubuntu-drivers-common
sudo ubuntu-drivers autoinstall
sudo reboot
# After reboot, verify:
nvidia-smi
```

### Step 2 — Install NVIDIA Container Toolkit (required for Docker GPU access)

```bash
# Add NVIDIA repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Register NVIDIA runtime with Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify GPU is accessible inside Docker
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

### Step 3 — Verify GPU config in docker-compose.yml

The `ml-service` in `docker-compose.yml` already has GPU enabled:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

If running on a **CPU-only machine**, add these to `.env` to override:
```
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

---

## 4. Application Deployment

### Pull Ollama Model (first time only)

```bash
# Start infrastructure services first
docker compose up -d postgres redis minio opensearch languagetool ollama

# Wait ~30 seconds for services to be healthy, then pull the LLM model
docker exec sca-ollama ollama pull llama3.1:8b

# Verify model is available
docker exec sca-ollama ollama list
```

### Build and Start All Services

```bash
# Build application images
docker compose --profile app build

# Start everything
docker compose --profile app up -d

# Verify all containers are running
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Run Database Migrations (first time and after code updates)

```bash
docker exec sca-backend alembic upgrade head
```

### Seed Initial Users (first time only)

```bash
docker exec sca-backend python scripts/seed_users.py
```

Default credentials after seeding:
| Role | Email | Password |
|---|---|---|
| Admin | admin@company.com | Admin@1234 |
| Manager | manager@company.com | Manager@1234 |
| Agent | agent@company.com | Agent@1234 |

---

## 5. Environment Variables

Create `.env` in the project root. Never commit this file.

```env
# ── PostgreSQL ──────────────────────────────────────────────
POSTGRES_DB=sales_call_analyzer
POSTGRES_USER=sca_user
POSTGRES_PASSWORD=your_strong_password_here

DATABASE_URL=postgresql+asyncpg://sca_user:your_strong_password_here@postgres:5432/sales_call_analyzer
DATABASE_URL_SYNC=postgresql+psycopg2://sca_user:your_strong_password_here@postgres:5432/sales_call_analyzer

# ── Redis ────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── MinIO ────────────────────────────────────────────────────
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_strong_minio_password
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=your_strong_minio_password
MINIO_ENDPOINT=minio:9000
MINIO_SECURE=false

# ── JWT ──────────────────────────────────────────────────────
JWT_SECRET_KEY=replace_with_long_random_string_here

# ── Ollama ───────────────────────────────────────────────────
OLLAMA_URL=http://ollama:11434
OLLAMA_DEFAULT_MODEL=llama3.1:8b
OLLAMA_TIMEOUT_SECONDS=900

# ── Whisper (GPU machine) ────────────────────────────────────
WHISPER_MODEL_SIZE=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16

# ── Whisper (CPU machine — uncomment and comment out GPU lines above)
# WHISPER_MODEL_SIZE=small
# WHISPER_DEVICE=cpu
# WHISPER_COMPUTE_TYPE=int8

# ── OpenSearch ───────────────────────────────────────────────
OPENSEARCH_URL=http://opensearch:9200

# ── LanguageTool ─────────────────────────────────────────────
LANGUAGETOOL_URL=http://languagetool:8010

# ── ML Service ───────────────────────────────────────────────
ML_SERVICE_URL=http://ml-service:8001

# ── CORS (comma-separated allowed origins) ───────────────────
# AWS:    ALLOWED_ORIGINS=http://<your-ec2-ip>
# OnPrem: ALLOWED_ORIGINS=http://<server-ip>,http://localhost:5173
ALLOWED_ORIGINS=http://localhost:5173,http://localhost

# ── App ──────────────────────────────────────────────────────
ENVIRONMENT=production
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE_MB=500

# ── Seed credentials (change these) ──────────────────────────
SEED_ADMIN_EMAIL=admin@company.com
SEED_ADMIN_PASSWORD=Admin@1234
SEED_MANAGER_EMAIL=manager@company.com
SEED_MANAGER_PASSWORD=Manager@1234
SEED_AGENT_EMAIL=agent@company.com
SEED_AGENT_PASSWORD=Agent@1234

# ── Optional: HuggingFace token for Pyannote diarization ─────
# HUGGINGFACE_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx

# ── Optional: Claude API key (bypasses Ollama for LLM tasks) ─
# CLAUDE_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
```

---

## 6. Post-Deploy Steps

```bash
# Verify frontend is accessible
curl -s -o /dev/null -w "%{http_code}" http://localhost/

# Verify backend API is healthy
curl http://localhost/health

# Verify ML service is running
curl http://localhost:8001/health

# Check GPU is being used by ml-service (GPU only)
docker exec sca-ml-service python -c "import torch; print('CUDA:', torch.cuda.is_available())"

# Watch all logs together
docker compose logs -f --tail=50
```

---

## 7. Updating the Application

Run these after every code push:

```bash
# Pull latest code
git pull

# Rebuild changed images
docker compose --profile app build backend ml-service

# Recreate containers (picks up new .env values too)
docker compose --profile app up -d --force-recreate backend celery-worker ml-service

# Run any new migrations
docker exec sca-backend alembic upgrade head
```

> **Important:** `docker compose restart` does NOT reload `.env` variables.
> Always use `--force-recreate` after changing `.env` or after `git pull`.

---

## 8. Useful Diagnostic Commands

```bash
# ── Container status ────────────────────────────────────────
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# ── Live logs ───────────────────────────────────────────────
docker logs -f sca-backend
docker logs -f sca-celery-worker
docker logs -f sca-ml-service

# ── Check env variable inside a container ───────────────────
docker exec sca-celery-worker env | grep OLLAMA
docker exec sca-ml-service env | grep WHISPER

# ── Redis queue depth ────────────────────────────────────────
docker exec sca-redis redis-cli llen celery

# ── Database: list users ─────────────────────────────────────
docker exec sca-postgres psql -U sca_user -d sales_call_analyzer -c "SELECT email, role FROM users;"

# ── Database: check pending calls ───────────────────────────
docker exec sca-postgres psql -U sca_user -d sales_call_analyzer -c "SELECT id, status, disposition FROM calls ORDER BY created_at DESC LIMIT 10;"

# ── Ollama: list loaded models ───────────────────────────────
docker exec sca-ollama ollama list

# ── GPU utilisation (GPU machines only) ─────────────────────
watch -n 2 nvidia-smi

# ── Disk usage ───────────────────────────────────────────────
docker system df
df -h
```

---

## 9. On-Premises Specific Notes

### Network / Firewall
```bash
# Open port 80 for the frontend (Ubuntu ufw)
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

### ALLOWED_ORIGINS in .env
Set this to your on-prem server's IP or hostname:
```
ALLOWED_ORIGINS=http://192.168.1.100,http://your-internal-hostname
```

### Windows Server (Docker Desktop)
- Install Docker Desktop for Windows with WSL2 backend
- GPU passthrough requires WSL2 + NVIDIA drivers for WSL
- Run all `docker compose` commands in PowerShell or WSL terminal
- Paths in `.env` use forward slashes even on Windows

### Persisted Data (Docker Volumes)
All data is stored in named Docker volumes — safe across container restarts:
| Volume | Contents |
|---|---|
| `postgres_data` | All call records, scores, users |
| `minio_data` | Audio recordings |
| `redis_data` | Task queue state |
| `ollama_data` | Downloaded LLM models |
| `ml_models` | Whisper model weights |

To back up PostgreSQL:
```bash
docker exec sca-postgres pg_dump -U sca_user sales_call_analyzer > backup_$(date +%Y%m%d).sql
```

To restore:
```bash
docker exec -i sca-postgres psql -U sca_user -d sales_call_analyzer < backup_20260421.sql
```
