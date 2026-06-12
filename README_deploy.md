# Déploiement — Madrina / AsistenteTFG

## Architecture globale

```
┌─────────────────────────────────────────────────────────────────┐
│                        Navigateur                               │
│              http://localhost:4200                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / WebSocket
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Container : frontend  (Nginx :80 → exposé :4200)             │
│  Angular 13 buildé en statique                                │
│  • SPA routing géré par nginx (try_files → index.html)        │
│  • /api/, /login/, /socket.io/ → proxy vers backend:3000      │
└───────────────────────────┬───────────────────────────────────┘
                            │ HTTP / Socket.IO (réseau Docker)
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Container : backend  (Node.js 18 :3000 → exposé :3000)       │
│  Express + Socket.IO                                          │
│                                                               │
│  Lors du traitement d'un examen :                             │
│    └─ spawn() → /app/.venv/bin/python main.py                 │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Module IA Python (même container)                      │  │
│  │  PyTorch CPU · OpenCV · PyPDF2 · Levenshtein            │  │
│  │  • détecte les DNI manuscrits (CNN SmallCNN)            │  │
│  │  • détecte les notes (exam_model)                       │  │
│  │  • émet les résultats ligne par ligne sur stdout        │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────┬───────────────────────────────────┘
                            │ MySQL TCP :3306
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Container : db  (MySQL 8.0 → exposé :3306)                   │
│  Base : db_roadtomatricula                                    │
│  Init automatique via MargotDB.sql au premier démarrage       │
│  Données persistées dans le volume Docker  db_data            │
└───────────────────────────────────────────────────────────────┘
```

### Fichiers créés pour Docker

| Fichier | Rôle |
|---|---|
| `AsistenteWebTFG/Dockerfile` | Build Angular (Node 16) + serve Nginx |
| `AsistenteWebTFG/nginx.conf` | Config Nginx : SPA + proxy API/Socket |
| `Dockerfile.backend` | Backend Node + venv Python + module IA |
| `docker-compose.yml` | Orchestre les 3 services + volumes |

---

## Prérequis

- **Docker** ≥ 24 — `docker --version`
- **Docker Compose plugin** — `docker compose version`
  - Si absent : `curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 -o ~/.docker/cli-plugins/docker-compose && chmod +x ~/.docker/cli-plugins/docker-compose`
- Ports **3000**, **4200**, **3306** libres sur la machine hôte

---

## Lancer l'application (Docker — recommandé)

### Premier démarrage (build complet ~10 min)

```bash
docker compose up --build
```

> PyTorch CPU fait ~800 Mo. Le build du backend est long la première fois ;
> Docker met tout en cache pour les lancements suivants.

### Démarrages suivants (rapide)

```bash
docker compose up
```

### En arrière-plan

```bash
docker compose up -d
docker compose logs -f          # suivre les logs
```

### Arrêter

```bash
docker compose down             # arrête et supprime les conteneurs
docker compose down -v          # + supprime les volumes (reset BDD)
```

### Vérifier que tout tourne

```bash
docker compose ps
```

Résultat attendu :

```
NAME                STATUS          PORTS
madrina_db          Up (healthy)    0.0.0.0:3306->3306/tcp
madrina_backend     Up              0.0.0.0:3000->3000/tcp
madrina_frontend    Up              0.0.0.0:4200->80/tcp
```

**Accès :** `http://localhost:4200`

---

## Lancer sans Docker (développement local)

### 1. Base de données MySQL

```bash
mysql -u root -p < MargotDB.sql
```

Configurer `.env` dans `AsistenteWebTFGBackend/` :

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=<ton_mot_de_passe>
DB_NAME=db_roadtomatricula
DB_PORT=3306
```

### 2. Backend Node.js

```bash
cd AsistenteWebTFGBackend
npm install
node ./bin/www
# → http://localhost:3000
```

### 3. Module IA Python (venv)

Le module est lancé automatiquement par le backend via `spawn()`.
Pour le préparer manuellement :

```bash
python3 -m venv .venv
.venv/bin/pip install torch torchvision PyPDF2 python-Levenshtein numpy opencv-python Pillow
```

> Le backend cherche `.venv` à `../` depuis `AsistenteWebTFGBackend/`,
> donc placer le venv à la racine du projet.

### 4. Frontend Angular

```bash
cd AsistenteWebTFG
npm install --legacy-peer-deps
npm start
# → http://localhost:4200
```

> `--legacy-peer-deps` est nécessaire à cause du conflit de peer deps
> entre `ngx-socket-io ^4.1.0` et Angular 13 sous npm v8+.

---

## Variables d'environnement (backend)

| Variable | Défaut Docker | Description |
|---|---|---|
| `DB_HOST` | `db` | Hôte MySQL (nom du service Docker) |
| `DB_USER` | `root` | Utilisateur MySQL |
| `DB_PASSWORD` | `MargotDB_2024` | Mot de passe MySQL |
| `DB_NAME` | `db_roadtomatricula` | Nom de la base |
| `DB_PORT` | `3306` | Port MySQL |
| `PORT` | `3000` | Port d'écoute Express |

---

## GPU (optionnel — NVIDIA)

Par défaut, le module IA tourne sur **CPU**. Pour activer le GPU :

**1. Modifier `Dockerfile.backend`** — remplacer la ligne torch :

```dockerfile
RUN /app/.venv/bin/pip install torch==2.1.0 torchvision==0.16.0 \
    --index-url https://download.pytorch.org/whl/cu121
```

**2. Ajouter dans `docker-compose.yml`** sous le service `backend` :

```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

**3.** Installer `nvidia-container-toolkit` sur l'hôte.

---

## Volumes persistants

| Volume Docker | Contenu |
|---|---|
| `db_data` | Données MySQL |
| `backend_public` | Fichiers PDF/ZIP générés |
| `backend_user_data` | PDFs uploadés par les utilisateurs |

Pour réinitialiser complètement (y compris la BDD) :

```bash
docker compose down -v
docker compose up --build
```

---

## Dépannage rapide

| Problème | Cause probable | Solution |
|---|---|---|
| `backend` redémarre en boucle | MySQL pas encore prêt | Attendre le healthcheck (`service_healthy`) |
| `npm ci` échoue sur le frontend | Conflit peer deps ngx-socket-io | `--legacy-peer-deps` déjà appliqué dans le Dockerfile |
| Port 3306 déjà utilisé | MySQL local qui tourne | `sudo systemctl stop mysql` ou changer le port dans compose |
| Module IA introuvable | Chemin `.venv` incorrect | Vérifier que le venv est à `/app/.venv` dans le container |
