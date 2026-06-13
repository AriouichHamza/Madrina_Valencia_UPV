#!/usr/bin/env bash
set -euo pipefail

# Place this script at the project root.
# It will start the backend in the background, then the frontend.
# It supports either ./AsistenteWebTFGBackend or ./bakend as the backend folder name.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -d "$ROOT_DIR/AsistenteWebTFGBackend" ]; then
  BACKEND_DIR="$ROOT_DIR/AsistenteWebTFGBackend"
elif [ -d "$ROOT_DIR/AsistenteWebTFGBackend" ]; then
  BACKEND_DIR="$ROOT_DIR/AsistenteWebTFGBackend"
else
  echo "Erreur: dossier backend/bakend introuvable à côté du script."
  exit 1
fi

FRONTEND_DIR="$ROOT_DIR/AsistenteWebTFG"

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "Erreur: dossier frontend introuvable à côté du script."
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Erreur: node n'est pas installé ou n'est pas dans le PATH."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Erreur: npm n'est pas installé ou n'est pas dans le PATH."
  exit 1
fi

cleanup() {
  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    echo
    echo "Arrêt du backend..."
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

echo "Lancement du backend depuis: $BACKEND_DIR"
(
  cd "$BACKEND_DIR"
  node ./bin/www
) &
BACKEND_PID=$!

# Petite pause pour laisser le backend démarrer.
sleep 2

echo "Lancement du frontend depuis: $FRONTEND_DIR"
cd "$FRONTEND_DIR"
npm start
