# AWS Deployment Guide — Sales Call Analyzer

Complete reference for migrating and deploying on AWS EC2 with GPU support.

---

## Table of Contents

0. [Full AWS CLI Setup Script](#0-full-aws-cli-setup-script)
1. [Instance Sizing](#1-instance-sizing)
2. [Request GPU Quota](#2-request-gpu-quota)
3. [Launch EC2 Instance](#3-launch-ec2-instance)
4. [Security Group Rules](#4-security-group-rules)
5. [Assign Elastic IP](#5-assign-elastic-ip)
6. [Server Setup (Docker + NVIDIA)](#6-server-setup)
7. [Clone and Configure](#7-clone-and-configure)
8. [Deploy the Application](#8-deploy-the-application)
9. [Verify Everything Works](#9-verify-everything-works)
10. [Updating After Code Changes](#10-updating-after-code-changes)
11. [Diagnostic Commands](#11-diagnostic-commands)
12. [Backup and Restore](#12-backup-and-restore)
13. [Cost Breakdown](#13-cost-breakdown)

---

## 0. Full AWS CLI Setup Script

Run this entire block from your **local machine** (requires AWS CLI installed and configured with `aws configure`).
It creates every AWS resource needed and prints the SSH command at the end.

### Prerequisites

```bash
# Install AWS CLI (if not already installed)
# macOS
brew install awscli

# Windows (PowerShell)
winget install Amazon.AWSCLI

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Configure credentials
aws configure
# Enter: AWS Access Key ID, Secret Access Key, Region (e.g. us-east-1), Output format (json)

# Verify
aws sts get-caller-identity
```

### Step 0.1 — Set variables (edit these before running)

```bash
REGION="us-east-1"
INSTANCE_TYPE="g5.2xlarge"
KEY_NAME="sca-key"
SG_NAME="sca-sg"
INSTANCE_NAME="sca-production"
YOUR_IP="$(curl -s https://checkip.amazonaws.com)/32"   # auto-detects your current IP
VOLUME_SIZE=100

echo "Your IP: $YOUR_IP"
echo "Region:  $REGION"
```

### Step 0.2 — Request GPU quota (must be approved before launching)

```bash
aws service-quotas request-service-quota-increase \
  --service-code ec2 \
  --quota-code L-DB2E81BA \
  --desired-value 8 \
  --region $REGION

# Check approval status (run again after a few hours)
aws service-quotas list-requested-changes-by-service \
  --service-code ec2 \
  --region $REGION \
  --query "RequestedQuotas[?QuotaName=='Running On-Demand G and VT instances'].{Status:Status,Value:DesiredValue}" \
  --output table
```

### Step 0.3 — Create SSH key pair

```bash
# Create key pair and save the .pem file locally
aws ec2 create-key-pair \
  --key-name $KEY_NAME \
  --query "KeyMaterial" \
  --output text \
  --region $REGION > ~/${KEY_NAME}.pem

# Secure the key file
chmod 400 ~/${KEY_NAME}.pem

echo "Key saved to: ~/${KEY_NAME}.pem"
```

### Step 0.4 — Create security group

```bash
# Get your default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region $REGION)

echo "VPC ID: $VPC_ID"

# Create security group
SG_ID=$(aws ec2 create-security-group \
  --group-name $SG_NAME \
  --description "Sales Call Analyzer security group" \
  --vpc-id $VPC_ID \
  --region $REGION \
  --query "GroupId" \
  --output text)

echo "Security Group ID: $SG_ID"

# SSH — your IP only
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 22 \
  --cidr $YOUR_IP \
  --region $REGION

# HTTP — public (frontend)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region $REGION

# Backend API — your IP only (optional direct API access)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 3000 \
  --cidr $YOUR_IP \
  --region $REGION

echo "Security group rules added"
```

### Step 0.5 — Find latest Ubuntu 22.04 AMI

```bash
AMI_ID=$(aws ec2 describe-images \
  --owners 099720109477 \
  --filters \
    "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    "Name=state,Values=available" \
    "Name=architecture,Values=x86_64" \
  --query "sort_by(Images, &CreationDate)[-1].ImageId" \
  --output text \
  --region $REGION)

echo "Latest Ubuntu 22.04 AMI: $AMI_ID"
```

### Step 0.6 — Launch EC2 instance

```bash
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY_NAME \
  --security-group-ids $SG_ID \
  --block-device-mappings "[{
    \"DeviceName\": \"/dev/sda1\",
    \"Ebs\": {
      \"VolumeSize\": $VOLUME_SIZE,
      \"VolumeType\": \"gp3\",
      \"Iops\": 3000,
      \"Throughput\": 125,
      \"DeleteOnTermination\": true
    }
  }]" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
  --region $REGION \
  --query "Instances[0].InstanceId" \
  --output text)

echo "Instance ID: $INSTANCE_ID"

# Wait until the instance is running
echo "Waiting for instance to be running..."
aws ec2 wait instance-running \
  --instance-ids $INSTANCE_ID \
  --region $REGION

echo "Instance is running"
```

### Step 0.7 — Allocate and associate Elastic IP

```bash
# Allocate a new Elastic IP
ALLOC_ID=$(aws ec2 allocate-address \
  --domain vpc \
  --region $REGION \
  --query "AllocationId" \
  --output text)

echo "Elastic IP Allocation ID: $ALLOC_ID"

# Associate it with the instance
aws ec2 associate-address \
  --instance-id $INSTANCE_ID \
  --allocation-id $ALLOC_ID \
  --region $REGION

# Get the actual public IP
ELASTIC_IP=$(aws ec2 describe-addresses \
  --allocation-ids $ALLOC_ID \
  --query "Addresses[0].PublicIp" \
  --output text \
  --region $REGION)

echo "Elastic IP: $ELASTIC_IP"
```

### Step 0.8 — Print summary and SSH command

```bash
echo ""
echo "============================================"
echo " AWS Infrastructure Created Successfully"
echo "============================================"
echo " Instance ID:      $INSTANCE_ID"
echo " Instance Type:    $INSTANCE_TYPE"
echo " AMI:              $AMI_ID"
echo " Security Group:   $SG_ID"
echo " Key Pair:         ~/${KEY_NAME}.pem"
echo " Elastic IP:       $ELASTIC_IP"
echo " Region:           $REGION"
echo "============================================"
echo ""
echo " SSH command:"
echo " ssh -i ~/${KEY_NAME}.pem ubuntu@${ELASTIC_IP}"
echo ""
echo " After SSH — follow Section 6 onwards in this guide."
echo "============================================"
```

### Teardown — delete everything when no longer needed

```bash
# Stop instance first (optional — terminate does this anyway)
aws ec2 stop-instances --instance-ids $INSTANCE_ID --region $REGION
aws ec2 wait instance-stopped --instance-ids $INSTANCE_ID --region $REGION

# Terminate instance (deletes root EBS volume too — all Docker volumes lost)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION
aws ec2 wait instance-terminated --instance-ids $INSTANCE_ID --region $REGION

# Release Elastic IP (otherwise charged $0.005/hr when unattached)
aws ec2 release-address --allocation-id $ALLOC_ID --region $REGION

# Delete security group
aws ec2 delete-security-group --group-id $SG_ID --region $REGION

# Delete key pair (also delete the local .pem manually)
aws ec2 delete-key-pair --key-name $KEY_NAME --region $REGION
rm ~/${KEY_NAME}.pem

echo "All AWS resources deleted"
```

---

## 1. Instance Sizing

### Models running in this application

| Model | VRAM | RAM | Purpose |
|---|---|---|---|
| Whisper large-v3 | ~3 GB | — | Transcription |
| llama3.1:8b (4-bit) | ~5 GB | — | LLM analysis |
| all-MiniLM-L6-v2 | minimal | ~500 MB | Embeddings |
| spaCy en_core_web_sm | — | ~200 MB | NLP |
| **Total GPU VRAM needed** | **~8 GB** | | |

### Instance recommendations

| Use Case | Instance | vCPU | RAM | GPU | VRAM | Cost/hr | Cost/mo |
|---|---|---|---|---|---|---|---|
| Dev / Testing | t3.2xlarge | 8 | 32 GB | None | — | $0.33 | ~$240 |
| Small team < 20 calls/day | g4dn.xlarge | 4 | 16 GB | T4 | 16 GB | $0.53 | ~$380 |
| Standard 20–100 calls/day | g4dn.2xlarge | 8 | 32 GB | T4 | 16 GB | $0.75 | ~$540 |
| **Recommended: 100+ calls/day** | **g5.2xlarge** | **8** | **32 GB** | **A10G** | **24 GB** | **$1.21** | **~$875** |

**Why g5.2xlarge is the right choice:**
- A10G has 24 GB VRAM — fits Whisper large-v3 (~3 GB) + llama3.1:8b (~5 GB) simultaneously with 16 GB spare
- llama3.1:8b runs at ~120 tokens/sec on A10G vs ~10 tokens/sec on CPU
- Full 5-minute call processes in ~30–60 seconds end-to-end

### Storage

| Volume | Size | Type |
|---|---|---|
| Root EBS | 100 GB | gp3 |

What fills the disk:
- Docker images (all services): ~15 GB
- Whisper large-v3 weights: ~3 GB (downloaded on first transcription)
- llama3.1:8b weights: ~5 GB (downloaded via `ollama pull`)
- OS + tools: ~10 GB
- Audio recordings (MinIO): grows with usage

**100 GB is minimum. Use 150 GB if you expect heavy audio recording volume.**

---

## 2. Request GPU Quota

AWS accounts default to 0 vCPU allowance for GPU instances. Request this first — it must be approved before you can launch.

### Via AWS Console

1. Open **AWS Console → Service Quotas → EC2**
2. Search: `Running On-Demand G and VT instances`
3. Click the quota → **Request increase at account level**
4. Set value to **8** (g5.2xlarge needs 8 vCPUs)
5. Business justification: `Running AI/ML workloads with GPU-accelerated LLM and speech transcription`
6. Submit — typically approved within a few hours to 1 business day

### Via AWS CLI

```bash
aws service-quotas request-service-quota-increase \
  --service-code ec2 \
  --quota-code L-DB2E81BA \
  --desired-value 8 \
  --region us-east-1
```

Check status:
```bash
aws service-quotas list-requested-changes-by-service --service-code ec2
```

---

## 3. Launch EC2 Instance

### Via AWS Console

1. Go to **EC2 → Launch Instance**
2. **Name:** `sca-production`
3. **AMI:** Ubuntu Server 22.04 LTS (HVM), SSD Volume Type
   - Search for `Ubuntu 22.04` in the AMI catalog
   - us-east-1 AMI ID: `ami-0c7217cdde317cfec` (verify this is current)
4. **Instance type:** `g5.2xlarge`
5. **Key pair:** Create new → name `sca-key` → download `.pem` → store securely
6. **Network settings:**
   - Auto-assign public IP: **Enable**
   - Create new security group named `sca-sg` (configure ports in Section 4)
7. **Storage:** 100 GB, type **gp3**, IOPS 3000, Throughput 125 MB/s
8. **Launch instance**

### Via AWS CLI

```bash
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \
  --instance-type g5.2xlarge \
  --key-name sca-key \
  --security-group-ids sg-XXXXXXXXXXXXXXXXX \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":100,"VolumeType":"gp3","Iops":3000,"Throughput":125}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=sca-production}]' \
  --region us-east-1
```

---

## 4. Security Group Rules

Go to **EC2 → Security Groups → Create security group**, name it `sca-sg`.

### Inbound rules

| Type | Protocol | Port | Source | Purpose |
|---|---|---|---|---|
| SSH | TCP | 22 | Your IP only (`x.x.x.x/32`) | Server access |
| HTTP | TCP | 80 | `0.0.0.0/0` | Frontend (React UI) |
| Custom TCP | TCP | 3000 | Your IP only | Backend API direct access (optional) |

> **Never expose** ports 5432 (Postgres), 6379 (Redis), 9200 (OpenSearch), 9000/9001 (MinIO), 8001 (ML service), or 11434 (Ollama). All internal services communicate over the Docker network only.

### Outbound rules

| Type | Protocol | Port | Destination |
|---|---|---|---|
| All traffic | All | All | `0.0.0.0/0` |

---

## 5. Assign Elastic IP

Elastic IP gives you a static IP that survives stop/start cycles.

**Via Console:** EC2 → Elastic IPs → Allocate Elastic IP → Associate → select your instance

**Via CLI:**
```bash
# Allocate
ALLOC_ID=$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)
echo $ALLOC_ID

# Associate with your instance
aws ec2 associate-address \
  --instance-id i-XXXXXXXXXXXXXXXXX \
  --allocation-id $ALLOC_ID
```

---

## 6. Server Setup

SSH into the instance:

```bash
chmod 400 ~/sca-key.pem
ssh -i ~/sca-key.pem ubuntu@<YOUR-ELASTIC-IP>
```

All commands below run on the server.

### Step 6.1 — Update system

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y curl git htop unzip
```

### Step 6.2 — Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version        # Docker version 24.x or higher
docker compose version  # Docker Compose version v2.x or higher
```

### Step 6.3 — Install NVIDIA Driver

```bash
# Check if already installed
nvidia-smi

# If not installed:
sudo apt-get install -y ubuntu-drivers-common
sudo ubuntu-drivers autoinstall
sudo reboot
```

After reboot, SSH back in and verify:
```bash
nvidia-smi
# Expected output: NVIDIA-SMI, Driver Version: 535.x+, GPU: NVIDIA A10G
```

### Step 6.4 — Install NVIDIA Container Toolkit

```bash
# Add NVIDIA package repository
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

# Verify — should print GPU info from inside a container
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

### Step 6.5 — Fix system limits for OpenSearch

```bash
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Verify
sysctl vm.max_map_count
# Expected: vm.max_map_count = 262144
```

---

## 7. Clone and Configure

### Step 7.1 — Clone repository

```bash
cd ~
git clone https://github.com/mpdhanveer05-prakash/Sales-Call-Analyser-AI-ML-.git
cd Sales-Call-Analyser-AI-ML-
```

### Step 7.2 — Generate a secure JWT key

```bash
openssl rand -hex 64
# Copy this output — paste it as JWT_SECRET_KEY below
```

### Step 7.3 — Create and fill .env

```bash
cp .env.example .env
nano .env
```

Complete `.env` for g5.2xlarge:

```env
# ── PostgreSQL ────────────────────────────────────────────────────────────────
POSTGRES_DB=sales_call_analyzer
POSTGRES_USER=sca_user
POSTGRES_PASSWORD=CHANGE_THIS_STRONG_PASSWORD

DATABASE_URL=postgresql+asyncpg://sca_user:CHANGE_THIS_STRONG_PASSWORD@postgres:5432/sales_call_analyzer
DATABASE_URL_SYNC=postgresql+psycopg2://sca_user:CHANGE_THIS_STRONG_PASSWORD@postgres:5432/sales_call_analyzer

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── MinIO ─────────────────────────────────────────────────────────────────────
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=CHANGE_THIS_MINIO_PASSWORD
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=CHANGE_THIS_MINIO_PASSWORD
MINIO_ENDPOINT=minio:9000
MINIO_SECURE=false

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_SECRET_KEY=PASTE_OUTPUT_OF_openssl_rand_-hex_64_HERE

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_URL=http://ollama:11434
OLLAMA_DEFAULT_MODEL=llama3.1:8b
OLLAMA_TIMEOUT_SECONDS=120

# ── Whisper — GPU (g5.2xlarge / A10G) ────────────────────────────────────────
WHISPER_MODEL_SIZE=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16

# ── OpenSearch ────────────────────────────────────────────────────────────────
OPENSEARCH_URL=http://opensearch:9200

# ── LanguageTool ──────────────────────────────────────────────────────────────
LANGUAGETOOL_URL=http://languagetool:8010

# ── ML Service ────────────────────────────────────────────────────────────────
ML_SERVICE_URL=http://ml-service:8001

# ── CORS — replace with your Elastic IP ──────────────────────────────────────
ALLOWED_ORIGINS=http://<YOUR-ELASTIC-IP>

# ── App ───────────────────────────────────────────────────────────────────────
ENVIRONMENT=production
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE_MB=500

# ── Seed credentials (change before first deploy) ─────────────────────────────
SEED_ADMIN_EMAIL=admin@yourcompany.com
SEED_ADMIN_PASSWORD=ChangeThisAdmin@1234
SEED_MANAGER_EMAIL=manager@yourcompany.com
SEED_MANAGER_PASSWORD=ChangeThisManager@1234
SEED_AGENT_EMAIL=agent@yourcompany.com
SEED_AGENT_PASSWORD=ChangeThisAgent@1234

# ── Optional: HuggingFace token (enables Pyannote diarization on mono audio) ──
# HUGGINGFACE_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx

# ── Optional: Claude API (bypasses Ollama, faster + more accurate) ────────────
# CLAUDE_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
```

---

## 8. Deploy the Application

Run these in order on the server.

### Step 8.1 — Start infrastructure services

```bash
docker compose up -d postgres redis minio opensearch languagetool ollama

# Wait ~60 seconds then check all are healthy
watch docker ps --format "table {{.Names}}\t{{.Status}}"
# Press Ctrl+C when all show "healthy" or stable "Up X seconds"
```

### Step 8.2 — Pull Ollama LLM model

```bash
# ~5 GB download — wait for it to complete fully
docker exec sca-ollama ollama pull llama3.1:8b

# Verify
docker exec sca-ollama ollama list
# Expected: llama3.1:8b   ...   5.0 GB
```

### Step 8.3 — Build application images

```bash
# First-time build takes 5–10 minutes (downloads Python packages)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile app build
```

### Step 8.4 — Start all services with GPU

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile app up -d

# Verify all 10 containers are running
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected containers:

```
sca-frontend       Up ... (healthy)   0.0.0.0:80->80/tcp
sca-backend        Up ...             0.0.0.0:3000->3000/tcp
sca-celery-worker  Up ...
sca-ml-service     Up ...             0.0.0.0:8001->8001/tcp
sca-ollama         Up ...             0.0.0.0:11434->11434/tcp
sca-languagetool   Up ... (healthy)   0.0.0.0:8010->8010/tcp
sca-opensearch     Up ... (healthy)   0.0.0.0:9200->9200/tcp
sca-minio          Up ... (healthy)   0.0.0.0:9000-9001->9000-9001/tcp
sca-redis          Up ... (healthy)   127.0.0.1:6379->6379/tcp
sca-postgres       Up ... (healthy)   127.0.0.1:5432->5432/tcp
```

### Step 8.5 — Run database migrations

```bash
docker exec sca-backend alembic upgrade head
# Should end with: INFO  [alembic.runtime.migration] Running upgrade ... -> ...
```

### Step 8.6 — Seed initial users (first time only)

```bash
docker exec sca-backend python scripts/seed_users.py
```

---

## 9. Verify Everything Works

```bash
# Frontend loads
curl -s -o /dev/null -w "%{http_code}" http://localhost/
# Expected: 200

# Backend healthy
curl http://localhost:3000/health
# Expected: {"status":"healthy",...}

# ML service healthy
curl http://localhost:8001/health
# Expected: {"status":"ok"}

# Whisper loaded on GPU
docker logs sca-ml-service | grep -i whisper
# Expected: Loading Whisper 'large-v3' on cuda (float16)
#           Whisper model loaded

# Ollama has the model
curl http://localhost:11434/api/tags
# Expected: {"models":[{"name":"llama3.1:8b",...}]}

# GPU is being used
nvidia-smi
# After uploading a test call: GPU-Util should spike, Memory-Usage shows ~8 GB

# Database has users
docker exec sca-postgres psql -U sca_user -d sales_call_analyzer \
  -c "SELECT email, role FROM users;"
```

Open `http://<YOUR-ELASTIC-IP>` in your browser and log in with the admin credentials.

---

## 10. Updating After Code Changes

```bash
# 1. Pull latest code
git pull

# 2. Rebuild changed images
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile app build \
  backend celery-worker ml-service frontend

# 3. Force-recreate containers (picks up new .env values too)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile app up -d \
  --force-recreate backend celery-worker ml-service frontend

# 4. Run any new migrations
docker exec sca-backend alembic upgrade head
```

> **Critical:** `docker compose restart` does NOT reload `.env` variables.
> Always use `--force-recreate` after `git pull` or `.env` changes.

---

## 11. Diagnostic Commands

```bash
# All container status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Live logs per service
docker logs -f sca-backend
docker logs -f sca-celery-worker
docker logs -f sca-ml-service

# All service logs together
docker compose -f docker-compose.yml -f docker-compose.gpu.yml logs -f --tail=50

# GPU utilisation (live)
watch -n 2 nvidia-smi

# Check Whisper/Ollama device inside containers
docker exec sca-ml-service env | grep WHISPER
docker exec sca-celery-worker env | grep OLLAMA

# Redis queue depth (0 = all jobs done)
docker exec sca-redis redis-cli llen celery

# Recent calls and their status
docker exec sca-postgres psql -U sca_user -d sales_call_analyzer \
  -c "SELECT id, status, disposition, sales_score, created_at FROM calls ORDER BY created_at DESC LIMIT 10;"

# Calls stuck in processing (should be empty when idle)
docker exec sca-postgres psql -U sca_user -d sales_call_analyzer \
  -c "SELECT id, status, created_at FROM calls WHERE status NOT IN ('COMPLETED','FAILED','CANCELLED');"

# Ollama models available
docker exec sca-ollama ollama list

# Disk usage
docker system df
df -h /

# Memory usage per container
docker stats --no-stream
```

---

## 12. Backup and Restore

### Backup PostgreSQL

```bash
mkdir -p ~/backups

# Dump database
docker exec sca-postgres pg_dump -U sca_user sales_call_analyzer \
  | gzip > ~/backups/sca_db_$(date +%Y%m%d_%H%M).sql.gz

# List backups
ls -lh ~/backups/
```

### Restore PostgreSQL

```bash
# Stop app services (keep postgres running)
docker compose --profile app stop backend celery-worker

# Restore
gunzip -c ~/backups/sca_db_20260503_1200.sql.gz | \
  docker exec -i sca-postgres psql -U sca_user -d sales_call_analyzer

# Restart
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile app up -d \
  --force-recreate backend celery-worker
```

### Docker volumes — what to back up

| Volume | Contents | Back up? |
|---|---|---|
| `postgres_data` | All call records, scores, users | **Yes — critical** |
| `minio_data` | Audio recordings | **Yes — critical** |
| `redis_data` | Task queue state | No — rebuilds itself |
| `ollama_data` | llama3.1:8b weights | No — re-pullable |
| `ml_models` | Whisper large-v3 weights | No — re-downloadable |
| `opensearch_data` | Search index | No — re-indexable from DB |

---

## 13. Cost Breakdown

### g5.2xlarge on-demand (us-east-1)

| Item | Monthly Cost |
|---|---|
| g5.2xlarge instance (24/7) | ~$875 |
| 100 GB gp3 EBS volume | ~$8 |
| Elastic IP (while attached) | Free |
| Data transfer out (estimate) | ~$5–20 |
| **Total** | **~$890–$905/mo** |

### Reduce costs

**1-year Reserved Instance (no upfront):** ~35% discount → ~$570/mo
- Buy via: EC2 → Reserved Instances → Purchase Reserved Instances
- Type: `g5.2xlarge`, Term: 1 year, Payment option: No Upfront

**Stop when not in use:**
```bash
# Stop instance (data persists on EBS, GPU memory cleared)
aws ec2 stop-instances --instance-ids i-XXXXXXXXXXXXXXXXX

# Start it again
aws ec2 start-instances --instance-ids i-XXXXXXXXXXXXXXXXX

# After start — bring services back up (Ollama re-loads model into GPU)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile app up -d
```

Stopping saves ~$1.21/hr. Elastic IP stays assigned. All Docker volumes persist.
