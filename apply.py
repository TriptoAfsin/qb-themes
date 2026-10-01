"""Switch qBittorrent (Windows) to one of these themes. Quit qBittorrent first (File > Exit),
because it rewrites its settings file on exit.

    python apply.py nocturne-blue   # enable a theme (backs up qBittorrent.ini once)
    python apply.py --revert        # restore the backup
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
APPDATA = Path(os.environ["APPDATA"]) / "qBittorrent"
INI = APPDATA / "qBittorrent.ini"
BACKUP = APPDATA / "qBittorrent.ini.pre-qb-themes.bak"


def set_key(text: str, section: str, key: str, value: str) -> str:
    header = f"[{section}]"
    if header not in text:
        return text.rstrip("\n") + f"\n\n{header}\n{key}={value}\n"
    start = text.index(header) + len(header)
    nxt = re.search(r"^\[", text[start:], flags=re.M)
    end = start + nxt.start() if nxt else len(text)
    body = text[start:end]
    line = re.compile(rf"^{re.escape(key)}=.*$", flags=re.M)
    body = line.sub(lambda _: f"{key}={value}", body) if line.search(body) else body.rstrip("\n") + f"\n{key}={value}\n\n"
    return text[:start] + body + text[end:]


def qbittorrent_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq qbittorrent.exe"], capture_output=True, text=True).stdout
    return "qbittorrent.exe" in out.lower()


if len(sys.argv) != 2:
    sys.exit(__doc__)
if qbittorrent_running():
    sys.exit("qBittorrent is running. Quit it with File > Exit, then run this again.")

if sys.argv[1] == "--revert":
    shutil.copy2(BACKUP, INI)
    sys.exit(f"Restored {INI}")

theme = ROOT / "dist" / f"{sys.argv[1]}.qbtheme"
if not theme.exists():
    sys.exit(f"No such theme: {theme.name}. Available: {', '.join(p.stem for p in (ROOT / 'dist').glob('*.qbtheme'))}")

if not BACKUP.exists():
    shutil.copy2(INI, BACKUP)
text = INI.read_text(encoding="utf-8")
text = set_key(text, "Preferences", r"General\UseCustomUITheme", "true")
text = set_key(text, "Preferences", r"General\CustomUIThemePath", theme.resolve().as_posix())
text = set_key(text, "Appearance", "Style", "Fusion")
text = set_key(text, "Appearance", "ColorScheme", "Dark")
INI.write_text(text, encoding="utf-8")
print(f"{theme.stem} enabled. Start qBittorrent to see it. Backup: {BACKUP}")
