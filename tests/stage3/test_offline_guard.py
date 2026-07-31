from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import unittest

from stage3_pipeline.core import (
    OfflineNetworkError,
    OfflineOperationError,
    offline_audit_snapshot,
    offline_execution_guard,
)
from tests.stage3.helpers import ROOT


class OfflineGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.update({
            "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "TEMP": str(ROOT / ".codex-temp"), "TMP": str(ROOT / ".codex-temp"),
        })

    def test_network_and_subprocess_public_entries_block_before_side_effect(self) -> None:
        guard = offline_execution_guard()
        with guard:
            with self.assertRaises(OfflineNetworkError):
                socket.socket()
            calls = (
                lambda: subprocess.Popen(["stage3-command-that-does-not-exist"]),
                lambda: subprocess.run(["stage3-command-that-does-not-exist"]),
                lambda: subprocess.call(["stage3-command-that-does-not-exist"]),
                lambda: subprocess.check_call(["stage3-command-that-does-not-exist"]),
                lambda: subprocess.check_output(["stage3-command-that-does-not-exist"]),
            )
            for call in calls:
                with self.assertRaises(OfflineOperationError):
                    call()
        self.assertEqual(guard.report["category_counts"]["network"], 1)
        self.assertEqual(guard.report["category_counts"]["subprocess"], len(calls))

    def test_system_spawn_exec_and_available_fork_events_are_classified(self) -> None:
        guard = offline_execution_guard()
        with guard:
            with self.assertRaises(OfflineOperationError):
                os.system("stage3-command-that-does-not-exist")
            with self.assertRaises(OfflineOperationError):
                os.popen("stage3-command-that-does-not-exist")
            with self.assertRaises(OfflineOperationError):
                sys.audit("os.popen", "stage3-command-that-does-not-exist")
            with self.assertRaises(OfflineOperationError):
                sys.audit("os.spawn", "stage3-command-that-does-not-exist")
            with self.assertRaises(OfflineOperationError):
                sys.audit("os.exec", "stage3-command-that-does-not-exist")
            if hasattr(os, "spawnv"):
                with self.assertRaises(OfflineOperationError):
                    os.spawnv(os.P_WAIT, "stage3-command-that-does-not-exist", ["stage3-command-that-does-not-exist"])
            if hasattr(os, "execv"):
                with self.assertRaises(OfflineOperationError):
                    os.execv("stage3-command-that-does-not-exist", ["stage3-command-that-does-not-exist"])
            if hasattr(os, "fork"):
                # POSIX os.spawnv may be implemented via fork and add an earlier fork event.
                fork_before = offline_audit_snapshot()["category_counts"]["fork"]
                with self.assertRaises(OfflineOperationError):
                    sys.audit("os.fork")
                fork_after = offline_audit_snapshot()["category_counts"]["fork"]
                self.assertEqual(fork_after, fork_before + 1)
        counts = guard.report["category_counts"]
        self.assertEqual(counts["system"], 2)
        self.assertGreaterEqual(counts["subprocess"], 1)
        self.assertGreaterEqual(counts["spawn"], 1)
        self.assertGreaterEqual(counts["exec"], 1)
        if hasattr(os, "fork"):
            self.assertGreaterEqual(counts["fork"], 1)

    def test_new_thread_cannot_bypass_process_scope(self) -> None:
        failures: list[BaseException] = []

        def attempt() -> None:
            try:
                socket.socket()
            except BaseException as exc:
                failures.append(exc)

        guard = offline_execution_guard()
        with guard:
            thread = threading.Thread(target=attempt)
            thread.start()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], OfflineNetworkError)
        self.assertEqual(guard.report["category_counts"]["network"], 1)

    def test_exception_exit_nested_restore_and_outside_scope(self) -> None:
        with self.assertRaisesRegex(ValueError, "fixture"):
            guard = offline_execution_guard()
            with guard:
                raise ValueError("fixture")
        self.assertEqual(guard.report["process_depth_after_exit"], 0)
        outer = offline_execution_guard()
        inner = offline_execution_guard()
        with outer:
            with inner:
                self.assertEqual(offline_audit_snapshot()["depth"], 2)
            self.assertEqual(inner.report["process_depth_after_exit"], 1)
            self.assertEqual(offline_audit_snapshot()["depth"], 1)
        self.assertEqual(outer.report["process_depth_after_exit"], 0)
        before = offline_audit_snapshot()["category_counts"].copy()
        sys.audit("socket.connect", None)
        self.assertEqual(offline_audit_snapshot()["category_counts"], before)

    def test_concurrent_nested_refcount_is_process_global_and_locked(self) -> None:
        entered = threading.Barrier(3)
        release = threading.Barrier(3)
        reports: list[dict[str, object]] = []
        failures: list[BaseException] = []

        def worker() -> None:
            try:
                guard = offline_execution_guard()
                with guard:
                    entered.wait(timeout=5)
                    release.wait(timeout=5)
                reports.append(guard.report)
            except BaseException as exc:
                failures.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        entered.wait(timeout=5)
        self.assertEqual(offline_audit_snapshot()["depth"], 2)
        release.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(reports), 2)
        self.assertEqual(offline_audit_snapshot()["depth"], 0)
        self.assertEqual(sorted(report["process_depth_after_exit"] for report in reports), [0, 1])


if __name__ == "__main__":
    unittest.main()
