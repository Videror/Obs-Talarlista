"""Boden Kommunfullmäktige Kontrollpanel.

Dubbelklicka på exe-filen och klicka på den som talar eller på en
textruta. Appen skriver vad som ska visas till data/aktuell_visning.json,
och overlay.html (en webbläsarkälla med "Lokal fil" i OBS) läser av filen
flera gånger i sekunden.

Själva kontrollpanelen (control.html) är inbakad i exe-filen. Allt som går
att ändra – listor, textrutor, ikoner, partier.js och overlay.html – ligger
i programmets mapp bredvid exe-filen.

Kör utan exe med:  python app.py   (använder programmappen bredvid källkod/)
Bygg om exe-filen med bygg_app.bat om du ändrar i källkoden.
"""

import filecmp
import json
import mimetypes
import os
import re
import shutil
import sys
import threading
import time

import webview

APP_NAME = "Boden Kommunfullmäktige Kontrollpanel"

if getattr(sys, "frozen", False):
    # Exe: programmappen är där exe-filen ligger, de inbakade filerna
    # packas upp i en tillfällig mapp.
    ROOT = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE = sys._MEIPASS
else:
    # Utveckling: källkod/app.py använder programmappen bredvid.
    BUNDLE = os.path.dirname(os.path.abspath(__file__))
    ROOT = os.path.join(os.path.dirname(BUNDLE), APP_NAME)

CONTROL_FILE = os.path.join(BUNDLE, "control.html")
# Filer och mappar som återskapas från exe-filen om de saknas i programmappen.
RESTORABLE = ["overlay.html", "partier.js", "ikoner"]
# Enskilda filer som alltid ska finnas, även i en ikonmapp från en äldre version.
REQUIRED_FILES = ["ikoner/bodens-kommun-vapen.png"]

DATA_DIR = os.path.join(ROOT, "data")
DISPLAY_FILE = os.path.join(DATA_DIR, "aktuell_visning.json")
UI_FILE = os.path.join(DATA_DIR, "installningar.json")
# Bilder och videor till pausskärmen kopieras hit så att de följer med
# programmappen, t.ex. till en USB-sticka.
MEDIA_DIR = os.path.join(ROOT, "paus")
MAX_NAME = 80
MAX_TEXT = 400
MAX_PAUSE_TEXT = 300

PAUSE_DEFAULTS = {
    "visible": False,
    "text": "Paus – sändningen fortsätter strax",
    "textSize": 64,
    "textY": 72,
    "textBox": False,
    "textBoxOpacity": 60,
    "logo": "ikoner/bodens-kommun-vapen.png",
    "logoSize": 260,
    "logoY": 40,
    "background": "",
    "zoom": 100,
    "blur": False,
    "blurAmount": 14,
}
# Tillåtna värden för reglagen: (minsta, största).
PAUSE_LIMITS = {
    "textSize": (12, 240),
    "textY": (0, 100),
    "textBoxOpacity": (0, 100),
    "logoSize": (20, 1000),
    "logoY": (0, 100),
    "zoom": (100, 400),
    "blurAmount": (0, 60),
}
PAUSE_SWITCHES = ("visible", "blur", "textBox")
FILE_TYPES = {
    "logo": ("Bilder (*.png;*.jpg;*.jpeg;*.gif;*.webp;*.svg)",),
    "background": ("Bilder och video (*.png;*.jpg;*.jpeg;*.gif;*.webp;*.mp4;*.webm;*.mov;*.m4v)",),
}

# De två sorters listor som appen hanterar.
KINDS = {
    "talare": {
        "folder": "listor",
        "field": "talare",
        "session": "senaste_talare.json",
    },
    "textrutor": {
        "folder": "textrutor",
        "field": "textrutor",
        "session": "senaste_textrutor.json",
    },
}


def read_json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path, data):
    """Skriver först till en tillfällig fil så att OBS aldrig läser en halv fil."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # OBS kan ha filen öppen ett ögonblick medan den läses.
    for _ in range(25):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.02)
    os.replace(tmp, path)


def kind_info(kind):
    if kind not in KINDS:
        raise ValueError(f"Okänd listtyp: {kind}")
    return KINDS[kind]


def kind_folder(kind):
    return os.path.join(ROOT, kind_info(kind)["folder"])


def safe_file_name(name):
    """Gör om ett listnamn till ett säkert filnamn, t.ex. 'KF oktober.json'."""
    name = re.sub(r"[^\w\s\-().,]", "", str(name), flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip(" .")[:60]
    return (name or "Lista") + ".json"


def list_path(kind, file_name):
    """Returnerar sökvägen i listans mapp, eller None om namnet är ogiltigt."""
    if not isinstance(file_name, str) or not file_name.lower().endswith(".json"):
        return None
    if safe_file_name(file_name[:-5]) != file_name:
        return None
    return os.path.join(kind_folder(kind), file_name)


def inside_root(path):
    """True om sökvägen ligger i programmappen."""
    root = os.path.realpath(ROOT)
    try:
        return os.path.commonpath([os.path.realpath(path), root]) == root
    except ValueError:  # t.ex. en annan enhet
        return False


def relative_media_path(value):
    """Godkänner bara relativa sökvägar inom programmappen, t.ex. 'paus/bild.jpg'."""
    if not isinstance(value, str):
        return None
    value = value.replace("\\", "/").strip()
    if value == "":
        return ""
    if os.path.isabs(value) or ".." in value.split("/"):
        return None
    return value


def clean_pause(current, changes):
    """Slår ihop nya pausinställningar med de gamla och kontrollerar värdena."""
    result = dict(current)
    for key, value in (changes or {}).items():
        if key not in PAUSE_DEFAULTS:
            continue
        if key in PAUSE_LIMITS:
            low, high = PAUSE_LIMITS[key]
            try:
                value = min(high, max(low, int(round(float(value)))))
            except (TypeError, ValueError):
                continue
        elif key in PAUSE_SWITCHES:
            value = bool(value)
        elif key == "text":
            value = str(value)[:MAX_PAUSE_TEXT]
        else:
            value = relative_media_path(value)
            if value is None:
                continue
        result[key] = value
    return result


def import_media(source):
    """Kopierar en vald fil till mappen paus och returnerar den relativa sökvägen.

    Filer som redan ligger i programmappen används där de är.
    """
    if inside_root(source):
        return os.path.relpath(source, ROOT).replace("\\", "/")

    os.makedirs(MEDIA_DIR, exist_ok=True)
    base, ext = os.path.splitext(os.path.basename(source))
    target = os.path.join(MEDIA_DIR, base + ext)
    number = 2
    # Samma fil igen återanvänds, en annan fil med samma namn får ett nummer.
    while os.path.exists(target) and not filecmp.cmp(source, target, shallow=True):
        target = os.path.join(MEDIA_DIR, f"{base} ({number}){ext}")
        number += 1
    if not os.path.exists(target):
        shutil.copy2(source, target)
    return os.path.relpath(target, ROOT).replace("\\", "/")


class Api:
    """Funktionerna som kontrollpanelen (control.html) anropar."""

    def __init__(self):
        self._lock = threading.Lock()
        self._window = None  # Sätts i main(), behövs för fildialogen.
        self._display = {
            "talare": {"name": "", "party": ""},
            "textruta": {"text": ""},
            "installningar": {"autoBredd": True, "datum": ""},
            "paus": dict(PAUSE_DEFAULTS),
        }
        try:
            saved = read_json(DISPLAY_FILE)
            for key in ("talare", "textruta", "installningar"):
                if isinstance(saved.get(key), dict):
                    self._display[key].update(saved[key])
            self._display["paus"] = clean_pause(PAUSE_DEFAULTS, saved.get("paus"))
        except (OSError, ValueError, AttributeError):
            pass

    # ---------- Det som visas i OBS ----------

    def _write_display(self):
        with self._lock:
            write_json(DISPLAY_FILE, {**self._display, "updatedAt": time.time()})
        return True

    def get_display(self):
        return self._display

    def set_speaker(self, name, party):
        self._display["talare"] = {"name": str(name or "")[:MAX_NAME],
                                   "party": str(party or "")[:30]}
        return self._write_display()

    def set_textbox(self, text, first=False):
        # "first" betyder att det är textruta 0, den enda som visar datumet.
        self._display["textruta"] = {"text": str(text or "")[:MAX_TEXT],
                                     "first": bool(first)}
        return self._write_display()

    def set_options(self, options):
        if isinstance(options, dict):
            if "autoBredd" in options:
                self._display["installningar"]["autoBredd"] = bool(options["autoBredd"])
            if "datum" in options:
                # Datumet längst till höger på textruta 0, skrivs för hand.
                self._display["installningar"]["datum"] = str(options["datum"] or "")[:40]
        return self._write_display()

    def set_pause(self, settings):
        self._display["paus"] = clean_pause(self._display["paus"], settings)
        self._write_display()
        return self._display["paus"]

    def clear_all(self):
        """Släcker allt i OBS. Pausskärmens inställningar sparas till nästa gång."""
        self._display["talare"] = {"name": "", "party": ""}
        self._display["textruta"] = {"text": ""}
        self._display["paus"]["visible"] = False
        return self._write_display()

    # ---------- Pausskärmens filer ----------

    def choose_media(self, kind):
        """Låter användaren bläddra fram en logga eller bakgrund.

        Returnerar {"path": ...}, {"fel": ...} eller None om man avbröt.
        """
        if kind not in FILE_TYPES or self._window is None:
            return None
        chosen = self._window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=FILE_TYPES[kind])
        if not chosen:
            return None
        source = chosen[0] if isinstance(chosen, (list, tuple)) else chosen
        try:
            return {"path": import_media(source)}
        except OSError as error:
            return {"fel": f"Kunde inte kopiera filen: {error}"}

    def media_exists(self, path):
        """True om en vald logga/bakgrund fortfarande finns i programmappen."""
        rel = relative_media_path(path)
        if not rel:
            return False
        full = os.path.join(ROOT, rel)
        return inside_root(full) and os.path.isfile(full)

    # ---------- Appens egna inställningar (dolda sektioner m.m.) ----------

    def load_ui(self):
        try:
            data = read_json(UI_FILE)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_ui(self, data):
        if isinstance(data, dict):
            write_json(UI_FILE, {k: v for k, v in data.items() if isinstance(v, bool)})
        return True

    # ---------- Senaste listan (sparas automatiskt) ----------

    def load_session(self, kind):
        try:
            return read_json(os.path.join(DATA_DIR, kind_info(kind)["session"]))
        except (OSError, ValueError):
            return None

    def save_session(self, kind, data):
        write_json(os.path.join(DATA_DIR, kind_info(kind)["session"]), data)
        return True

    # ---------- Sparade listor ----------

    def list_lists(self, kind):
        """Alla sparade listor av en sort, nyast först."""
        folder = kind_folder(kind)
        field = kind_info(kind)["field"]
        os.makedirs(folder, exist_ok=True)
        items = []
        for entry in os.scandir(folder):
            if not entry.is_file() or not entry.name.lower().endswith(".json"):
                continue
            title, count = entry.name[:-5], 0
            try:
                data = read_json(entry.path)
                if isinstance(data, dict):
                    title = data.get("namn") or title
                    count = len(data.get(field) or [])
                elif isinstance(data, list):
                    count = len(data)
            except (OSError, ValueError):
                pass
            items.append({
                "fil": entry.name,
                "namn": title,
                "antal": count,
                "andrad": entry.stat().st_mtime,
            })
        items.sort(key=lambda i: i["andrad"], reverse=True)
        return items

    def open_list(self, kind, file_name):
        path = list_path(kind, file_name)
        if not path or not os.path.isfile(path):
            return {"fel": "Listan finns inte."}
        try:
            return {"data": read_json(path)}
        except ValueError:
            return {"fel": "Filen innehåller ett fel."}

    def save_list(self, kind, data):
        field = kind_info(kind)["field"]
        if not isinstance(data, dict) or not isinstance(data.get(field), list):
            return {"fel": "Det här är ingen giltig lista."}
        folder = kind_folder(kind)
        os.makedirs(folder, exist_ok=True)
        file_name = safe_file_name(data.get("namn") or "Lista")
        path = os.path.join(folder, file_name)
        existed = os.path.exists(path)
        write_json(path, data)
        return {"fil": file_name, "ersatt": existed}

    def open_list_folder(self, kind):
        folder = kind_folder(kind)
        os.makedirs(folder, exist_ok=True)
        os.startfile(folder)
        return True


def request_path(environ):
    """Sökvägen i förfrågan, med å, ä och ö rätt avkodade.

    Webbservern har redan avkodat %-tecknen men lämnar texten som latin-1
    (så säger WSGI-standarden), så "ä" kommer fram som "Ã¤". Gör om till
    riktig UTF-8 igen.
    """
    raw = environ.get("PATH_INFO") or "/"
    try:
        return raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw


def web_app(environ, start_response):
    """Visar kontrollpanelen i appens fönster.

    Själva sidan kommer inifrån exe-filen, medan partier.js och ikonerna
    hämtas från programmappen så att de går att ändra.
    """
    path = request_path(environ)
    if path in ("/", "/control.html"):
        file = CONTROL_FILE
    else:
        file = os.path.join(ROOT, path.lstrip("/"))
        # Lämna aldrig ut filer utanför programmappen.
        if not inside_root(file) or not os.path.isfile(file):
            start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
            return ["Filen finns inte.".encode("utf-8")]

    content_type = mimetypes.guess_type(file)[0] or "application/octet-stream"
    if content_type.startswith("text/") or content_type.endswith("javascript"):
        content_type += "; charset=utf-8"
    headers = [
        ("Content-Type", content_type),
        ("Accept-Ranges", "bytes"),
        ("Cache-Control", "no-store"),
    ]

    # Videor hämtas i delar ("Range"), annars går de inte att spola och loopa.
    size = os.path.getsize(file)
    start, end, status = 0, size - 1, "200 OK"
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", environ.get("HTTP_RANGE", "").strip())
    if match and size and match.group(1) + match.group(2):
        first, last = match.groups()
        if first:
            start = int(first)
            end = min(int(last), size - 1) if last else size - 1
        else:  # "bytes=-500" betyder de sista 500 byten
            start = max(0, size - int(last))
        if start > end:
            start_response("416 Range Not Satisfiable", [("Content-Range", f"bytes */{size}")])
            return [b""]
        status = "206 Partial Content"
        headers.append(("Content-Range", f"bytes {start}-{end}/{size}"))

    length = max(0, end - start + 1)
    headers.append(("Content-Length", str(length)))
    start_response(status, headers)
    return read_chunks(file, start, length)


def read_chunks(path, start, length, chunk_size=256 * 1024):
    """Läser en fil bit för bit så att stora videor inte läses in i minnet."""
    with open(path, "rb") as f:
        f.seek(start)
        while length > 0:
            data = f.read(min(chunk_size, length))
            if not data:
                break
            length -= len(data)
            yield data


def prepare_folder():
    """Skapar mapparna och återställer overlay.html, partier.js och
    ikoner/ om de saknas helt. Det som redan finns rörs aldrig."""
    for folder in [DATA_DIR] + [kind_folder(kind) for kind in KINDS]:
        os.makedirs(folder, exist_ok=True)
    for name in RESTORABLE:
        source = os.path.join(BUNDLE, name)
        target = os.path.join(ROOT, name)
        if os.path.exists(target) or source == target:
            continue
        if os.path.isdir(source):
            shutil.copytree(source, target)
        elif os.path.isfile(source):
            shutil.copy2(source, target)
    # Standardloggan till pausskärmen saknas i mappar från äldre versioner.
    for name in REQUIRED_FILES:
        source = os.path.join(BUNDLE, name)
        target = os.path.join(ROOT, name)
        if not os.path.exists(target) and os.path.isfile(source):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(source, target)


def main():
    prepare_folder()

    api = Api()
    # Se till att filen finns så att overlayn har något att läsa.
    if not os.path.isfile(DISPLAY_FILE):
        api.clear_all()

    window = webview.create_window(
        APP_NAME, web_app, js_api=api,
        width=600, height=940, min_size=(380, 520),
        background_color="#151820")
    api._window = window

    # Släck allt när appen stängs, så att inget gammalt står kvar
    # nästa gång OBS startas.
    window.events.closed += api.clear_all

    webview.start()


if __name__ == "__main__":
    main()
