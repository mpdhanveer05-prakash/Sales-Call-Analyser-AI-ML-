# Windows Server Deployment Guide

> **Phase 7 reference.** Do not start until Phase 6 is fully signed off on localhost.

This guide migrates the localhost Docker Compose stack to a Windows Server.
The architecture is identical — same containers, same config — with production overrides applied.

---

## Server Requirements

| Resource | Minimum | Recommended |
|---|---|---|
| OS | Windows Server 2019 | Windows Server 2022 |
| CPU | 8 cores | 16 cores |
| RAM | 32 GB | 64 GB |
| Disk (OS + app) | 100 GB SSD | 200 GB NVMe SSD |
| Disk (data volumes) | 500 GB | 1 TB |
| GPU | None (CPU mode) | NVIDIA RTX 3080+ (for GPU whisper) |
| Network | LAN access for sales team | Static IP or hostname |

### GPU Note
If the server has an NVIDIA GPU, install:
- [NVIDIA Game Ready / Studio Driver](https://www.nvidia.com/Download/index.aspx)
- [CUDA Toolkit 12.x](https://developer.nvidia.com/cuda-downloads)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

Then set `WHISPER_DEVICE=cuda` in `.env` and update `ml-service` in `docker-compose.prod.yml` to expose the GPU.

---

## Prerequisites on Windows Server

1. **Install Docker Desktop** (or Docker Engine for Windows Server)
   - Download: [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
   - Enable WSL2 backend (recommended) or Hyper-V backend
   - Verify: `docker --version` and `docker compose version`

2. **Clone the repository**
   ```cmd
   git clone <repo-url> C:\apps\sales-call-analyzer
   cd C:\apps\sales-call-analyzer
   ```

3. **Create production `.env`**
   ```cmd
   copy .env.example .env
   notepad .env
   ```
   Update all values marked `CHANGE_IN_PRODUCTION` (see section below).

---

## Production `.env` Changes

| Variable | Localhost Value | Production Value |
|---|---|---|
| `POSTGRES_PASSWORD` | `postgres` | Strong random password (32+ chars) |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | Strong random password |
| `JWT_SECRET_KEY` | `dev-secret` | `openssl rand -hex 32` output |
| `REDIS_PASSWORD` | *(none)* | Add `requirepass <password>` to redis config |
| `BACKEND_CORS_ORIGINS` | `http://localhost:5173` | `http://<server-ip>:5173` or domain |
| `OLLAMA_HOST` | `http://ollama:11434` | *(unchanged — internal Docker network)* |

---

## Create `docker-compose.prod.yml`

Place this file alongside `docker-compose.yml`. It applies production overrides only.

```yaml
# docker-compose.prod.yml — production overrides
# Usage: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

services:
  backend:
    restart: always
    environment:
      - ENV=production

  frontend:
    restart: always

  ml-service:
    restart: always
    # Uncomment below if server has NVIDIA GPU:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: all
    #           capabilities: [gpu]

  postgres:
    restart: always
    volumes:
      - C:/data/sca/postgres:/var/lib/postgresql/data

  redis:
    restart: always
    volumes:
      - C:/data/sca/redis:/data

  minio:
    restart: always
    volumes:
      - C:/data/sca/minio:/data

  opensearch:
    restart: always
    volumes:
      - C:/data/sca/opensearch:/usr/share/opensearch/data

  ollama:
    restart: always
    volumes:
      - C:/data/sca/ollama:/root/.ollama

  celery-worker:
    restart: always
```

Create the data directories before first launch:
```cmd
mkdir C:\data\sca\postgres
mkdir C:\data\sca\redis
mkdir C:\data\sca\minio
mkdir C:\data\sca\opensearch
mkdir C:\data\sca\ollama
```

---

## First-Time Launch

```cmd
cd C:\apps\sales-call-analyzer

# Start all services with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify all containers are healthy
docker compose ps

# Pull the LLM model (one-time, ~4–8 GB download)
docker exec sca-ollama ollama pull llama3.1:8b

# Run database migrations
docker exec sca-backend alembic upgrade head

# Seed default users (change passwords immediately after)
docker exec sca-backend python scripts/seed_users.py
```

---

## Windows Firewall Rules

Open ports for sales team LAN access:

```powershell
# Run as Administrator
New-NetFirewallRule -DisplayName "SCA Frontend" -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow
New-NetFirewallRule -DisplayName "SCA Backend API" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow
New-NetFirewallRule -DisplayName "SCA MinIO Console" -Direction Inbound -Protocol TCP -LocalPort 9001 -Action Allow
```

Do **not** open ports 5432 (PostgreSQL), 6379 (Redis), 8001 (ML service), or 9200 (OpenSearch) externally.

---

## Windows Task Scheduler — Nightly Backup

Create a scheduled task to back up PostgreSQL nightly:

1. Open **Task Scheduler** → Create Basic Task
2. Name: `SCA Database Backup`
3. Trigger: Daily at 2:00 AM
4. Action: Start a program
5. Program: `cmd.exe`
6. Arguments:
   ```
   /c docker exec sca-postgres pg_dump -U postgres sca_db > C:\backups\sca\db_%date:~-4,4%%date:~-10,2%%date:~7,2%.sql
   ```

Create the backup directory:
```cmd
mkdir C:\backups\sca
```

Add a cleanup task to delete backups older than 30 days:
```
/c forfiles /p C:\backups\sca /m *.sql /d -30 /c "cmd /c del @path"
```

---

## Keeping the App Updated

```cmd
cd C:\apps\sales-call-analyzer

# Pull latest code
git pull origin main

# Rebuild changed containers only
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Apply any new database migrations
docker exec sca-backend alembic upgrade head

# Restart services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## Health Check URLs (from server or LAN)

| Service | URL |
|---|---|
| App (Frontend) | `http://<server-ip>:5173` |
| API Health | `http://<server-ip>:3000/health` |
| API Docs | `http://<server-ip>:3000/docs` |
| MinIO Console | `http://<server-ip>:9001` |

---

## Troubleshooting

### Container fails to start
```cmd
docker compose logs <service-name>
```

### Database migration fails
```cmd
docker exec -it sca-backend alembic history
docker exec -it sca-backend alembic current
```

### Ollama model missing after restart
```cmd
docker exec sca-ollama ollama list
docker exec sca-ollama ollama pull llama3.1:8b
```

### OpenSearch out of disk space
OpenSearch requires `vm.max_map_count=262144`. On Windows with WSL2 backend:
```powershell
wsl -d docker-desktop sysctl -w vm.max_map_count=262144
```
To make permanent, add to `%USERPROFILE%\.wslconfig`:
```ini
[wsl2]
kernelCommandLine = sysctl.vm.max_map_count=262144
```

### Reset everything (destructive)
```cmd
docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v
# Then re-run first-time launch steps above
```

---

*Phase 7 — do not start until Phase 6 is fully signed off.*
