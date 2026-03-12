# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AI Recruitment System.
Produces a single-folder dist/ARS/ containing the .exe and all runtime deps.

Usage:
    pip install pyinstaller
    pyinstaller build.spec
"""

import os, sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
ROOT = os.path.abspath('.')

# ── Collect hidden imports that PyInstaller misses ──
hidden = (
    collect_submodules('mediapipe') +
    collect_submodules('google.auth') +
    collect_submodules('google_auth_oauthlib') +
    collect_submodules('googleapiclient') +
    collect_submodules('vosk') +
    collect_submodules('speech_recognition') +
    collect_submodules('pyttsx3.drivers')
)

# ── Data files to embed inside the exe folder ──
# Find vosk package directory (has native DLLs that cffi loads at runtime)
import importlib
_vosk_dir = os.path.dirname(importlib.import_module('vosk').__file__)
_sr_dir = os.path.dirname(importlib.import_module('speech_recognition').__file__)

datas = [
    # Templates & static assets (Flask needs these at runtime)
    ('templates',       'templates'),
    ('static',          'static'),
    # Config (will be editable after install)
    ('config.py',       '.'),
    # Google Calendar credentials (if present)
]
if os.path.exists('credentials.json'):
    datas.append(('credentials.json', '.'))

# Vosk native DLLs + Python files (cffi-based, PyInstaller can't trace)
datas.append((_vosk_dir, 'vosk'))
# speech_recognition data files (flac binaries, pocketsphinx-data, etc.)
datas.append((_sr_dir, 'speech_recognition'))

# Collect mediapipe model data that PyInstaller won't find
datas += collect_data_files('mediapipe')

a = Analysis(
    ['app.py'],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'notebook', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],                   # NOT one-file — we use COLLECT below
    exclude_binaries=True,
    name='ARS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,        # No console window (pywebview provides the GUI)
    icon='static/icon/ai.ico',
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
