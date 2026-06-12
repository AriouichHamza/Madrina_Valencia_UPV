# ── Stage 1 : build Angular ──────────────────────────────────────────────────
FROM node:16-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci --legacy-peer-deps && npm install --legacy-peer-deps @angular/cli@13

COPY . .
RUN ./node_modules/.bin/ng build --configuration production

# ── Stage 2 : Nginx pour servir le SPA ───────────────────────────────────────
FROM nginx:1.25-alpine

COPY --from=build /app/dist/frontend /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80