# PROGRESS — WildQuest AI

---

## ✅ Task 0 — Project Scaffold (completed 2026-10-10)

### What was done
- Created project directories: `/backend`, `/frontend`, `/eval`
- Added root `.gitignore` (Python, Node, OS, editor, secrets)
- Created `README.md` with full setup instructions, stack overview, and architecture diagram
- Created `PROGRESS.md` (this file)
- Checked hardware: Apple M5, 16 GB unified RAM, 315 GB free disk, Metal 4 GPU
- Checked current Ollama `gemma3` model tags (library page scraped live)
- **Recommended model: `gemma3:12b`** (8.2 GB) — best quality that fits comfortably in 16 GB unified memory; `gemma3:27b` (17 GB) would exceed RAM and cause swapping

### No app code written yet — scaffold only

---

## ✅ Task 1 — Backend Foundation (completed 2026-10-10)

### What was done
- `requirements.txt` — FastAPI, Uvicorn, Pydantic v2, httpx, pytest, pytest-asyncio
- `schemas.py` — `QuestRequest` (with interest allowlist validator), `Quest`, `QuestResponse`
- `prompts.py` — `SYSTEM_PROMPT` + `build_user_prompt()` + `build_retry_prompt()` (importable by eval)
- `validator.py` — `validate_quest()`: ±20% duration, non-empty safety note, 3–6 steps, six unsafe content pattern groups (eating plants, swimming, climbing, animals, trespassing, after dark) checked across ALL text fields with word-boundary regex
- `seed_quests.json` — 8 diverse, schema-valid seed quests as fallback
- `quest_generator.py` — async pipeline: strips markdown fences → parse JSON → Pydantic validate → business validate → retry up to 2×, feeding error back to model → seed fallback; logs only setting/duration/age_group
- `main.py` — FastAPI app, CORS for Vite dev server, `POST /api/quest`, `GET /api/health`
- `tests/test_validator.py` — **73 tests, 73 passed** covering malformed JSON, fenced JSON, duration bounds, safety note, step counts, and 5–8 phrasings per unsafe category across all text fields

---

## ⏭ Task 2 — Next Up: React + Vite + Tailwind Frontend

- [ ] Scaffold Vite + React + Tailwind project in /frontend
- [ ] Quest generation form (setting, duration, energy, interests, age group)
- [ ] Quest display with minimal "focus mode" UI during active quest
- [ ] Timer countdown during quest
- [ ] Quest journal stored in localStorage
- [ ] Health check banner if backend/Ollama is down

---

_Updated after each task._
