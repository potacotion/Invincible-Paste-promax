# -*- mode: python ; coding: utf-8 -*-

import os

ICON_PATH = os.path.join(SPECPATH, 'assets', 'icon.ico')
VERSION_PATH = os.path.join(SPECPATH, 'version_info_receiver.txt')

a = Analysis(
    ['vm_receiver_app.py'],
    pathex=[],
    binaries=[],
    datas=[('Interception_Installer/', 'Interception_Installer/')],
    hiddenimports=[],
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
    name='虚拟机接收端_输入法模式',
    icon=ICON_PATH,
    version=VERSION_PATH,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
)
