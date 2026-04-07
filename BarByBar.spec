from pathlib import Path

project_root = Path.cwd()
src_root = project_root / "src"


datas = [
    (str(src_root / "barbybar" / "assets" / "barbybar-icon.ico"), "barbybar/assets"),
    (str(src_root / "barbybar" / "assets" / "barbybar-icon.svg"), "barbybar/assets"),
]

hiddenimports = []


a = Analysis(
    ["src/barbybar/app.py"],
    pathex=[str(src_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BarByBar",
    icon=str(src_root / "barbybar" / "assets" / "barbybar-icon.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BarByBar",
)
