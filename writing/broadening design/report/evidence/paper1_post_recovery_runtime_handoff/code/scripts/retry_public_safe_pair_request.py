#!/usr/bin/env python3
"""Retry one invalid v2 request while preserving every attempt as raw evidence."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / ".codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-v2-20260908T111917Z"
SOURCE = RUN / "raw/a/safe-pair_341.a.json"
MAX_RETRIES = 100


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    prompt = source["user_prompt_text"]
    message = prompt
    outdir = RUN / "retry_341_a"
    outdir.mkdir(parents=True, exist_ok=False)
    attempts = []
    parsed = None
    thread_id = None
    raw_output = ""
    returncode = None
    for attempt_no in range(1, MAX_RETRIES + 2):
        workdir = outdir / f"isolated-attempt-{attempt_no:03d}"
        workdir.mkdir(parents=True, exist_ok=False)
        event_path = outdir / f"attempt-{attempt_no:03d}.events.jsonl"
        last_path = outdir / f"attempt-{attempt_no:03d}.last.json"
        started = now()
        proc = subprocess.run(
            ["codex", "-a", "never", "exec", "--ephemeral", "--json", "--skip-git-repo-check", "-C", str(workdir), "-s", "read-only", "-m", "gpt-5.6-terra", "-c", "model_reasoning_effort=low", "--output-last-message", str(last_path), "-"],
            input=message + "\n", text=True, capture_output=True, cwd=ROOT, timeout=900,
            env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1"},
        )
        returncode = proc.returncode
        event_path.write_text(proc.stdout, encoding="utf-8")
        if proc.stderr:
            (outdir / f"attempt-{attempt_no:03d}.stderr.txt").write_text(proc.stderr, encoding="utf-8")
        events = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        thread_id = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)
        raw_output = next((e["item"]["text"] for e in events if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"), "").strip()
        try:
            parsed = json.loads(raw_output)
        except Exception:
            parsed = None
        rate = "429" in (proc.stdout + proc.stderr).lower() and "too many requests" in (proc.stdout + proc.stderr).lower()
        attempts.append({"attempt_no": attempt_no, "started_at_utc": started, "ended_at_utc": now(), "returncode": returncode, "thread_id": thread_id, "event_path": str(event_path), "last_path": str(last_path) if last_path.exists() else None, "rate_limited_429": rate, "raw_output": raw_output, "parsed_output": parsed})
        if rate and attempt_no <= MAX_RETRIES:
            time.sleep(min(60, 5 * (2 ** min(attempt_no - 1, 4))))
            continue
        break
    final = dict(source)
    final["status"] = "ok" if isinstance(parsed, dict) and parsed.get("pair_id") == "safe-pair:341" and parsed.get("prompt_revision") == "public-semantic-pair-quality-v2" else "pending"
    final["failure_reason"] = None if final["status"] == "ok" else "retry_output_invalid"
    final["agent_identity"] = {"thread_id": thread_id, "model": "gpt-5.6-terra", "model_revision": "codex-cli-0.153.4", "reasoning_effort": "low"}
    final["raw_output"] = raw_output
    final["raw_output_sha256"] = __import__("hashlib").sha256(raw_output.encode()).hexdigest()
    final["parsed_output"] = parsed
    final["attempts"] = attempts
    final["attempt_count"] = len(attempts)
    final["retry_source"] = str(SOURCE)
    target = RUN / "raw/a/safe-pair_341.a.retry.json"
    target.write_text(json.dumps(final, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": final["status"], "attempt_count": len(attempts), "thread_id": thread_id, "target": str(target)}))
    return 0 if final["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
