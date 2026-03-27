"""Tests for control_panel/config_io.py — atomic write and load_config."""
import json
import os
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# test_atomic_write_produces_valid_json
# ---------------------------------------------------------------------------
def test_atomic_write_produces_valid_json(tmp_path):
    """atomic_write_config writes valid JSON to target path; reading it back matches input dict."""
    from control_panel.config_io import atomic_write_config

    target = tmp_path / "config.json"
    data = {"layout": {"display": {"width": 1920, "height": 515}}, "widgets": []}
    atomic_write_config(str(target), data)

    assert target.exists()
    with open(target, encoding="utf-8") as f:
        result = json.load(f)
    assert result == data


# ---------------------------------------------------------------------------
# test_atomic_write_uses_os_replace
# ---------------------------------------------------------------------------
def test_atomic_write_uses_os_replace(tmp_path):
    """atomic_write_config uses os.replace (not os.rename) for atomic swap."""
    from control_panel.config_io import atomic_write_config

    target = tmp_path / "config.json"
    data = {"test": True}

    # Patch the os.replace name inside the control_panel.config_io module to observe the call.
    # wraps=os.replace delegates to the real function so the file is actually moved.
    with patch("control_panel.config_io.os.replace", wraps=os.replace) as mock_replace:
        atomic_write_config(str(target), data)

    mock_replace.assert_called_once()
    # Verify the destination is our target
    args = mock_replace.call_args[0]
    assert str(target) in args[1]


# ---------------------------------------------------------------------------
# test_atomic_write_cleans_up_on_error
# ---------------------------------------------------------------------------
def test_atomic_write_cleans_up_on_error(tmp_path):
    """atomic_write_config cleans up temp file when json.dump raises (non-serializable value)."""
    from control_panel.config_io import atomic_write_config

    target = tmp_path / "config.json"
    bad_data = {"bad": object()}  # not JSON-serializable

    with pytest.raises(TypeError):
        atomic_write_config(str(target), bad_data)

    # No .tmp files should remain
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"Found leftover temp files: {tmp_files}"


# ---------------------------------------------------------------------------
# test_atomic_write_temp_in_same_dir
# ---------------------------------------------------------------------------
def test_atomic_write_temp_in_same_dir(tmp_path):
    """atomic_write_config temp file is created in same directory as target (not system temp)."""
    from control_panel.config_io import atomic_write_config

    target = tmp_path / "config.json"
    data = {"test": True}

    real_mkstemp = __import__("tempfile").mkstemp

    with patch("tempfile.mkstemp", wraps=real_mkstemp) as mock_mkstemp:
        atomic_write_config(str(target), data)

    mock_mkstemp.assert_called_once()
    call_kwargs = mock_mkstemp.call_args[1]
    # The dir= argument should be the parent directory of the target file
    assert call_kwargs.get("dir") == str(tmp_path)


# ---------------------------------------------------------------------------
# test_load_config_reads_file
# ---------------------------------------------------------------------------
def test_load_config_reads_file(tmp_path):
    """load_config reads config.json and returns dict with correct contents."""
    from control_panel.config_io import load_config

    config_file = tmp_path / "config.json"
    expected = {"layout": {"display": {"width": 1920, "height": 515}}, "widgets": []}
    config_file.write_text(json.dumps(expected), encoding="utf-8")

    result = load_config(str(config_file))
    assert result == expected


# ---------------------------------------------------------------------------
# test_load_config_returns_default_when_missing
# ---------------------------------------------------------------------------
def test_load_config_returns_default_when_missing(tmp_path):
    """load_config returns default config dict when file does not exist."""
    from control_panel.config_io import load_config

    nonexistent = tmp_path / "does_not_exist.json"
    result = load_config(str(nonexistent))

    assert "layout" in result
    assert "widgets" in result
