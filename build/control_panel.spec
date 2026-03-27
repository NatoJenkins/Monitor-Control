# build/control_panel.spec
# PyInstaller 6.x spec for MonitorControl control panel
# Rebuild: pyinstaller build/control_panel.spec
# Output: dist/MonitorControl/MonitorControl.exe
import sys
from pathlib import Path

block_cipher = None
project_root = str(Path(SPECPATH).parent)

a = Analysis(
    [str(Path(project_root) / 'control_panel' / '__main__.py')],
    pathex=[project_root],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MonitorControl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(Path(project_root) / 'build' / 'icon.ico'),
    contents_directory='.',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MonitorControl',
)
