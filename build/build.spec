# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AI Recruitment System.
Produces a single-folder dist/ARS/ containing the .exe and all runtime deps.

Usage:
    pip install pyinstaller
    pyinstaller build/build.spec
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
# ROOT is the project root — one level above this spec file (which is in build/)
ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

# ── Collect hidden imports that PyInstaller misses ──
hidden = (
    collect_submodules('mediapipe') +
    collect_submodules('google.auth') +
    collect_submodules('ollama') +
    collect_submodules('httpx') +
    collect_submodules('httpcore') +
    collect_submodules('vosk') +
    collect_submodules('pyttsx3.drivers') +
    [
        'anyio._backends._asyncio',
        'google.oauth2.credentials',
        'google_auth_oauthlib.flow',
        'googleapiclient.discovery',
        'googleapiclient.errors',
        'googleapiclient.http',
        'googleapiclient.model',
        'speech_recognition',
    ]
)

# ── Data files to embed inside the exe folder ──
# Find vosk package directory (has native DLLs that cffi loads at runtime)
import importlib
_vosk_dir = os.path.dirname(importlib.import_module('vosk').__file__)

datas = [
    # Templates & static assets (Flask needs these at runtime)
    (os.path.join(ROOT, 'app/templates'),   'app/templates'),
    (os.path.join(ROOT, 'app/static'),      'app/static'),
    # Google Calendar credentials (if present)
]
if os.path.exists(os.path.join(ROOT, 'credentials.json')):
    datas.append((os.path.join(ROOT, 'credentials.json'), '.'))

# Vosk native DLLs + Python files (cffi-based, PyInstaller can't trace)
datas.append((_vosk_dir, 'vosk'))
# Collect mediapipe model data that PyInstaller won't find
datas += collect_data_files('mediapipe')

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT, os.path.join(ROOT, 'app'), os.path.join(ROOT, 'src')],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'notebook',
        'IPython',
        'config',
        'pytest',
        'py',
        'anyio.pytest_plugin',
        'googleapiclient.discovery_cache.documents',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

def _keep_data(entry):
    dest = entry[0].replace('/', '\\')
    if dest.startswith('googleapiclient\\discovery_cache\\documents\\'):
        return False
    if dest.startswith('speech_recognition\\pocketsphinx-data\\'):
        return False
    if dest in {
        'speech_recognition\\flac-linux-x86',
        'speech_recognition\\flac-linux-x86_64',
        'speech_recognition\\flac-mac',
    }:
        return False
    return True


a.datas = [entry for entry in a.datas if _keep_data(entry)]

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
    icon=os.path.join(ROOT, 'app/static/icon/ai.ico'),
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
