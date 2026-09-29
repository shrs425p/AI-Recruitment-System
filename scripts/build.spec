# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os

include_creds = os.environ.get("BUNDLE_CREDS", "0") == "1"

my_datas = [
    ('../app', 'app'),
    ('../src', 'src'),
    ('../config', 'config'),
    ('../media', 'media'),
    ('../models', 'models')
]
if include_creds and os.path.exists('../credentials.json'):
    my_datas.append(('../credentials.json', '.'))

a = Analysis(
    ['../main.py'],
    pathex=[],
    binaries=[],
    datas=my_datas,
    hiddenimports=[
        'waitress',
        'flask',
        'webview',
        'pydantic',
        'sqlalchemy',
        'fitz',
        'pymupdf',
        'googleapiclient.discovery',
        'google.oauth2.credentials',
        'pyttsx3.drivers',
        'pyttsx3.drivers.sapi5',
        'speech_recognition',
        'vosk',
        'mediapipe',
        'cv2',
        'fpdf',
        'pytesseract',
        'PIL',
        'icalendar',
        'ollama',
        'anthropic'
    ],
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
    name='ARS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ARS',
)
