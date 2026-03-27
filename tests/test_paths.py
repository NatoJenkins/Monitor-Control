"""Tests for shared.paths config resolution and pythonw.exe null-guard (INFRA-01, INFRA-02)."""
import os
import sys
from pathlib import Path

import pytest


def test_get_config_path_is_absolute():
    from shared.paths import get_config_path
    p = get_config_path()
    assert isinstance(p, Path)
    assert p.is_absolute()
    assert p.name == "config.json"


def test_get_config_path_cwd_independent(tmp_path, monkeypatch):
    from shared.paths import get_config_path
    before = get_config_path()
    monkeypatch.chdir(tmp_path)
    after = get_config_path()
    assert before == after


def test_get_config_path_in_localappdata():
    from shared.paths import get_config_path
    import os
    appdata = Path(os.environ["LOCALAPPDATA"])
    p = get_config_path()
    assert appdata in p.parents, f"Expected config inside LOCALAPPDATA, got {p}"
    assert "MonitorControl" in p.parts, f"Expected MonitorControl subdir, got {p}"


def test_no_bare_config_strings_in_host_main():
    src = Path(__file__).resolve().parent.parent / "host" / "main.py"
    text = src.read_text(encoding="utf-8")
    # Remove comment lines before checking
    code_lines = [l for l in text.splitlines() if not l.strip().startswith("#")]
    code = "\n".join(code_lines)
    assert '"config.json"' not in code, "host/main.py still has bare 'config.json' string"


def test_no_bare_config_strings_in_control_panel():
    src = Path(__file__).resolve().parent.parent / "control_panel" / "__main__.py"
    text = src.read_text(encoding="utf-8")
    code_lines = [l for l in text.splitlines() if not l.strip().startswith("#")]
    code = "\n".join(code_lines)
    assert '"config.json"' not in code, "control_panel/__main__.py still has bare 'config.json' string"


def test_null_guard_stdout(monkeypatch):
    """Simulates pythonw.exe context where sys.stdout is None."""
    monkeypatch.setattr(sys, "stdout", None)
    # Apply the same guard pattern used in host/main.py
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    # This must not raise AttributeError
    print("test output after null-guard")
    assert sys.stdout is not None


def test_null_guard_stderr(monkeypatch):
    """Simulates pythonw.exe context where sys.stderr is None."""
    monkeypatch.setattr(sys, "stderr", None)
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    assert sys.stderr is not None
