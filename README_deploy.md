# Deployment — Madrina / AsistenteTFG

## Architecture overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          Browser                                │
│              http://localhost:4200                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / WebSocket
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Container: frontend  (Nginx :80 → exposed :4200)             │
│  Angular 13 built as static files                             │
│  • SPA routing handled by nginx (try_files → index.html)      │
│  • /api/, /login/, /socket.io/ → proxied to backend:3000      │
└───────────────────────────┬───────────────────────────────────┘
                            │ HTTP / Socket.IO (Docker network)
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Container: backend  (Node.js 18 :3000 → exposed :3000)       │
│  Express + Socket.IO                                          │
│                                                               │
│  When processing an exam:                                     │
│    └─ spawn() → /app/.venv/bin/python main.py                 │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Python AI Module (same container)                      │  │
│  │  PyTorch CPU · OpenCV · PyPDF2 · Levenshtein            │  │
│  │  • detects handwritten DNI digits (SmallCNN)            │  │
│  │  • detects grades (exam_model)                          │  │
│  │  • streams results line by line on stdout               │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────┬───────────────────────────────────┘
                            │ MySQL TCP :3306
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Container: db  (MySQL 8.0)                                   │
│  Database: MargotDB                                           │
│  Auto-initialised from MargotDB.sql on first start            │
│  Data persisted in Docker volume  db_data                     │
└───────────────────────────────────────────────────────────────┘
```

### Docker files

| File | Role |
|---|---|
| `AsistenteWebTFG/Dockerfile` | Build Angular (Node 16) + serve with Nginx |
| `AsistenteWebTFG/nginx.conf` | Nginx config: SPA routing + API/Socket proxy |
| `Dockerfile.backend` | Node backend + Python venv + AI module |
| `docker-compose.yml` | Orchestrates the 3 services + volumes |

---

## Prerequisites

- **Docker** ≥ 24 — `docker --version`
- **Docker Compose plugin** — `docker compose version`
  - If missing: `curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 -o ~/.docker/cli-plugins/docker-compose && chmod +x ~/.docker/cli-plugins/docker-compose`
- Ports **3000**, **4200**, **3306** available on the host machine

---

## Running with Docker (recommended)

### First start (full build ~10 min)

```bash
docker compose up --build
```

> PyTorch CPU is ~800 MB. The backend build is slow on first run;
> Docker caches all layers for subsequent starts.

### Subsequent starts (fast)

```bash
docker compose up
```

### Background mode

```bash
docker compose up -d
docker compose logs -f          # stream logs
```

### Stop

```bash
docker compose down             # stop and remove containers
docker compose down -v          # + remove volumes (resets the database)
```

### Check everything is running

```bash
docker compose ps
```

Expected output:

```
NAME                STATUS          PORTS
madrina_db          Up (healthy)    0.0.0.0:3306->3306/tcp
madrina_backend     Up              0.0.0.0:3000->3000/tcp
madrina_frontend    Up              0.0.0.0:4200->80/tcp
```

**Access:** `http://localhost:4200`

---

## Running without Docker (local development)

### 1. MySQL database

```bash
mysql -u root -p < MargotDB.sql
```

Configure `.env` in `AsistenteWebTFGBackend/`:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=<your_password>
DB_NAME=MargotDB
DB_PORT=3306
AI_PYTHON_BIN=../.venv/bin/python
AI_MODULE_PATH=../AsistenteWebTFGBackendAIModule/main.py
AI_MODULE_USER_DATA_ROOT=./user_data
```

### 2. Node.js backend

```bash
cd AsistenteWebTFGBackend
npm install
node ./bin/www
# → http://localhost:3000
```

### 3. Python AI module (venv)

The module is launched automatically by the backend via `spawn()`.
To set it up manually:

```bash
python3 -m venv .venv
.venv/bin/pip install torch torchvision PyPDF2 python-Levenshtein numpy opencv-python Pillow
```

> These paths can be changed with `AI_PYTHON_BIN`, `AI_MODULE_PATH` and
> `AI_MODULE_USER_DATA_ROOT`.

### 4. Angular frontend

```bash
cd AsistenteWebTFG
npm install --legacy-peer-deps
npm start
# → http://localhost:4200
```

> `--legacy-peer-deps` is required due to a peer dependency conflict
> between `ngx-socket-io ^4.1.0` and Angular 13 under npm v8+.

---

## Backend environment variables

| Variable | Docker default | Description |
|---|---|---|
| `DB_HOST` | `db` | MySQL host (Docker service name) |
| `DB_USER` | `root` | MySQL user |
| `DB_PASSWORD` | `MargotDB_2024` | MySQL password |
| `DB_NAME` | `MargotDB` | Database name |
| `DB_PORT` | `3306` | MySQL port |
| `PORT` | `3000` | Express listening port |
| `AI_PYTHON_BIN` | `/app/.venv/bin/python` | Python executable used by Node.js |
| `AI_MODULE_PATH` | `/app/AsistenteWebTFGBackendAIModule/main.py` | AI entry point |
| `AI_MODULE_USER_DATA_ROOT` | `/app/AsistenteWebTFGBackend/user_data` | Uploaded PDF root |
| `AI_PDF_WORKERS` | `2` | Concurrent Poppler rendering jobs |
| `AI_DETECTION_WORKERS` | `2` | Concurrent first-page detection jobs |

---

## Connecting to an external database

To use an existing remote MySQL server instead of the local Docker container:

**1.** Comment out the entire `db` block in `docker-compose.yml`.

**2.** Update the backend environment variables:
```yaml
environment:
  DB_HOST: my-server.example.com   # remote IP or domain
  DB_USER: my_user
  DB_PASSWORD: my_password
  DB_NAME: my_database
  DB_PORT: 3306
```

**3.** Remove the `depends_on` block from the backend service (no local `db` anymore).

**4.** Make sure the remote MySQL server accepts connections from your machine (grant user from `%` or the specific IP, open port 3306 in the server firewall).

---

## GPU support (optional — NVIDIA)

By default the AI module runs on **CPU**. To enable GPU:

**1. Update `Dockerfile.backend`** — replace the torch install line:

```dockerfile
RUN /app/.venv/bin/pip install torch==2.11.0 torchvision==0.26.0 \
    --extra-index-url https://download.pytorch.org/whl/cu126
```

**2. Add to `docker-compose.yml`** under the `backend` service:

```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

**3.** Install `nvidia-container-toolkit` on the host machine.

---

## Persistent volumes

| Docker volume | Contents |
|---|---|
| `db_data` | MySQL data |
| `backend_public` | Generated PDF/ZIP files |
| `backend_user_data` | PDFs uploaded by users |

To fully reset (including the database):

```bash
docker compose down -v
docker compose up --build
```

---

## Troubleshooting

| Issue | Likely cause | Fix |
|---|---|---|
| `backend` keeps restarting | MySQL not ready yet | Wait for the healthcheck (`service_healthy`) |
| `npm ci` fails on frontend | ngx-socket-io peer dep conflict | `--legacy-peer-deps` already applied in the Dockerfile |
| Port 3306 already in use | Local MySQL running on host | `sudo systemctl stop mysql` or remove port mapping in compose |
| AI module not found | Invalid AI path variables | Check `AI_PYTHON_BIN`, `AI_MODULE_PATH` and `AI_MODULE_USER_DATA_ROOT` |
| AI stops without results | No first page detected or invalid PDF | Read `docker compose logs backend`; the Python error is forwarded to the UI |
| MySQL reports `Unable to lock ./ibdata1 error: 11` | An old `mysqld` process still owns the volume, often after mixing Snap Docker and system Docker | Keep only one Docker installation active, stop the orphan process, then restart only the `db` service |

Do not run the Snap and system installations of Docker at the same time. Check
the active data root with:

```bash
docker info --format '{{.DockerRootDir}}'
ps -ef | grep '[d]ockerd'
```

If the data root starts with `/var/snap/docker/`, keep the Snap service and
disable the duplicate system daemon:

```bash
sudo systemctl stop docker.service docker.socket
sudo systemctl disable docker.service docker.socket
sudo systemctl mask docker.service docker.socket
sudo snap restart docker
```

Never delete `ibdata1` and do not use `docker compose down -v` to solve a lock;
both actions can destroy the persisted database.
