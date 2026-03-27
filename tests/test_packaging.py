"""Tests for Phase 7 packaging preconditions."""
import struct
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_spec_file_exists():
    """PKG-04: .spec file must be committed at build/control_panel.spec."""
    spec = PROJECT_ROOT / "build" / "control_panel.spec"
    assert spec.exists(), f"Missing: {spec}"
    content = spec.read_text()
    assert "contents_directory='.'" in content, "Spec must set contents_directory='.'"
    assert "console=False" in content, "Spec must set console=False"
    assert "icon=" in content, "Spec must set icon= parameter"


def test_icon_file_exists():
    """PKG-03: icon.ico must exist at build/icon.ico."""
    ico = PROJECT_ROOT / "build" / "icon.ico"
    assert ico.exists(), f"Missing: {ico}"


def test_icon_file_is_valid_ico():
    """PKG-03: icon.ico must be a valid ICO file with multiple sizes."""
    ico = PROJECT_ROOT / "build" / "icon.ico"
    data = ico.read_bytes()
    # ICO header: reserved(2) + type(2) + count(2)
    assert len(data) >= 6, "ICO file too small"
    reserved, ico_type, count = struct.unpack_from("<HHH", data, 0)
    assert reserved == 0, f"ICO reserved field must be 0, got {reserved}"
    assert ico_type == 1, f"ICO type must be 1 (icon), got {ico_type}"
    assert count >= 3, f"ICO must contain at least 3 sizes, got {count}"


def test_null_guard_in_control_panel_main():
    """PKG-02: control_panel/__main__.py must null-guard stdout/stderr before imports."""
    main_py = PROJECT_ROOT / "control_panel" / "__main__.py"
    content = main_py.read_text()
    lines = content.splitlines()
    # Find the null-guard and the first non-stdlib import
    guard_line = None
    first_app_import_line = None
    for i, line in enumerate(lines):
        if "sys.stdout is None" in line and guard_line is None:
            guard_line = i
        if ("from PyQt6" in line or "from control_panel" in line) and first_app_import_line is None:
            first_app_import_line = i
    assert guard_line is not None, "Missing sys.stdout null-guard"
    assert first_app_import_line is not None, "Missing app imports"
    assert guard_line < first_app_import_line, (
        f"Null-guard (line {guard_line}) must appear before app imports (line {first_app_import_line})"
    )
