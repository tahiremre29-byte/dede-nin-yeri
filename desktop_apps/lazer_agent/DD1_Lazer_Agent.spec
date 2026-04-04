# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main_app.py'],
    pathex=[],
    binaries=[],
    datas=[('ui_interface.py', '.'), ('ai_module.py', '.'), ('vector_module.py', '.')],
    hiddenimports=['PyQt6.QtSvgWidgets', 'PyQt6.QtSvg', 'vtracer', 'ezdxf', 'cv2', 'PIL'],
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
    a.binaries,
    a.datas,
    [],
    name='DD1_Lazer_Agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
