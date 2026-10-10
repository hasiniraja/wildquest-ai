# WildQuest AI — Evaluation Suite

## ⚠️ Eval / Training split

All prompts in `prompts.json` carry `"_split": "eval"`.
**Never include these prompts in training data.** The eval script enforces
this by filtering on `_split == "eval"` before running.

## Files

| File | Purpose |
|------|---------|
| `prompts.json` | 40 fixed `QuestRequest` prompts — all settings, durations, ages, energies |
| `eval.py` | Evaluation script — calls Ollama directly, no seed-quest fallback |
| `results/` | Per-model JSON output (git-ignored) |

## Running the eval

Prerequisites: Ollama running + model pulled.

```bash
# From the repo root
cd eval

# Basic run — all 40 prompts against gemma3:12b
../backend/.venv/bin/python3 eval.py --model gemma3:12b

# Quick smoke-test (first 5 prompts only)
../backend/.venv/bin/python3 eval.py --model gemma3:12b --max 5

# Compare a fine-tuned model
../backend/.venv/bin/python3 eval.py --model wildquest-ft:latest

# Fully greedy / deterministic (temperature=0)
../backend/.venv/bin/python3 eval.py --model gemma3:12b --temperature 0

# Single-shot, no retries (measures raw first-attempt quality)
../backend/.venv/bin/python3 eval.py --model gemma3:12b --retries 0
```

## Metrics explained

| Metric | What it measures |
|--------|----------------|
| JSON validity | % of responses that were parseable JSON |
| Schema validity | % that also matched the `Quest` Pydantic schema |
| Safety pass rate | % that passed all 6 unsafe-content regex rules |
| Duration compliance | % where `quest.duration_minutes` is within ±20% of the request |
| Title variety score | `unique_titles / total_titles` — low = repetitive |
| Mean / p95 latency | Measured from first HTTP byte to last, including retries |

## Expanding prompts

- Add new entries with `"_id"` starting from 41, `"_split": "eval"`
- Tricky combos to consider: `kids + low + 10 min`, `adults + high + 60 min`, single interest
- Never add entries with `"_split": "train"` to this file — keep a separate `train_prompts.json`
