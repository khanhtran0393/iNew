# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

added_files = [
    ('app/web/static', 'app/web/static'),
    ('app/web/templates', 'app/web/templates'),
]

try:
    added_files += collect_data_files('trafilatura')
except Exception:
    pass

try:
    added_files += collect_data_files('courlan')
except Exception:
    pass

try:
    added_files += collect_data_files('htmldate')
except Exception:
    pass

hidden_imports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespans',
    'uvicorn.lifespans.on',
    'fastapi',
    'starlette',
    'jinja2',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'pydantic',
    'pydantic_settings',
    'pystray',
    'PIL',
    'PIL.Image',
    'aiogram',
    'telethon',
    'anthropic',
    'yt_dlp',
    'onnxruntime',
    'sea_g2p',
    'vieneu',
    'vieneu_utils',
    'python_multipart',
    'aiofiles',
]

a = Analysis(
    ['app/launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'IPython'],
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
    name='iNew',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/web/static/img/app.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='iNew',
)
