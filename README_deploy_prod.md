# Production Deployment

This guide deploys Madrina from prebuilt Docker images on a server where MySQL
is already installed and running directly on the host.

## Production Architecture

```text
Browser
  |
  | http://SERVER_IP:8080
  v
Frontend container (Nginx, port 8080 -> 80)
  |
  | backend:3000 -> host gateway
  v
Backend container (host network, port 3000)
  |
  | 127.0.0.1:3306
  v
MySQL installed on the server
```

The backend uses `network_mode: host`. This allows it to connect to the existing
MySQL server through `127.0.0.1` without changing MySQL's `bind-address`.

The frontend remains in Docker's default network. Its `backend` hostname is
mapped to the host gateway, where the backend listens on port `3000`.

## Server Layout

```text
/home/
├── madrina/
│   └── AsistenteWebTFGBackend/
│       └── user_data/             # Existing uploaded exams
└── madrina_AI/
    ├── docker-compose.prod.yml
    ├── .env.prod                  # Production secrets, never commit
    └── madrina_images.tar.gz
```

## Build And Export Images

Run these commands on the development machine from the project root.

### 1. Build both images

```bash
docker compose build backend frontend
```

### 2. Export the images

```bash
docker save madrina-backend:latest madrina-frontend:latest \
  | gzip > madrina_images.tar.gz
```

### 3. Copy deployment files to the server

```bash
ssh harioui@corex-tfg "mkdir -p /home/madrina_AI"

scp madrina_images.tar.gz \
  docker-compose.prod.yml \
  .env.prod.example \
  harioui@corex-tfg:/home/madrina_AI/
```

## First Deployment

Run these commands on the production server.

### 1. Open the deployment directory

```bash
cd /home/madrina_AI
```

### 2. Load the Docker images

```bash
sudo docker load < madrina_images.tar.gz
```

Expected images:

```text
madrina-backend:latest
madrina-frontend:latest
```

### 3. Create the production environment file

```bash
cp .env.prod.example .env.prod
nano .env.prod
chmod 600 .env.prod
```

Example:

```dotenv
USER_DATA_PATH=/home/madrina/AsistenteWebTFGBackend/user_data
DB_HOST=127.0.0.1
DB_USER=root
DB_PASSWORD=replace_with_the_real_mysql_password
DB_NAME=db_roadtomatricula
DB_PORT=3306
```

Important:

- `DB_HOST=127.0.0.1` works because the backend uses the host network.
- `DB_NAME` must exactly match the existing MySQL database name.
- `USER_DATA_PATH` must be an existing directory accessible by Docker.
- Do not commit or transfer a populated `.env.prod` through source control.

### 4. Validate the Compose configuration

For Docker Compose v2:

```bash
sudo docker compose \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  config
```

For Docker Compose v1:

```bash
sudo docker-compose \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  config
```

### 5. Start the application

Docker Compose v2:

```bash
sudo docker compose \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  up -d
```

Docker Compose v1:

```bash
sudo docker-compose \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  up -d
```

### 6. Check the containers

```bash
sudo docker-compose \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  ps

sudo docker-compose \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  logs --tail=100
```

The backend log should contain:

```text
open pool
SERVER
Encendido
```

## MySQL Verification

MySQL can continue listening only on localhost:

```bash
sudo ss -lntp | grep 3306
```

The expected address is:

```text
127.0.0.1:3306
```

Verify the credentials and database configured in `.env.prod`:

```bash
mysql \
  -h 127.0.0.1 \
  -P 3306 \
  -u root \
  -p \
  db_roadtomatricula \
  -e "SELECT 1;"
```

Replace the user and database with the values from `.env.prod` when necessary.

Test MySQL from the backend image using the same host network:

```bash
sudo docker run --rm \
  --network host \
  --env-file .env.prod \
  madrina-backend:latest \
  node -e '
const mysql = require("mysql2/promise");
mysql.createConnection({
  host: process.env.DB_HOST,
  port: Number(process.env.DB_PORT),
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME
}).then(async connection => {
  await connection.query("SELECT 1");
  console.log("MySQL connection successful");
  await connection.end();
}).catch(error => {
  console.error(error.code, error.message);
  process.exit(1);
});'
```

## Application Access

The frontend is exposed on port `8080`:

```text
http://SERVER_IP:8080
```

Find the server IP with:

```bash
hostname -I
```

If a firewall is enabled, allow only the required application port:

```bash
sudo ufw allow 8080/tcp
```

Port `3306` does not need to be opened because the backend and MySQL communicate
through the host network.

## Updating The Deployment

### Update both images

On the development machine:

```bash
docker compose build backend frontend
docker save madrina-backend:latest madrina-frontend:latest \
  | gzip > madrina_images.tar.gz
scp madrina_images.tar.gz harioui@corex-tfg:/home/madrina_AI/
```

On the server:

```bash
cd /home/madrina_AI
sudo docker load < madrina_images.tar.gz
sudo docker-compose \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  up -d --force-recreate
```

### Update only the backend

On the development machine:

```bash
docker compose build backend
docker save madrina-backend:latest | gzip > madrina-backend.tar.gz
scp madrina-backend.tar.gz harioui@corex-tfg:/home/madrina_AI/
```

On the server:

```bash
cd /home/madrina_AI
sudo docker load < madrina-backend.tar.gz
sudo docker-compose \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  up -d --force-recreate backend
```

### Update only the frontend

On the development machine:

```bash
docker compose build frontend
docker save madrina-frontend:latest | gzip > madrina-frontend.tar.gz
scp madrina-frontend.tar.gz harioui@corex-tfg:/home/madrina_AI/
```

On the server:

```bash
cd /home/madrina_AI
sudo docker load < madrina-frontend.tar.gz
sudo docker-compose \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  up -d --force-recreate frontend
```

## Operations

All commands below are executed from `/home/madrina_AI`.

```bash
# Container status
sudo docker-compose -f docker-compose.prod.yml --env-file .env.prod ps

# All logs
sudo docker-compose -f docker-compose.prod.yml --env-file .env.prod logs -f

# Backend logs
sudo docker-compose -f docker-compose.prod.yml --env-file .env.prod logs -f backend

# Frontend logs
sudo docker-compose -f docker-compose.prod.yml --env-file .env.prod logs -f frontend

# Restart the backend
sudo docker-compose -f docker-compose.prod.yml --env-file .env.prod restart backend

# Stop the application without deleting volumes
sudo docker-compose -f docker-compose.prod.yml --env-file .env.prod down

# Start it again
sudo docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

Do not use `down -v` unless the persistent Docker volumes must intentionally be
deleted.

## Troubleshooting

### Backend repeatedly restarts

Inspect its logs:

```bash
sudo docker logs --tail=100 madrina_backend
```

If the log reports a database connection failure, verify:

```bash
grep '^DB_' .env.prod
sudo ss -lntp | grep 3306
mysql -h 127.0.0.1 -u root -p -e "SHOW DATABASES;"
```

### Frontend returns `502 Bad Gateway`

Verify that the backend listens on the host port:

```bash
sudo ss -lntp | grep 3000
curl -I http://127.0.0.1:3000/
sudo docker logs --tail=100 madrina_frontend
```

The frontend Compose service must contain:

```yaml
extra_hosts:
  - "backend:host-gateway"
```

### Port 8080 is already in use

```bash
sudo ss -lntp | grep 8080
```

Stop the conflicting service or change the frontend mapping in
`docker-compose.prod.yml`, for example:

```yaml
ports:
  - "8081:80"
```

The application would then be available at `http://SERVER_IP:8081`.

## Use A Domain Name And HTTPS

This section replaces:

```text
http://corex-tfg.disca.upv.es:8080
```

with a public address such as:

```text
https://madrina-ai.es
```

The Docker frontend can remain on port `8080`. Nginx installed on the host will
listen on ports `80` and `443`, then forward requests to
`http://127.0.0.1:8080`.

### 1. Register or obtain the domain

Register `madrina-ai.es`, or request an institutional subdomain from the server
administrator. A public domain requires control of its DNS zone.

If the UPV network does not allow direct public access to ports `80` and `443`,
ask the network administrator to:

- associate the domain with `corex-tfg.disca.upv.es`;
- allow inbound HTTP and HTTPS traffic;
- configure the institutional reverse proxy when required.

### 2. Configure DNS

At the DNS provider, create an `A` record:

```text
Type:  A
Name:  @
Value: SERVER_PUBLIC_IP
TTL:   300
```

Optionally add `www`:

```text
Type:  CNAME
Name:  www
Value: madrina-ai.es
TTL:   300
```

If only the existing hostname is available, the provider may support:

```text
Type:  CNAME
Name:  @
Value: corex-tfg.disca.upv.es
```

Many DNS providers do not allow a CNAME at the zone root. In that case, use an
`A` record with the server's public IP.

Verify DNS propagation:

```bash
dig +short madrina-ai.es
dig +short www.madrina-ai.es
```

The returned IP must point to the production server or its institutional reverse
proxy.

### 3. Install Nginx on the server

```bash
sudo apt update
sudo apt install nginx
```

Confirm that the Docker frontend is available locally:

```bash
curl -I http://127.0.0.1:8080
```

### 4. Configure the host reverse proxy

Create `/etc/nginx/sites-available/madrina-ai`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name madrina-ai.es www.madrina-ai.es;

    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

Enable and validate it:

```bash
sudo ln -s /etc/nginx/sites-available/madrina-ai \
  /etc/nginx/sites-enabled/madrina-ai

sudo nginx -t
sudo systemctl reload nginx
```

The application should now respond on:

```text
http://madrina-ai.es
```

### 5. Enable HTTPS with Let's Encrypt

DNS must already resolve to the server, and ports `80` and `443` must be
reachable from the Internet.

```bash
sudo apt install certbot python3-certbot-nginx

sudo certbot --nginx \
  -d madrina-ai.es \
  -d www.madrina-ai.es
```

Choose the option that redirects HTTP traffic to HTTPS.

Verify certificate renewal:

```bash
sudo certbot renew --dry-run
sudo systemctl status certbot.timer
```

The final application URL is:

```text
https://madrina-ai.es
```

### 6. Firewall rules

Allow only the public web ports:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

Port `8080` should ideally remain accessible only locally. Change the frontend
port mapping in `docker-compose.prod.yml` from:

```yaml
ports:
  - "8080:80"
```

to:

```yaml
ports:
  - "127.0.0.1:8080:80"
```

Then recreate only the frontend:

```bash
sudo docker-compose \
  -f docker-compose.prod.yml \
  --env-file .env.prod \
  up -d --force-recreate frontend
```

This prevents direct external access to `http://SERVER_IP:8080`; users must use
the HTTPS domain through Nginx.

## Local Network Access With Apache

This alternative exposes the application as `http://madrina-ai.es` to users on
the same local network. It does not require public DNS or a public domain
registration.

The Docker frontend must already be available on:

```text
http://127.0.0.1:8080
```

### 1. Install and prepare Apache

```bash
sudo apt update
sudo apt install apache2

sudo a2enmod proxy proxy_http headers
sudo systemctl restart apache2
```

Apache and Nginx cannot both listen on port `80` at the same time. If the Nginx
configuration from the previous section is enabled, disable or stop it before
using Apache:

```bash
sudo systemctl disable --now nginx
```

### 2. Create the Apache virtual host

Create the configuration file:

```bash
sudo nano /etc/apache2/sites-available/madrina-ai.conf
```

Add:

```apache
<VirtualHost *:80>
    ServerName madrina-ai.es
    ServerAlias www.madrina-ai.es

    ProxyPreserveHost On
    ProxyRequests Off

    LimitRequestBody 524288000

    ProxyPass / http://127.0.0.1:8080/
    ProxyPassReverse / http://127.0.0.1:8080/

    RequestHeader set X-Forwarded-Proto "http"
    RequestHeader set X-Forwarded-Port "80"

    ErrorLog ${APACHE_LOG_DIR}/madrina-ai-error.log
    CustomLog ${APACHE_LOG_DIR}/madrina-ai-access.log combined
</VirtualHost>
```

Save the file with `Ctrl+O`, press `Enter`, then exit with `Ctrl+X`.

### 3. Enable and validate the site

```bash
sudo a2ensite madrina-ai.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

The configuration test must return:

```text
Syntax OK
```

Test the virtual host from the server:

```bash
curl -I -H "Host: madrina-ai.es" http://127.0.0.1
```

The expected response is:

```text
HTTP/1.1 200 OK
```

### 4. Configure client name resolution

On every Linux or macOS computer that needs access, edit `/etc/hosts`:

```bash
sudo nano /etc/hosts
```

Add:

```text
158.42.180.127 madrina-ai.es www.madrina-ai.es
```

On Windows, edit this file as Administrator:

```text
C:\Windows\System32\drivers\etc\hosts
```

Add the same entry:

```text
158.42.180.127 madrina-ai.es www.madrina-ai.es
```

Replace `158.42.180.127` if the server's local network IP changes. Verify the
server address with:

```bash
hostname -I
```

Users can then open:

```text
http://madrina-ai.es
```

For many client computers, configure the same hostname in the organization's
local DNS server instead of editing every `hosts` file.
