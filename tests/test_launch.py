import contextlib
import io
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from assets import launch


class LaunchTests(unittest.TestCase):
    def test_explicit_occupied_port_is_rejected_before_startup(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            with tempfile.TemporaryDirectory() as temporary:
                dashboard = Path(temporary) / "phd_explorer.py"
                dashboard.write_text("pass\n", encoding="utf-8")
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    status = launch.main(
                        [str(dashboard), "--port", str(port), "--no-open"]
                    )

        self.assertEqual(status, 1)
        self.assertIn("already in use", stderr.getvalue())

    def test_free_port_is_bindable(self):
        port = launch.free_port(32740)
        self.assertTrue(launch.port_available(port))

    def test_never_ready_child_is_stopped(self):
        class FakeProcess:
            pid = 424242
            returncode = None

            @staticmethod
            def poll():
                return None

            @staticmethod
            def wait(timeout=None):
                return 0

        with tempfile.TemporaryDirectory() as temporary:
            dashboard = Path(temporary) / "phd_explorer.py"
            dashboard.write_text("pass\n", encoding="utf-8")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            with (
                mock.patch.object(launch.subprocess, "Popen", return_value=FakeProcess()),
                mock.patch.object(
                    launch.urllib.request,
                    "urlopen",
                    side_effect=OSError("not ready"),
                ),
                mock.patch.object(launch.time, "sleep"),
                mock.patch.object(launch.os, "killpg") as killpg,
                contextlib.redirect_stderr(io.StringIO()),
            ):
                status = launch.main(
                    [str(dashboard), "--port", str(port), "--no-open"]
                )
                helper_copied = (Path(temporary) / "excel_export.py").is_file()

        self.assertEqual(status, 1)
        self.assertTrue(helper_copied)
        killpg.assert_called_once_with(FakeProcess.pid, launch.signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
