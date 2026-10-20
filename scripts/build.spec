# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

include_creds = os.environ.get("BUNDLE_CREDS", "0") == "1"

vosk_datas = collect_data_files('vosk')
vosk_binaries = collect_dynamic_libs('vosk')

try:
    mediapipe_datas = collect_data_files('mediapipe')
    mediapipe_binaries = collect_dynamic_libs('mediapipe')
except Exception:
    mediapipe_datas = []
    mediapipe_binaries = []

my_datas = [
    ('../app', 'app'),
    ('../src', 'src'),
    ('../config', 'config'),
    ('../media', 'media'),
    ('../models', 'models')
] + vosk_datas + mediapipe_datas

my_binaries = vosk_binaries + mediapipe_binaries

if include_creds and os.path.exists('../credentials.json'):
    my_datas.append(('../credentials.json', '.'))

a = Analysis(
    ['../main.py'],
    pathex=[],
    binaries=my_binaries,
    datas=my_datas,
    hiddenimports=[
        'waitress',
        'flask',
        'webview',
        'pydantic',
        'sqlalchemy',
        'pypdf',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'googleapiclient.discovery',
        'google.oauth2.credentials',
        'pyttsx3.drivers',
        'pyttsx3.drivers.sapi5',
        'speech_recognition',
        'vosk',
        'mediapipe',
        'mediapipe.tasks',
        'mediapipe.tasks.python',
        'mediapipe.tasks.python.vision',
        'mediapipe.tasks.python.vision.face_detector',
        'cv2',
        'fpdf',
        'fpdf2',
        'docx',
        'pytesseract',
        'PIL',
        'icalendar',
        'ollama',
        'anthropic',
        'comtypes',
        'comtypes.client',
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
    entitlements_file=None,
    icon='../app/static/icon/ai.ico'
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
