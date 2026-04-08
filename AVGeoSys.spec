# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for AVGeoSys — onedir mode (startup muito mais rápido)

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['avgeosys/ui/tkinter_ui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('rnx2rtkp.exe', '.'),
        ('AVGeoSysIcon.ico', '.'),
        ('avgeosys/credentials/gdrive.json', 'credentials'),
    ],
    hiddenimports=[
        'piexif',
        'simplekml',
        'pandas',
        'numpy',
        'folium',
        'branca',
        'google.auth',
        'google.oauth2.credentials',
        'google.auth.transport.requests',
        'googleapiclient.discovery',
        'googleapiclient.http',
        'httplib2',
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
    name='AVGeoSys',
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
    icon='AVGeoSysIcon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AVGeoSys',
)
