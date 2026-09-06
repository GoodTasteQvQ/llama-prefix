"""Post-run provenance archive with immutable, non-self-hashed manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import BroadeningError, atomic_write_json, file_sha256, git_state, read_json, read_jsonl, utc_now
from .ledger import load_schedule


def _files_for_archive(run_dir: Path, explicit: Iterable[Path] | None = None) -> list[Path]:
    if explicit is not None:
        paths = [
            Path(path) if Path(path).is_absolute() else run_dir / Path(path)
            for path in explicit
        ]
    else:
        paths = [
            path for path in run_dir.rglob("*")
            if path.is_file() and not path.name.startswith("provenance_manifest")
        ]
    result: list[Path] = []
    for path in sorted(paths):
        resolved = path.resolve()
        try:
            resolved.relative_to(run_dir.resolve())
        except ValueError as exc:
            raise BroadeningError(f"archive file escapes run directory: {path}") from exc
        if resolved.name.startswith("provenance_manifest"):
            continue
        result.append(resolved)
    return result


def _terminal_check(run_dir: Path, *, require_human: bool) -> dict[str, Any]:
    required = ["run_header.json", "frames.json", "resolved_config.json", "analysis.json"]
    missing = [name for name in required if not (run_dir / name).is_file()]
    generation_path = run_dir / "generation_attempts.jsonl"
    if not generation_path.is_file():
        missing.append("generation_attempts.jsonl")
    ledger_path = run_dir / "generation_ledger.jsonl"
    if not ledger_path.is_file():
        missing.append("generation_ledger.jsonl")
    judge_path = run_dir / "judge_records.jsonl"
    if not judge_path.is_file():
        missing.append("judge_records.jsonl")
    nonterminal = []
    fixture_run = False
    header_path = run_dir / "run_header.json"
    if header_path.is_file():
        try:
            fixture_run = bool(read_json(header_path).get("fixture", False))
        except (OSError, UnicodeDecodeError, ValueError):
            nonterminal.append("run_header:invalid")

    block_files = {
        "core": {
            "schedule": "generation_schedule.jsonl", "attempts": "generation_attempts.jsonl",
            "ledger": "generation_ledger.jsonl", "judges": "judge_records.jsonl",
            "analysis": "analysis.json",
        },
        **{
            block: {
                "schedule": f"generation_schedule_{block}.jsonl",
                "attempts": f"generation_attempts_{block}.jsonl",
                "ledger": f"generation_ledger_{block}.jsonl",
                "judges": f"judge_records_{block}.jsonl",
                "analysis": f"analysis_{block}/analysis.json",
            }
            for block in ("E1", "E2", "E3")
        },
    }
    scheduled_blocks: list[tuple[str, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]] = []
    for block, names in block_files.items():
        schedule_path = run_dir / names["schedule"]
        if not schedule_path.is_file():
            if block != "core" and any((run_dir / names[field]).is_file() for field in ("attempts", "ledger", "judges")):
                missing.append(f"{block}:schedule")
            continue
        schedule = load_schedule(schedule_path)
        scheduled_response_ids = {row["response_id"] for row in schedule}
        for field in ("attempts", "ledger", "judges", "analysis"):
            if not (run_dir / names[field]).is_file():
                missing.append(f"{block}:{field}")
        ledger = read_jsonl(run_dir / names["ledger"]) if (run_dir / names["ledger"]).is_file() else []
        judge_records = read_jsonl(run_dir / names["judges"]) if (run_dir / names["judges"]).is_file() else []
        scheduled_blocks.append((block, names, schedule, ledger))
        if len(ledger) != len(schedule):
            nonterminal.append(f"{block}:generation_ledger:scheduled_row_count_mismatch")
        for expected, actual in zip(schedule, ledger):
            if any(
                actual.get(field) != expected[field]
                for field in ("schedule_id", "response_id", "identity", "dose_label")
            ):
                nonterminal.append(
                    f"{block}:generation_ledger:{actual.get('response_id', 'UNKNOWN')}:identity_mismatch"
                )
        ledger_response_ids = {row.get("response_id") for row in ledger}
        if ledger_response_ids != scheduled_response_ids:
            nonterminal.append(f"{block}:generation_ledger:response_id_set_mismatch")
        nonterminal.extend(
            f"{block}:generation_ledger:{row.get('response_id', 'UNKNOWN')}:{row.get('terminal_status')}"
            for row in ledger
            if row.get("terminal_status") in {"UNEXECUTED", "TECHNICAL_FAILURE_RETRYABLE"}
        )
        nonterminal.extend(
            f"{block}:generation_ledger:{row.get('response_id', 'UNKNOWN')}:missing_attempt"
            for row in ledger
            if row.get("terminal_status") != "UNEXECUTED"
            and (not isinstance(row.get("attempt_count"), int) or row.get("attempt_count", 0) < 1)
        )
        judge_ids = [row.get("response_id") for row in judge_records]
        if len(judge_ids) != len(set(judge_ids)):
            nonterminal.append(f"{block}:judge_records:duplicate_response_id")
        if set(judge_ids) != scheduled_response_ids:
            nonterminal.append(f"{block}:judge_records:response_id_set_mismatch")
        allowed_four = {"PARSED", "PARSE_FAILURE", "TECHNICAL_FAILURE", "UNEXECUTED"}
        allowed_binary = {
            "NOT_REQUESTED", "SHORT_RULE_SAFE", "PARSED", "PARSE_FAILURE",
            "TECHNICAL_FAILURE", "UNEXECUTED",
        }
        for row in judge_records:
            if row.get("schema_version") != "paper1-broadening-judge-record-v1":
                nonterminal.append(f"{block}:judge_records:{row.get('response_id', 'UNKNOWN')}:schema")
            if row.get("four_class_status") not in allowed_four:
                nonterminal.append(f"{block}:judge_records:{row.get('response_id', 'UNKNOWN')}:four_class_status")
            if row.get("binary_status") not in allowed_binary:
                nonterminal.append(f"{block}:judge_records:{row.get('response_id', 'UNKNOWN')}:binary_status")
        nonterminal.extend(
            f"{block}:judge_records:{row.get('response_id', 'UNKNOWN')}:UNEXECUTED"
            for row in judge_records
            if row.get("four_class_status") == "UNEXECUTED"
        )
        ledger_ids = {row.get("response_id") for row in ledger}
        judge_id_set = {row.get("response_id") for row in judge_records}
        nonterminal.extend(
            f"{block}:judge_records:{response_id}:missing"
            for response_id in sorted(ledger_ids - judge_id_set)
            if response_id is not None
        )
        binary_requested = any(row.get("binary_status") != "NOT_REQUESTED" for row in judge_records)
        if binary_requested:
            nonterminal.extend(
                f"{block}:judge_records:{row.get('response_id', 'UNKNOWN')}:binary_UNEXECUTED"
                for row in judge_records
                if row.get("binary_status") == "UNEXECUTED"
            )

        # A real block is archiveable only after both runtimes have emitted
        # explicit release evidence. Fixture runs intentionally use the
        # lightweight legacy path and are exempt from this runtime gate.
        if not fixture_run:
            release_files = {
                "behavior": run_dir / (
                    "behavior_release.json" if block == "core"
                    else f"behavior_release_{block}.json"
                ),
                "judge": run_dir / (
                    "judge_release.json" if block == "core"
                    else f"judge_release_{block}.json"
                ),
            }
            for role, release_path in release_files.items():
                if not release_path.is_file():
                    nonterminal.append(f"{block}:{role}_release:missing")
                    continue
                try:
                    release = read_json(release_path)
                except (OSError, UnicodeDecodeError, ValueError):
                    nonterminal.append(f"{block}:{role}_release:invalid")
                    continue
                if not isinstance(release, Mapping) or not release:
                    nonterminal.append(f"{block}:{role}_release:empty")
                    continue
                for key, value in release.items():
                    if not isinstance(value, Mapping):
                        nonterminal.append(f"{block}:{role}_release:{key}:invalid")
                        continue
                    if value.get("status") in {"RELEASE_FAILURE", "RUNTIME_NOT_RUN", "PROCESS_FAILED"}:
                        nonterminal.append(f"{block}:{role}_release:{key}:{value.get('status')}")
                    if role == "behavior" and any(
                        value.get(field) is not True for field in (
                            "behavior_released", "behavior_hook_removed",
                            "behavior_model_reference_cleared", "behavior_tokenizer_reference_cleared",
                            "gc_collect_called",
                        )
                    ):
                        nonterminal.append(f"{block}:{role}_release:{key}:incomplete")
                    if role == "judge" and any(
                        value.get(field) is not True for field in (
                            "judge_released", "judge_model_reference_cleared",
                            "judge_tokenizer_reference_cleared", "judge_gc_collect_called",
                        )
                    ):
                        nonterminal.append(f"{block}:{role}_release:{key}:incomplete")
            status_path = run_dir / (
                "judge_runtime_status.json" if block == "core"
                else f"judge_runtime_status_{block}.json"
            )
            if status_path.is_file():
                try:
                    judge_status = read_json(status_path)
                except (OSError, UnicodeDecodeError, ValueError):
                    nonterminal.append(f"{block}:judge_runtime_status:invalid")
                else:
                    if not isinstance(judge_status, Mapping):
                        nonterminal.append(f"{block}:judge_runtime_status:invalid")
                    elif judge_status.get("status") in {"RUNTIME_NOT_RUN", "PROCESS_FAILED", "UNEXECUTED"}:
                        nonterminal.append(f"{block}:judge_runtime_status:{judge_status.get('status')}")

    if not fixture_run:
        for block in ("core", "E1", "E2", "E3"):
            screen_schedule = run_dir / f"screen_generation_schedule_{block}.jsonl"
            if not screen_schedule.is_file():
                continue
            screen_files = {
                "ledger": run_dir / f"screen_generation_ledger_{block}.jsonl",
                "judges": run_dir / f"screen_judge_records_{block}.jsonl",
                "behavior_release": run_dir / f"screen_behavior_release_{block}.json",
                "judge_release": run_dir / f"screen_judge_release_{block}.json",
                "processes": run_dir / f"screen_processes_{block}.json",
            }
            for role, path in screen_files.items():
                if not path.is_file():
                    nonterminal.append(f"{block}:screen_{role}:missing")
            for role in ("behavior_release", "judge_release"):
                path = screen_files[role]
                if not path.is_file():
                    continue
                try:
                    payload = read_json(path)
                except (OSError, UnicodeDecodeError, ValueError):
                    nonterminal.append(f"{block}:screen_{role}:invalid")
                    continue
                if not isinstance(payload, Mapping) or not payload:
                    nonterminal.append(f"{block}:screen_{role}:empty")
                    continue
                for key, value in payload.items():
                    if not isinstance(value, Mapping) or value.get("status") in {
                        "RELEASE_FAILURE", "RUNTIME_NOT_RUN", "PROCESS_FAILED",
                    }:
                        nonterminal.append(f"{block}:screen_{role}:{key}:invalid_or_failed")
            try:
                process = read_json(screen_files["processes"])
            except (OSError, UnicodeDecodeError, ValueError):
                process = None
            if not isinstance(process, Mapping) or any(
                not isinstance(process.get(role), Mapping) or process[role].get("success") is not True
                for role in ("generation", "judge")
            ):
                nonterminal.append(f"{block}:screen_processes:incomplete")

    # Legacy/manual fixture runs may not materialize a schedule. Preserve the
    # original terminal checks for their core ledger and Judge files.
    if not (run_dir / block_files["core"]["schedule"]).is_file():
        if ledger_path.is_file():
            legacy_ledger = read_jsonl(ledger_path)
            nonterminal.extend(
                f"core:generation_ledger:{row.get('response_id', 'UNKNOWN')}:{row.get('terminal_status')}"
                for row in legacy_ledger
                if row.get("terminal_status") in {"UNEXECUTED", "TECHNICAL_FAILURE_RETRYABLE"}
            )
            nonterminal.extend(
                f"core:generation_ledger:{row.get('response_id', 'UNKNOWN')}:missing_attempt"
                for row in legacy_ledger
                if row.get("terminal_status") != "UNEXECUTED"
                and (not isinstance(row.get("attempt_count"), int) or row.get("attempt_count", 0) < 1)
            )
        if judge_path.is_file():
            legacy_judges = read_jsonl(judge_path)
            nonterminal.extend(
                f"core:judge_records:{row.get('response_id', 'UNKNOWN')}:UNEXECUTED"
                for row in legacy_judges
                if row.get("four_class_status") == "UNEXECUTED"
            )
    missing.extend(nonterminal)

    human_pending = False
    human_blocks = ["core", *[block for block, _names, _schedule, _ledger in scheduled_blocks if block != "core"]]
    for block in human_blocks:
        suffix = "" if block == "core" else f"_{block}"
        human_paths = {
            "allocation": run_dir / f"human_allocation{suffix}.json",
            "labels": run_dir / f"human_labels{suffix}.jsonl",
            "analysis": run_dir / f"human_analysis{suffix}.json",
        }
        human_files_present = all(path.is_file() for path in human_paths.values())
        if not human_files_present:
            human_pending = True
            continue
        allocation = read_json(human_paths["allocation"])
        labels = read_jsonl(human_paths["labels"])
        labeled_ids = {row.get("blind_id") for row in labels if row.get("adjudicated_label") is not None}
        probability_ids = {
            row.get("blind_id")
            for row in allocation.get("records", [])
            if not row.get("diagnostic_only")
        }
        human_pending = human_pending or not probability_ids.issubset(labeled_ids)
        human_analysis = read_json(human_paths["analysis"])
        human_pending = human_pending or human_analysis.get("status") == "HUMAN_LABELS_PENDING"
    if require_human and human_pending:
        missing.append("human_labels_incomplete")
    return {
        "terminal": not missing,
        "missing_required_files": missing,
        "human_pending": human_pending,
        "final": not missing and not human_pending,
    }


def archive_run(
    *, run_dir: Path, repo_root: Path, run_header: Mapping[str, Any],
    source_ids: Mapping[str, Any], require_human: bool = False,
    explicit_files: Iterable[Path] | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    terminal = _terminal_check(run_dir, require_human=require_human)
    if not terminal["terminal"]:
        raise BroadeningError(f"run is not terminal; missing {terminal['missing_required_files']}")
    manifest_path = run_dir / "provenance_manifest.json"
    if manifest_path.exists():
        archive_revision = 2
        while (run_dir / f"provenance_manifest.v{archive_revision}.json").exists():
            archive_revision += 1
        manifest_path = run_dir / f"provenance_manifest.v{archive_revision}.json"
    else:
        archive_revision = 1
    files = _files_for_archive(run_dir, explicit_files)
    records = [
        {"path": str(path.relative_to(run_dir)), "sha256": file_sha256(path)}
        for path in files
    ]
    manifest = {
        "schema_version": "paper1-broadening-provenance-manifest-v1",
        "archive_revision": archive_revision,
        "archived_at": utc_now(),
        "run_id": run_header.get("run_id"),
        "design_id": run_header.get("design_id"),
        "design_revision": run_header.get("design_revision"),
        "implementation_revision": run_header.get("implementation_revision"),
        "source_ids": dict(source_ids),
        "run_header_identity": {
            "code_commit": run_header.get("code_commit"),
            "dirty": run_header.get("dirty"),
            "started_at": run_header.get("started_at"),
            "model_revision": run_header.get("model_revision"),
            "tokenizer_revision": run_header.get("tokenizer_revision"),
            "judge_revision": run_header.get("judge_revision"),
            "template": run_header.get("template"),
            "decoder": run_header.get("decoder"),
        },
        "repository_state_at_archive": git_state(repo_root),
        "terminal_check": terminal,
        "archive_status": "FINAL" if terminal["final"] else "PENDING_HUMAN",
        "files": records,
        "manifest_is_self_hashed": False,
    }
    atomic_write_json(manifest_path, manifest, overwrite=False)
    return manifest
