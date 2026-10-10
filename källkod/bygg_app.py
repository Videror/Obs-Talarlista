"""Bygger Boden Kommunfullmäktige Kontrollpanel.exe.

Exe-filen hamnar i programmappen bredvid källkod/. Kontrollpanelen
(control.html) bakas in i exe-filen, liksom en reservkopia av overlay.html,
partier.js och ikoner/ som återskapas om de saknas. Programikonen tas från
ikoner/app-ikon.png i programmappen.

Kör:  python bygg_app.py   (eller dubbelklicka på bygg_app.bat)
"""

import os
import subprocess
import sys
import tempfile

APP_NAME = "Boden Kommunfullmäktige Kontrollpanel"
HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(os.path.dirname(HERE), APP_NAME)
BUILD_DIR = os.path.join(tempfile.gettempdir(), "kontrollpanel-build")


def bundled(path):
    """--add-data-argument som lägger filen i exe-filens rot."""
    return f"{path}{os.pathsep}."


def main():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet",
                           "pyinstaller", "pywebview", "pillow"])
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--onefile", "--noconsole",
        "--name", APP_NAME,
        # Pillow gör om PNG-bilden till en Windows-ikon.
        "--icon", os.path.join(APP_DIR, "ikoner", "app-ikon.png"),
        "--add-data", bundled(os.path.join(HERE, "control.html")),
        "--add-data", bundled(os.path.join(APP_DIR, "overlay.html")),
        "--add-data", bundled(os.path.join(APP_DIR, "partier.js")),
        "--add-data", f"{os.path.join(APP_DIR, 'ikoner')}{os.pathsep}ikoner",
        "--distpath", APP_DIR,
        "--workpath", BUILD_DIR,
        "--specpath", BUILD_DIR,
        os.path.join(HERE, "app.py"),
    ])
    print(f"\nKlart! {APP_NAME}.exe ligger i {APP_DIR}")


if __name__ == "__main__":
    main()
