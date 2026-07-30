#!/usr/bin/env python3
"""Strict offline loader smoke test with empty caches and blocked networking."""

from __future__ import annotations

import argparse
import copy
import hashlib
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.core import (  # noqa: E402
    OfflineNetworkError,
    canonical_sha256,
    file_sha256,
    require_strict_offline_runtime,
)
from stage3_pipeline.offline_assets import (  # noqa: E402
    AssetError,
    CANDIDATE_SPECS,
    OfflineJsonLoader,
    build_bundle,
    build_offline_asset_manifest,
    inspect_json_asset,
)
from stage3_pipeline.local_temp import require_project_local_temp  # noqa: E402


def manifest_hash(document: dict[str, object]) -> None:
    document.pop("manifest_sha256", None)
    document["manifest_sha256"] = canonical_sha256(document)


def ready_manifest(entry: dict[str, object]) -> dict[str, object]:
    formal = copy.deepcopy(entry)
    formal["disposition"] = "SYNTHETIC_FIXTURE_INPUT"
    formal["formal_input"] = False
    formal["prompt_frame_membership"] = "SYNTHETIC_E0_EXACT_FULL_FRAME"
    document: dict[str, object] = {
        "schema_version": "paper1-stage3-offline-asset-manifest-v1",
        "protocol_version": "v3.5-rc2",
        "created_at_utc": "2000-01-01T00:00:00Z",
        "asset_root_identity": "PAPER1_STAGE3_ASSET_ROOT",
        "absolute_paths_are_identity": False,
        "formal_inputs": [formal],
        "binding_inputs": [],
        "candidate_assets": [],
        "binding_validation": {
            "schema_version": "paper1-stage3-offline-loader-fixture-authorization-v1",
            "validation_status": "PASS",
            "synthetic_fixture": True,
            "formal_input_claim": False,
            "formal_experiment_run": False,
        },
        "offline_asset_status": "SYNTHETIC-OFFLINE-LOADER-READY",
        "run_ready": False,
        "formal_experiment_run": False,
        "blocking_reasons": [],
        "raw_sources_modified": False,
        "online_fallback": False,
    }
    manifest_hash(document)
    return document


def expect_asset_error(callable_object: object, marker: str, checks: list[str]) -> None:
    try:
        callable_object()  # type: ignore[operator]
    except AssetError:
        checks.append(marker)
    else:
        raise AssertionError(f"expected fail-closed AssetError: {marker}")


def bound_loader(document: dict[str, object], asset_root: Path) -> OfflineJsonLoader:
    expected = document.get("manifest_sha256")
    if not isinstance(expected, str):
        raise AssertionError("synthetic manifest lacks its explicit freeze-bound hash")
    return OfflineJsonLoader(
        document,
        asset_root,
        expected_manifest_sha256=expected,
        allow_synthetic_fixture=True,
    )


def write_raw(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_smoke() -> dict[str, object]:
    source_hashes = {path.name: file_sha256(path) for path in sorted((ROOT / "data").glob("*.json"))}
    network_attempts: list[str] = []

    def blocked(*_args: object, **_kwargs: object) -> None:
        network_attempts.append("network")
        raise AssertionError("HTTP/HTTPS/network access is forbidden in Stage 3 production")

    local_temp = require_project_local_temp(ROOT)
    with tempfile.TemporaryDirectory(prefix="paper1-stage3-offline-", dir=local_temp) as directory:
        temp = Path(directory)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HOME"] = str(temp / "empty-hf-home")
        os.environ["HF_DATASETS_CACHE"] = str(temp / "empty-datasets-cache")
        os.environ["TRANSFORMERS_CACHE"] = str(temp / "empty-transformers-cache")
        for variable in ("HF_HOME", "HF_DATASETS_CACHE", "TRANSFORMERS_CACHE"):
            Path(os.environ[variable]).mkdir()

        asset_root = temp / "asset-root"
        (asset_root / "data").mkdir(parents=True)
        source = ROOT / "data/jbb_behaviors_harmful.json"
        target = asset_root / "data/jbb_behaviors_harmful.json"
        shutil.copyfile(source, target)
        entry = inspect_json_asset(asset_root, CANDIDATE_SPECS[0])
        manifest = ready_manifest(entry)
        checks: list[str] = []

        with ExitStack() as stack:
            stack.enter_context(patch.object(socket, "create_connection", side_effect=blocked))
            stack.enter_context(patch.object(urllib.request, "urlopen", side_effect=blocked))
            stack.enter_context(patch.object(http.client.HTTPConnection, "connect", blocked))
            stack.enter_context(patch.object(http.client.HTTPSConnection, "connect", blocked))
            loaded = bound_loader(manifest, asset_root).load_formal(
                "data/jbb_behaviors_harmful.json"
            )
            if len(loaded) != 100:
                raise AssertionError("offline loader did not return exact synthetic-bound frame")
            checks.append("exact_bound_input_pass")

            blocked_manifest = build_offline_asset_manifest(ROOT)
            if blocked_manifest["offline_asset_status"] != "DATA_IDENTITY_BLOCKED":
                raise AssertionError("unbound repository candidates were treated as formal")
            expect_asset_error(
                lambda: bound_loader(blocked_manifest, ROOT).load_formal(
                    "data/jbb_behaviors_harmful.json"
                ),
                "unbound_candidate_rejected",
                checks,
            )

            missing_root = temp / "missing-root"
            missing_root.mkdir()
            expect_asset_error(
                lambda: bound_loader(manifest, missing_root).load_formal(
                    "data/jbb_behaviors_harmful.json"
                ),
                "missing_file_rejected",
                checks,
            )

            target.write_bytes(target.read_bytes() + b"\n")
            expect_asset_error(
                lambda: bound_loader(manifest, asset_root).load_formal(
                    "data/jbb_behaviors_harmful.json"
                ),
                "raw_hash_mismatch_rejected",
                checks,
            )
            shutil.copyfile(source, target)

            schema_payload = json.loads(source.read_text(encoding="utf-8"))
            first = schema_payload[0]
            schema_payload[0] = {key: first[key] for key in reversed(list(first))}
            write_raw(target, schema_payload)
            schema_manifest = copy.deepcopy(manifest)
            schema_entry = schema_manifest["formal_inputs"][0]  # type: ignore[index]
            schema_entry["raw_sha256"] = file_sha256(target)
            schema_entry["byte_length"] = target.stat().st_size
            manifest_hash(schema_manifest)
            expect_asset_error(
                lambda: bound_loader(schema_manifest, asset_root).load_formal(
                    "data/jbb_behaviors_harmful.json"
                ),
                "schema_order_mismatch_rejected",
                checks,
            )

            wrong_type_payload = json.loads(source.read_text(encoding="utf-8"))
            wrong_type_payload[0]["Index"] = str(wrong_type_payload[0]["Index"])
            write_raw(target, wrong_type_payload)
            wrong_type_manifest = copy.deepcopy(manifest)
            wrong_type_entry = wrong_type_manifest["formal_inputs"][0]  # type: ignore[index]
            wrong_type_entry["raw_sha256"] = file_sha256(target)
            wrong_type_entry["byte_length"] = target.stat().st_size
            manifest_hash(wrong_type_manifest)
            expect_asset_error(
                lambda: bound_loader(wrong_type_manifest, asset_root).load_formal(
                    "data/jbb_behaviors_harmful.json"
                ),
                "schema_field_type_mismatch_rejected",
                checks,
            )

            nonfinite_payload = json.loads(source.read_text(encoding="utf-8"))
            nonfinite_payload[0]["Index"] = float("nan")
            write_raw(target, nonfinite_payload)
            nonfinite_manifest = copy.deepcopy(manifest)
            nonfinite_entry = nonfinite_manifest["formal_inputs"][0]  # type: ignore[index]
            nonfinite_entry["raw_sha256"] = file_sha256(target)
            nonfinite_entry["byte_length"] = target.stat().st_size
            manifest_hash(nonfinite_manifest)
            expect_asset_error(
                lambda: bound_loader(nonfinite_manifest, asset_root).load_formal(
                    "data/jbb_behaviors_harmful.json"
                ),
                "nonfinite_json_constant_rejected",
                checks,
            )

            duplicate_key_text = source.read_text(encoding="utf-8").replace(
                '"Index": 0,',
                '"Index": 0,\n    "Index": 0,',
                1,
            )
            target.write_text(duplicate_key_text, encoding="utf-8", newline="")
            duplicate_key_manifest = copy.deepcopy(manifest)
            duplicate_key_entry = duplicate_key_manifest["formal_inputs"][0]  # type: ignore[index]
            duplicate_key_entry["raw_sha256"] = file_sha256(target)
            duplicate_key_entry["byte_length"] = target.stat().st_size
            manifest_hash(duplicate_key_manifest)
            expect_asset_error(
                lambda: bound_loader(duplicate_key_manifest, asset_root).load_formal(
                    "data/jbb_behaviors_harmful.json"
                ),
                "duplicate_json_object_key_rejected",
                checks,
            )

            duplicate_payload = json.loads(source.read_text(encoding="utf-8"))
            duplicate_payload[-1] = copy.deepcopy(duplicate_payload[0])
            write_raw(target, duplicate_payload)
            duplicate_manifest = copy.deepcopy(manifest)
            duplicate_entry = duplicate_manifest["formal_inputs"][0]  # type: ignore[index]
            duplicate_entry["raw_sha256"] = file_sha256(target)
            duplicate_entry["byte_length"] = target.stat().st_size
            manifest_hash(duplicate_manifest)
            expect_asset_error(
                lambda: bound_loader(duplicate_manifest, asset_root).load_formal(
                    "data/jbb_behaviors_harmful.json"
                ),
                "duplicate_identity_rejected",
                checks,
            )
            shutil.copyfile(source, target)

            frame_manifest = copy.deepcopy(manifest)
            frame_manifest["formal_inputs"][0]["canonical_frame_sha256"] = "0" * 64  # type: ignore[index]
            manifest_hash(frame_manifest)
            expect_asset_error(
                lambda: bound_loader(frame_manifest, asset_root).load_formal(
                    "data/jbb_behaviors_harmful.json"
                ),
                "canonical_frame_hash_mismatch_rejected",
                checks,
            )

            corrupt_manifest = copy.deepcopy(manifest)
            corrupt_manifest["manifest_sha256"] = "0" * 64
            expect_asset_error(
                lambda: bound_loader(corrupt_manifest, asset_root),
                "manifest_hash_mismatch_rejected",
                checks,
            )

            expect_asset_error(
                lambda: OfflineJsonLoader(
                    manifest,
                    asset_root,
                    expected_manifest_sha256="0" * 64,
                ),
                "freeze_bound_manifest_hash_mismatch_rejected",
                checks,
            )

            symlink_root = temp / "symlink-root"
            (symlink_root / "data").mkdir(parents=True)
            (symlink_root / "cache").mkdir()
            symlink_target = symlink_root / "cache/jbb.json"
            shutil.copyfile(source, symlink_target)
            symlink_path = symlink_root / "data/jbb_behaviors_harmful.json"
            try:
                os.symlink(symlink_target, symlink_path)
            except OSError:
                (symlink_root / "data").rmdir()
                junction_target = symlink_root / "cache-data"
                junction_target.mkdir()
                shutil.copyfile(source, junction_target / "jbb_behaviors_harmful.json")
                created = subprocess.run(
                    [
                        "cmd.exe", "/d", "/c", "mklink", "/J",
                        str(symlink_root / "data"), str(junction_target),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if created.returncode != 0:
                    raise AssertionError(
                        "strict offline smoke could create neither symlink nor junction fixture: "
                        + created.stderr
                    )
            expect_asset_error(
                lambda: bound_loader(manifest, symlink_root).load_formal(
                    "data/jbb_behaviors_harmful.json"
                ),
                "data_symlink_rejected",
                checks,
            )

            no_license_output = temp / "bundle-no-license"
            expect_asset_error(
                lambda: build_bundle(
                    manifest,
                    no_license_output,
                    asset_root=asset_root,
                    expected_manifest_sha256=manifest["manifest_sha256"],
                    allow_synthetic_fixture=True,
                ),
                "missing_license_material_rejected",
                checks,
            )
            if no_license_output.exists():
                raise AssertionError("failed bundle validation left a partial output directory")

            licenses = asset_root / "licenses"
            licenses.mkdir()
            license_source = licenses / "synthetic-license.txt"
            license_source.write_text("Synthetic E0 license material.\n", encoding="ascii", newline="\n")
            bundle_manifest = copy.deepcopy(manifest)
            bundle_entry = bundle_manifest["formal_inputs"][0]  # type: ignore[index]
            bundle_entry["license"] = "SYNTHETIC-E0"
            bundle_entry["license_material"] = {
                "source_relative_path": "licenses/synthetic-license.txt",
                "bundle_relative_path": "LICENSES/jbb_behaviors_harmful.LICENSE.txt",
                "raw_sha256": file_sha256(license_source),
            }
            manifest_hash(bundle_manifest)
            first_bundle_dir = temp / "bundle-a"
            second_bundle_dir = temp / "bundle-b"
            original_umask = os.umask(0o077)
            try:
                first_bundle = build_bundle(
                    bundle_manifest,
                    first_bundle_dir,
                    asset_root=asset_root,
                    expected_manifest_sha256=bundle_manifest["manifest_sha256"],
                    allow_synthetic_fixture=True,
                )
                os.umask(0o022)
                second_bundle = build_bundle(
                    bundle_manifest,
                    second_bundle_dir,
                    asset_root=asset_root,
                    expected_manifest_sha256=bundle_manifest["manifest_sha256"],
                    allow_synthetic_fixture=True,
                )
            finally:
                os.umask(original_umask)
            if first_bundle["bundle_sha256"] != second_bundle["bundle_sha256"]:
                raise AssertionError("offline bundle archive is not byte deterministic")
            if first_bundle["file_count"] != 4 or first_bundle["payload_bytes"] <= len(source.read_bytes()):
                raise AssertionError("offline bundle file/byte accounting is inconsistent")
            with tarfile.open(first_bundle_dir.with_suffix(".tar.gz"), mode="r:gz") as archive:
                members = archive.getmembers()
                names = [member.name for member in members]
            for member in members:
                if member.isfile() and member.mode != 0o644:
                    raise AssertionError(f"bundle file mode is not 0644: {member.name}")
                if member.isdir() and member.mode != 0o755:
                    raise AssertionError(f"bundle directory mode is not 0755: {member.name}")
                if not member.isfile() and not member.isdir():
                    raise AssertionError(f"bundle contains unsupported member type: {member.name}")
            if any("\\" in name or not name.startswith("offline_bundle/") for name in names):
                raise AssertionError("offline bundle archive is not Linux-path portable")
            if "offline_bundle/data/jbb_behaviors_harmful.json" not in names:
                raise AssertionError("offline bundle omitted the raw formal input")
            if "offline_bundle/LICENSES/jbb_behaviors_harmful.LICENSE.txt" not in names:
                raise AssertionError("offline bundle omitted explicit license material")
            checks.extend(
                [
                    "explicit_license_material_bundled",
                    "deterministic_linux_portable_bundle",
                    "tar_member_modes_pinned_across_umasks",
                    "bundle_file_and_byte_counts_verified",
                ]
            )

            collision_dir = temp / "bundle-collision"
            collision_archive = collision_dir.with_suffix(".tar.gz")
            collision_bytes = b"preexisting-archive-must-survive"
            collision_archive.write_bytes(collision_bytes)
            expect_asset_error(
                lambda: build_bundle(
                    bundle_manifest,
                    collision_dir,
                    asset_root=asset_root,
                    expected_manifest_sha256=bundle_manifest["manifest_sha256"],
                    allow_synthetic_fixture=True,
                ),
                "preexisting_bundle_archive_rejected",
                checks,
            )
            if collision_dir.exists() or collision_archive.read_bytes() != collision_bytes:
                raise AssertionError("bundle collision handling changed a preexisting target")

            failed_bundle_dir = temp / "bundle-injected-failure"
            with patch.object(tarfile, "open", side_effect=OSError("synthetic tar failure")):
                try:
                    build_bundle(
                        bundle_manifest,
                        failed_bundle_dir,
                        asset_root=asset_root,
                        expected_manifest_sha256=bundle_manifest["manifest_sha256"],
                        allow_synthetic_fixture=True,
                    )
                except OSError:
                    pass
                else:
                    raise AssertionError("injected bundle failure did not fail closed")
            if failed_bundle_dir.exists() or failed_bundle_dir.with_suffix(".tar.gz").exists():
                raise AssertionError("failed bundle left a partial directory or archive")
            checks.append("failed_bundle_cleans_only_new_targets")

            unsupported_bundle_dir = temp / "bundle-unsupported-member"
            original_gettarinfo = tarfile.TarFile.gettarinfo
            injected = False

            def unsupported_gettarinfo(
                handle: tarfile.TarFile, name: str, arcname: str | None = None
            ) -> tarfile.TarInfo:
                nonlocal injected
                info = original_gettarinfo(handle, name, arcname)
                if info.isreg() and not injected:
                    info.type = tarfile.SYMTYPE
                    info.linkname = "forbidden-link-target"
                    injected = True
                return info

            with patch.object(tarfile.TarFile, "gettarinfo", unsupported_gettarinfo):
                expect_asset_error(
                    lambda: build_bundle(
                        bundle_manifest,
                        unsupported_bundle_dir,
                        asset_root=asset_root,
                        expected_manifest_sha256=bundle_manifest["manifest_sha256"],
                        allow_synthetic_fixture=True,
                    ),
                    "unsupported_tar_member_rejected",
                    checks,
                )
            if (
                unsupported_bundle_dir.exists()
                or unsupported_bundle_dir.with_suffix(".tar.gz").exists()
            ):
                raise AssertionError("unsupported tar member left a partial bundle")

            symlink_license = licenses / "synthetic-license-link.txt"
            symlink_license_relative = "licenses/synthetic-license-link.txt"
            try:
                os.symlink(license_source, symlink_license)
            except OSError:
                license_junction = asset_root / "license-links"
                created = subprocess.run(
                    [
                        "cmd.exe", "/d", "/c", "mklink", "/J",
                        str(license_junction), str(licenses),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if created.returncode != 0:
                    raise AssertionError(
                        "strict offline smoke could create neither license symlink nor junction: "
                        + created.stderr
                    )
                symlink_license_relative = "license-links/synthetic-license.txt"
            symlink_license_manifest = copy.deepcopy(bundle_manifest)
            symlink_license_entry = symlink_license_manifest["formal_inputs"][0]  # type: ignore[index]
            symlink_license_entry["license_material"]["source_relative_path"] = (  # type: ignore[index]
                symlink_license_relative
            )
            manifest_hash(symlink_license_manifest)
            expect_asset_error(
                lambda: build_bundle(
                    symlink_license_manifest,
                    temp / "bundle-symlink-license",
                    asset_root=asset_root,
                    expected_manifest_sha256=symlink_license_manifest["manifest_sha256"],
                    allow_synthetic_fixture=True,
                ),
                "license_symlink_rejected",
                checks,
            )

            require_strict_offline_runtime()
            for audit_event, marker in (
                ("socket.__new__", "formal_socket_creation_audit_guard_blocks_backend_network"),
                ("socket.sendto", "formal_udp_sendto_audit_guard_blocks_backend_network"),
                ("socket.sendmsg", "formal_udp_sendmsg_audit_guard_blocks_backend_network"),
                ("socket.bind", "formal_socket_bind_audit_guard_blocks_backend_network"),
                ("socket.getnameinfo", "formal_socket_dns_audit_guard_blocks_backend_network"),
                ("os.posix_spawn", "formal_posix_spawn_audit_guard_blocks_backend_escape"),
                ("os.fork", "formal_fork_audit_guard_blocks_backend_escape"),
                ("os.forkpty", "formal_forkpty_audit_guard_blocks_backend_escape"),
            ):
                try:
                    sys.audit(audit_event)
                except OfflineNetworkError:
                    checks.append(marker)
                else:
                    raise AssertionError(
                        f"formal socket audit guard allowed audit event: {audit_event}"
                    )
            try:
                subprocess.run([sys.executable, "-c", "pass"], check=False)
            except OfflineNetworkError:
                checks.append("formal_subprocess_audit_guard_blocks_backend_escape")
            else:
                raise AssertionError("formal runtime audit guard allowed subprocess escape")
            try:
                os.system("exit 0")
            except OfflineNetworkError:
                checks.append("formal_os_system_audit_guard_blocks_backend_escape")
            else:
                raise AssertionError("formal runtime audit guard allowed os.system escape")

        production_sources = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted((ROOT / "stage3_pipeline").glob("*.py"))
        )
        forbidden = ("load_dataset(", ".from_pretrained(", "requests.", "urllib.request", "http.client")
        found = [token for token in forbidden if token in production_sources]
        if found:
            raise AssertionError(f"production call graph contains network/download tokens: {found}")
        checks.append("production_call_graph_no_online_download")

    after_hashes = {path.name: file_sha256(path) for path in sorted((ROOT / "data").glob("*.json"))}
    if source_hashes != after_hashes:
        raise AssertionError("offline smoke modified repository JSON bytes")
    if network_attempts:
        raise AssertionError("production attempted network access")
    return {
        "schema_version": "paper1-stage3-offline-smoke-receipt-v1",
        "marker": "STAGE3_STRICT_OFFLINE_SMOKE_PASS",
        "synthetic_only": True,
        "formal_experiment_run": False,
        "offline_environment": {
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "empty_cache": True,
        },
        "network_attempt_count": 0,
        "checks": checks,
        "repository_json_sha256": source_hashes,
        "repository_json_unchanged": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_smoke()
    if args.output:
        output = args.output.resolve()
        if output.exists():
            raise SystemExit(f"refusing to overwrite {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
