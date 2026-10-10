
# 🌿 WildQuest AI

> **Hacktoberfest 2026 — "Touch Grass" Challenge**
> Get off the screen. Get outside. Complete a quest.

WildQuest AI generates short, personalized, safe outdoor quests (e.g. *"find 3 different leaf shapes in 15 minutes"*) using an open-weight **Gemma 3** model running locally via **Ollama**. No cloud. No paid APIs. No database server.

---

## Stack

| Layer | Technology |
|---|---|
| Inference | Ollama + `gemma3:4b` (local) |
| Backend | FastAPI + Pydantic (Python 3.11+) |
| Frontend | React + Vite + Tailwind CSS |
| Storage | Browser `localStorage` (quest journal) |
| Eval | Python scripts in `/eval` |

---

## Project Layout

```
wildquest-ai/
├── backend/          # FastAPI app, Pydantic schemas, quest logic
├── frontend/         # React + Vite + Tailwind UI
├── eval/             # Evaluation scripts for quest quality
├── .gitignore
├── README.md
└── PROGRESS.md       # Running log of what's done and what's next
```

---

## Prerequisites

### 1 — Install Ollama

```bash
# macOS (Apple Silicon) — recommended
brew install ollama

# Or download the macOS app directly:
# https://ollama.com/download/mac
```

### 2 — Pull the model

```bash
# Recommended: gemma3:4b  (8.2 GB — runs well on 16 GB Apple Silicon)
ollama pull gemma3:4b

# Lighter alternative if disk/RAM is tight:
# ollama pull gemma3:4b   (3.4 GB)
```

### 3 — Start the Ollama server

```bash
ollama serve
# Runs at http://localhost:11434 by default
```

---

## Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API will be at `http://localhost:8000`
Swagger docs at `http://localhost:8000/docs`

---

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

---

## Running Everything

Open **three** terminal tabs:

```bash
# Tab 1 — Ollama
ollama serve

# Tab 2 — Backend
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000

# Tab 3 — Frontend
cd frontend && npm run dev
```

---

## Architecture Overview

```
Browser (React)
    |  POST /quest/generate  { preferences }
    v
FastAPI backend
    |  Prompt template -> Ollama HTTP API
    v
Ollama (gemma3:4b, local)
    |  Raw JSON string
    v
Pydantic validation (up to 2 retries)
    |  Valid Quest schema  OR  seed quest fallback
    v
Browser <- response
    |
localStorage  (quest journal)
```

---

## Rules

- No paid APIs in the core app.
- Every quest is validated by a Pydantic schema; if invalid after 2 retries, a seed quest is returned so the app **never fails**.
- Journal data lives in browser `localStorage` — no backend persistence needed.
- UI is minimal during an active quest (the goal is to get you outside!).

---

