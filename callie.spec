# -*- mode: python ; coding: utf-8 -*-
# Builds the desktop app:  pyinstaller --noconfirm callie.spec
import sys
from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("uvicorn") + collect_submodules("websockets")
for extra in ("httptools", "h11", "dotenv", "anyio"):
    try:
        hidden += collect_submodules(extra)
    except Exception:
        pass

a = Analysis(["desktop/main.py"], pathex=["."], binaries=[],
             datas=[("client/pwa", "client/pwa"), ("VERSION", ".")],
             hiddenimports=hidden, excludes=["tkinter", "pytest", "scipy", "matplotlib", "PIL"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Callie", console=(sys.platform != "win32"),
          icon="client/pwa/icons/callie.ico" if sys.platform == "win32" else None, upx=False)
