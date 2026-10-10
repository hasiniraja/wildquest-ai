#!/usr/bin/env python3
"""
WildQuest AI — Quest Quality Evaluator
=======================================
Runs a fixed set of QuestRequests through the raw Ollama model (NO fallback)
and measures: JSON validity, schema validity, safety pass rate, duration
compliance, title variety, and latency (mean + p95).

Usage:
    python eval.py --model gemma3:12b
    python eval.py --model gemma3:4b --prompts prompts.json --max 20
    python eval.py --model my-finetuned-model --temperature 0

Outputs:
    results/<model_slug>.json   — full machine-readable results
    stdout                      — markdown table ready to paste
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

# ── Path setup ────────────────────────────────────────────────────────────────
# Allow running from /eval OR from the repo root.
EVAL_DIR    = Path(__file__).parent.resolve()
BACKEND_DIR = EVAL_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from prompts import SYSTEM_PROMPT, build_retry_prompt, build_user_prompt
from schemas import Quest, QuestRequest
from validator import validate_quest

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,   # suppress INFO noise from backend modules
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("eval")


# ── Constants ─────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_PROMPTS = EVAL_DIR / "prompts.json"
RESULTS_DIR     = EVAL_DIR / "results"

# Metadata keys in prompts.json that are NOT QuestRequest fields
_EVAL_META_KEYS = {"_id", "_split", "_note"}


# ── Low-level Ollama call (no fallback) ───────────────────────────────────────

async def _call_ollama(
    client: httpx.AsyncClient,
    model: str,
    request: QuestRequest,
    temperature: float,
    timeout: float,
    is_retry: bool = False,
    last_error: str = "",
) -> tuple[str | None, float]:
    """Single Ollama call. Returns (raw_text, latency_ms). raw_text=None on error."""
    user_msg = (
        build_retry_prompt(request, last_error)
        if is_retry
        else build_user_prompt(request)
    )

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
            "seed": 42,          # determinism — honoured by most Ollama builds
        },
    }

    t0 = time.monotonic()
    try:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"]
        return raw, (time.monotonic() - t0) * 1000
    except httpx.HTTPError as exc:
        logger.warning("Ollama HTTP error: %s", exc)
        return None, (time.monotonic() - t0) * 1000


# ── JSON / schema helpers ─────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```$", "", text)
    return text.strip()


def _try_parse(raw: str) -> tuple[dict | None, Quest | None, str]:
    """Returns (parsed_dict, Quest|None, failure_stage). failure_stage: '' | 'json' | 'schema'"""
    cleaned = _strip_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None, None, "json"
    try:
        quest = Quest.model_validate(data)
        return data, quest, ""
    except Exception:  # noqa: BLE001
        return data, None, "schema"


# ── Per-prompt evaluation ─────────────────────────────────────────────────────

async def evaluate_prompt(
    client: httpx.AsyncClient,
    prompt_entry: dict,
    model: str,
    temperature: float,
    timeout: float,
    max_retries: int,
) -> dict:
    """
    Run one QuestRequest through the model.
    NEVER falls back to seed quests — we measure raw model quality.
    """
    req_data = {k: v for k, v in prompt_entry.items() if k not in _EVAL_META_KEYS}
    request  = QuestRequest(**req_data)

    result: dict[str, Any] = {
        "prompt_id":        prompt_entry.get("_id"),
        "request":          req_data,
        "json_valid":       False,
        "schema_valid":     False,
        "safety_pass":      False,
        "duration_ok":      False,
        "title":            None,
        "attempts":         0,
        "total_latency_ms": 0.0,
        "failure_stage":    "not_attempted",
        "raw_response":     None,
    }

    last_error    = ""
    total_latency = 0.0

    for attempt in range(max_retries + 1):
        result["attempts"] = attempt + 1
        is_retry = attempt > 0

        raw, lat = await _call_ollama(
            client, model, request, temperature, timeout,
            is_retry=is_retry, last_error=last_error,
        )
        total_latency += lat

        if raw is None:
            result["failure_stage"]    = "ollama_unreachable"
            result["total_latency_ms"] = total_latency
            return result

        _data, quest, fail_stage = _try_parse(raw)

        if fail_stage == "json":
            last_error             = "JSON parse error — output was not valid JSON"
            result["failure_stage"] = "json"
            continue

        result["json_valid"] = True

        if fail_stage == "schema":
            last_error             = "Schema validation error — required fields missing or wrong types"
            result["failure_stage"] = "schema"
            continue

        result["schema_valid"] = True
        result["title"]        = quest.title

        # Business-rule safety check
        val_err = validate_quest(quest, request)
        if val_err:
            last_error             = val_err
            result["failure_stage"] = "safety"
            continue

        result["safety_pass"] = True

        # Duration compliance: ±20%
        lo = round(request.duration_minutes * 0.8)
        hi = round(request.duration_minutes * 1.2)
        result["duration_ok"]    = lo <= quest.duration_minutes <= hi
        result["failure_stage"]  = "" if result["duration_ok"] else "duration"
        result["raw_response"]   = raw
        break   # success

    result["total_latency_ms"] = total_latency
    return result


# ── Aggregate metrics ─────────────────────────────────────────────────────────

def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s   = sorted(values)
    idx = max(0, int(len(s) * 0.95) - 1)
    return s[idx]


def compute_metrics(results: list[dict], n_prompts: int) -> dict:
    n = n_prompts

    n_json     = sum(1 for r in results if r["json_valid"])
    n_schema   = sum(1 for r in results if r["schema_valid"])
    n_safety   = sum(1 for r in results if r["safety_pass"])
    n_duration = sum(1 for r in results if r["duration_ok"])

    latencies  = [r["total_latency_ms"] for r in results if r["schema_valid"]]
    mean_lat   = sum(latencies) / len(latencies) if latencies else 0.0
    p95_lat    = _p95(latencies)

    titles        = [r["title"] for r in results if r["title"]]
    unique_titles = len({t.lower().strip() for t in titles})
    variety_score = unique_titles / len(titles) if titles else 0.0

    failure_breakdown: dict[str, int] = {}
    for r in results:
        stage = r["failure_stage"] or "success"
        failure_breakdown[stage] = failure_breakdown.get(stage, 0) + 1

    return {
        "n_prompts":         n,
        "json_valid_rate":   n_json   / n,
        "schema_valid_rate": n_schema / n,
        "safety_pass_rate":  n_safety / n,
        "duration_ok_rate":  n_duration / n,
        "variety_score":     variety_score,
        "mean_latency_ms":   mean_lat,
        "p95_latency_ms":    p95_lat,
        "failure_breakdown": failure_breakdown,
    }


# ── Markdown table printer ────────────────────────────────────────────────────

def print_markdown_table(model: str, metrics: dict) -> None:
    def pct(v: float) -> str: return f"{v * 100:.1f}%"
    def ms_(v: float) -> str: return f"{v:.0f} ms"

    rows = [
        ("Model",               model),
        ("Prompts evaluated",   str(metrics["n_prompts"])),
        ("JSON validity",       pct(metrics["json_valid_rate"])),
        ("Schema validity",     pct(metrics["schema_valid_rate"])),
        ("Safety pass rate",    pct(metrics["safety_pass_rate"])),
        ("Duration compliance", pct(metrics["duration_ok_rate"])),
        ("Title variety score", pct(metrics["variety_score"])),
        ("Mean latency",        ms_(metrics["mean_latency_ms"])),
        ("p95 latency",         ms_(metrics["p95_latency_ms"])),
    ]

    col_w = max(len(r[0]) for r in rows) + 2
    val_w = max(len(r[1]) for r in rows) + 2

    print()
    print("## Quest Quality — Evaluation Results")
    print()
    print(f"| {'Metric':<{col_w}} | {'Value':<{val_w}} |")
    print(f"| {'-' * col_w} | {'-' * val_w} |")
    for label, value in rows:
        print(f"| {label:<{col_w}} | {value:<{val_w}} |")
    print()

    bd = metrics["failure_breakdown"]
    if bd:
        print("### Failure breakdown")
        print()
        print(f"| {'Stage':<22} | {'Count':>6} |")
        print(f"| {'-'*22} | {'-'*6} |")
        for stage, count in sorted(bd.items(), key=lambda x: -x[1]):
            print(f"| {stage:<22} | {count:>6} |")
        print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="WildQuest AI quest-quality evaluator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--model",       "-m", default="gemma3:12b",      help="Ollama model tag")
    p.add_argument("--prompts",     "-p", type=Path, default=DEFAULT_PROMPTS, help="prompts.json path")
    p.add_argument("--max",         "-n", type=int,  default=None,    help="Max prompts to run")
    p.add_argument("--tag",               default=None,               help="Extra label appended to results filename (e.g. 'strict-v2')")
    p.add_argument("--temperature", "-t", type=float, default=0.2,    help="Sampling temperature (0=greedy)")
    p.add_argument("--retries",           type=int,  default=1,       help="Max retries per prompt on schema error")
    p.add_argument("--timeout",           type=float, default=180.0,  help="Per-call Ollama timeout (s)")
    p.add_argument("--concurrency", "-c", type=int,  default=1,       help="Concurrent Ollama requests")
    p.add_argument("--verbose",     "-v", action="store_true",        help="Extra per-prompt output")
    return p


async def main() -> None:
    args = _build_parser().parse_args()

    # ── Load & filter prompts ──────────────────────────────────────────────────
    prompts_path = Path(args.prompts)
    if not prompts_path.exists():
        print(f"ERROR: prompts file not found: {prompts_path}", file=sys.stderr)
        sys.exit(1)

    with open(prompts_path, encoding="utf-8") as fh:  # noqa: ASYNC230
        all_prompts = json.load(fh)

    # _split='eval' guard prevents accidentally running training data
    eval_prompts = [p for p in all_prompts if p.get("_split") == "eval"]
    if not eval_prompts:
        print("WARNING: no _split='eval' prompts found — running all.", file=sys.stderr)
        eval_prompts = all_prompts

    if args.max:
        eval_prompts = eval_prompts[: args.max]

    n          = len(eval_prompts)
    model_slug = re.sub(r"[^a-zA-Z0-9_\-.]", "_", args.model)
    if args.tag:
        model_slug = f"{model_slug}_{re.sub(r'[^a-zA-Z0-9_-]', '_', args.tag)}"

    print("\n🌿 WildQuest Evaluator")
    print(f"   model       : {args.model}")
    print(f"   prompts     : {n}  (from {prompts_path.name})")
    print(f"   temperature : {args.temperature}")
    print(f"   retries     : {args.retries} per prompt")
    print(f"   output      : {RESULTS_DIR / (model_slug + '.json')}")
    print()

    # ── Preflight: check Ollama + model ───────────────────────────────────────
    print("Checking Ollama...", end=" ", flush=True)
    try:
        async with httpx.AsyncClient(timeout=10.0) as probe:
            r = await probe.get(f"{OLLAMA_BASE_URL}/api/tags")
            r.raise_for_status()
            available = [m["name"] for m in r.json().get("models", [])]
        if args.model not in available:
            print(f"\n⚠️  Model '{args.model}' not pulled.")
            print(f"   Available : {', '.join(available) or 'none'}")
            print(f"   Run       : ollama pull {args.model}")
            sys.exit(1)
        print(f"OK  ({len(available)} model(s) available)")
    except httpx.HTTPError as exc:
        print(f"\n❌ Ollama unreachable at {OLLAMA_BASE_URL}")
        print(f"   Error: {exc}")
        print("   Start: ollama serve")
        sys.exit(1)

    # ── Run evaluation ────────────────────────────────────────────────────────
    sem        = asyncio.Semaphore(args.concurrency)
    eval_start = time.monotonic()

    async with httpx.AsyncClient(timeout=args.timeout) as client:

        async def run_one(entry: dict, idx: int) -> dict:
            async with sem:
                # Progress line
                interests_str = ",".join(entry["interests"])
                print(
                    f"[{idx+1:2d}/{n}] id={entry.get('_id','?')!s:>3}  "
                    f"{entry['setting']:<9} {entry['duration_minutes']:>3}min  "
                    f"{entry['energy_level']:<7} {entry['age_group']:<7} "
                    f"{interests_str:<25} ... ",
                    end="", flush=True,
                )
                res = await evaluate_prompt(
                    client, entry, args.model,
                    args.temperature, args.timeout, args.retries,
                )
                # Status glyph
                if res["safety_pass"] and res["duration_ok"]:
                    glyph = "✅"
                elif res["schema_valid"]:
                    glyph = f"⚠️  {res['failure_stage']}"
                elif res["json_valid"]:
                    glyph = "❌ schema"
                else:
                    glyph = f"❌ {res['failure_stage']}"

                print(f"{glyph}  ({res['total_latency_ms']:.0f} ms)")
                return res

        tasks   = [run_one(p, i) for i, p in enumerate(eval_prompts)]
        results = list(await asyncio.gather(*tasks))

    elapsed = time.monotonic() - eval_start
    print(f"\nDone — {n} prompts in {elapsed:.1f}s")

    # ── Metrics & output ──────────────────────────────────────────────────────
    metrics = compute_metrics(results, n)
    print_markdown_table(args.model, metrics)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{model_slug}.json"
    output   = {
        "model":       args.model,
        "temperature": args.temperature,
        "retries":     args.retries,
        "run_at":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_s":   round(elapsed, 1),
        "metrics":     metrics,
        "results":     results,
    }
    with open(out_path, "w", encoding="utf-8") as fh:  # noqa: ASYNC230
        json.dump(output, fh, indent=2)
    print(f"Saved → {out_path}\n")


if __name__ == "__main__":
    asyncio.run(main())
