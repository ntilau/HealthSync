#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -f requirements.txt ]]; then
  echo "requirements.txt not found in $ROOT_DIR"
  exit 1
fi

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ ! -d .venv ]]; then
    echo "Creating virtual environment in .venv..."
    python3 -m venv .venv
  fi
  echo "Activating virtual environment..."
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

echo "Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Setup complete. Activate with: source .venv/bin/activate"
