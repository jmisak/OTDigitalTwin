import os

from engine.utils import safe_log


def test_safe_log_writes_file(tmp_path):
    # Call safe_log and ensure it writes an entry to the default log file.
    # The function writes to 'driftline_errors.log' in the cwd, so change cwd temporarily.
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        safe_log("test-context", "this is a test error message")

        log_path = tmp_path / "driftline_errors.log"
        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "[test-context] this is a test error message" in content
    finally:
        os.chdir(cwd)
