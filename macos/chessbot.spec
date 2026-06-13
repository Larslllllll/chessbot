# -*- mode: python ; coding: utf-8 -*-
import os

root = os.path.abspath(os.path.join(SPECPATH, '..'))

block_cipher = None

a = Analysis(
    [os.path.join(root, 'play_chess.py')],
    pathex=[root],
    binaries=[],
    datas=[
        (os.path.join(root, 'chessbot'), 'chessbot'),
    ],
    hiddenimports=[
        'chess',
        'chess.engine',
        'chess.pgn',
        'playwright',
        'playwright.sync_api',
        'playwright.async_api',
        'asyncio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'pytest_asyncio'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='chessbot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='chessbot',
)
