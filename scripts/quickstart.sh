#!/usr/bin/env bash
set -euo pipefail

# 1. Pull models used by the MVP
ollama pull qwen3:8b
ollama pull nomic-embed-text

# 2. Install deps
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Run the API
cp -n .env.example .env || true
uvicorn app.main:app --reload --port 8000
