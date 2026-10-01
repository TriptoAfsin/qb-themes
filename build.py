"""Build every theme in ./themes into a portable .qbtheme file.

    python build.py                 # all themes -> dist/<id>.qbtheme
    python build.py nocturne-blue   # just one

Needs Qt's `rcc` to pack the resource file: `pip install PySide6-Essentials`
(found automatically), or pass --rcc <path>.
Icons are Lucide (ISC) glyphs, recoloured per theme and cached in ./.cache.
"""

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
LUCIDE_VERSION = "1.49.0"
LUCIDE_URL = f"https://unpkg.com/lucide-static@{LUCIDE_VERSION}/icons/{{}}.svg"

# qBittorrent icon id -> (lucide glyph, colour token, filled)
ICONS = {
    # toolbar & actions
    "list-add":               ("plus", "icon", False),
    "insert-link":            ("link", "icon", False),
    "list-remove":            ("trash-2", "red", False),
    "torrent-start":          ("play", "accent", True),
    "torrent-start-forced":   ("fast-forward", "accent", True),
    "torrent-stop":           ("square", "icon", True),
    "configure":              ("settings", "icon", False),
    "torrent-creator":        ("file-plus", "icon", False),
    "torrent-magnet":         ("magnet", "icon", False),
    "application-exit":       ("power", "icon", False),
    "system-log-out":         ("log-out", "icon", False),
    "pause-session":          ("circle-pause", "icon", False),
    "force-recheck":          ("list-checks", "icon", False),
    "reannounce":             ("radio-tower", "icon", False),
    "set-location":           ("folder-input", "icon", False),
    "edit-rename":            ("pencil", "icon", False),
    "edit-copy":              ("copy", "icon", False),
    "edit-clear":             ("x", "icon", False),
    "edit-find":              ("search", "icon", False),
    "view-refresh":           ("refresh-cw", "icon", False),
    "view-preview":           ("eye", "icon", False),
    "view-statistics":        ("chart-column", "icon", False),
    "view-categories":        ("folder-tree", "icon", False),
    "go-top":                 ("arrow-up-to-line", "icon", False),
    "go-up":                  ("arrow-up", "icon", False),
    "go-down":                ("arrow-down", "icon", False),
    "go-bottom":              ("arrow-down-to-line", "icon", False),
    "help-about":             ("info", "icon", False),
    "help-contents":          ("circle-help", "icon", False),
    "plugins":                ("puzzle", "icon", False),
    "browser-cookies":        ("cookie", "icon", False),
    "wallet-open":            ("wallet", "icon", False),
    "mail-inbox":             ("inbox", "icon", False),
    "chart-line":             ("chart-line", "icon", False),
    "application-rss":        ("rss", "amber", False),
    "application-url":        ("link-2", "icon", False),
    "rss_read_article":       ("mail-open", "text-subtle", False),
    "rss_unread_article":     ("mail", "accent", False),

    # transfer-list row states
    "downloading":            ("circle-arrow-down", "accent", False),
    "stalledDL":              ("circle-arrow-down", "accent-dim", False),
    "stalledUP":              ("circle-arrow-up", "seed-idle", False),
    "stopped":                ("circle-stop", "done", False),
    "paused":                 ("circle-pause", "done", False),
    "queued":                 ("clock", "amber", False),
    "checked-completed":      ("circle-check", "accent", False),
    "task-complete":          ("circle-check-big", "accent", False),
    "task-reject":            ("circle-x", "red", False),
    "error":                  ("circle-x", "red", False),
    "loading":                ("loader-circle", "text-muted", False),
    "dialog-warning":         ("triangle-alert", "amber", False),

    # sidebar filters
    "filter-all":             ("layers", "icon", False),
    "filter-active":          ("zap", "accent", False),
    "filter-inactive":        ("zap-off", "text-muted", False),
    "filter-stalled":         ("hourglass", "text-muted", False),
    "download":               ("arrow-down", "accent", False),
    "upload":                 ("circle-arrow-up", "seed", False),   # also the seeding row icon
    "tags":                   ("tags", "icon", False),
    "directory":              ("folder", "icon", False),
    "folder-documents":       ("folder-open", "icon", False),
    "folder-new":             ("folder-plus", "icon", False),
    "folder-remote":          ("folder-down", "icon", False),
    "fileicon":               ("file", "icon", False),
    "name":                   ("type", "icon", False),
    "hash":                   ("hash", "icon", False),

    # trackers & peers
    "trackers":               ("radio-tower", "icon", False),
    "trackerless":            ("unlink", "text-muted", False),
    "tracker-error":          ("circle-alert", "red", False),
    "tracker-warning":        ("triangle-alert", "amber", False),
    "peers":                  ("users", "icon", False),
    "peers-add":              ("user-plus", "icon", False),
    "peers-remove":           ("user-minus", "icon", False),
    "ip-blocked":             ("ban", "red", False),
    "ratio":                  ("scale", "icon", False),

    # status bar & connectivity
    "connected":              ("globe", "accent", False),
    "disconnected":           ("unplug", "red", False),
    "firewalled":             ("shield-alert", "amber", False),
    "network-connect":        ("network", "icon", False),
    "network-server":         ("server", "icon", False),
    "speedometer":            ("gauge", "icon", False),
    "slow":                   ("gauge", "amber", False),
    "slow_off":               ("gauge", "text-muted", False),
    "object-locked":          ("lock", "icon", False),
    "security-high":          ("shield-check", "accent", False),
    "security-low":           ("shield-off", "amber", False),

    # options dialog pages
    "preferences-desktop":    ("monitor", "icon", False),
    "preferences-bittorrent": ("waypoints", "icon", False),
    "preferences-advanced":   ("sliders-horizontal", "icon", False),
    "preferences-webui":      ("app-window", "icon", False),
}

# Small widget glyphs referenced by the stylesheet (24x24 viewBox, stroke-drawn).
UI_GLYPHS = {
    "check":            ('<path d="M20 6 9 17l-5-5"/>', "text"),
    "check-ink":        ('<path d="M20 6 9 17l-5-5"/>', "accent-ink"),
    "dash":             ('<path d="M6 12h12"/>', "accent"),
    "dot":              ('<circle cx="12" cy="12" r="5" fill="{c}" stroke="none"/>', "accent"),
    "chevron-right":    ('<path d="m9 18 6-6-6-6"/>', "text-muted"),
    "chevron-down":     ('<path d="m6 9 6 6 6-6"/>', "text-muted"),
    "chevron-down-dim": ('<path d="m6 9 6 6 6-6"/>', "text-subtle"),
    "chevron-up":       ('<path d="m18 15-6-6-6 6"/>', "text-muted"),
    "x":                ('<path d="M18 6 6 18M6 6l12 12"/>', "text-muted"),
    "sort-up":          ('<path d="m18 15-6-6-6 6"/>', "accent"),
    "sort-down":        ('<path d="m6 9 6 6 6-6"/>', "accent"),
}

# qBittorrent colour id -> token
THEME_COLORS = {
    "Log.TimeStamp": "text-subtle",
    "Log.Normal": "text",
    "Log.Info": "seed",
    "Log.Warning": "amber",
    "Log.Critical": "red",
    "Log.BannedPeer": "red",
    "RSS.ReadArticle": "text-subtle",
    "RSS.UnreadArticle": "text",

    # Active rows pop; the long tail of idle seeds stays calm.
    "TransferList.Downloading": "accent",
    "TransferList.StalledDownloading": "accent-dim",
    "TransferList.DownloadingMetadata": "accent",
    "TransferList.ForcedDownloadingMetadata": "accent",
    "TransferList.ForcedDownloading": "accent",
    "TransferList.Uploading": "seed",
    "TransferList.StalledUploading": "seed-idle",
    "TransferList.ForcedUploading": "seed",
    "TransferList.QueuedDownloading": "amber",
    "TransferList.QueuedUploading": "amber",
    "TransferList.CheckingDownloading": "accent-dim",
    "TransferList.CheckingUploading": "accent-dim",
    "TransferList.CheckingResumeData": "accent-dim",
    "TransferList.StoppedDownloading": "done",
    "TransferList.StoppedUploading": "done",
    "TransferList.Moving": "accent-dim",
    "TransferList.MissingFiles": "red",
    "TransferList.Error": "red",

    "PiecesBar.Border": "line-strong",
    "PiecesBar.Piece": "accent-fill",
    "PiecesBar.PartialPiece": "seed",
    "PiecesBar.MissingPiece": "bg-2",
    "ProgressBar": "accent-fill",

    "Palette.Window": "bg-0",
    "Palette.WindowText": "text",
    "Palette.Base": "bg-1",
    "Palette.AlternateBase": "bg-1-alt",
    "Palette.Text": "text",
    "Palette.ToolTipBase": "bg-2",
    "Palette.ToolTipText": "text",
    "Palette.BrightText": "text",
    "Palette.Highlight": "accent-tint",
    "Palette.HighlightedText": "text",
    "Palette.Button": "bg-2",
    "Palette.ButtonText": "text",
    "Palette.Link": "seed",
    "Palette.LinkVisited": "seed-idle",
    "Palette.Light": "line-strong",
    "Palette.Midlight": "bg-3",
    "Palette.Mid": "bg-2",
    "Palette.Dark": "bg-0",
    "Palette.Shadow": "bg-0",
    "Palette.WindowTextDisabled": "text-subtle",
    "Palette.TextDisabled": "text-subtle",
    "Palette.ToolTipTextDisabled": "text-subtle",
    "Palette.BrightTextDisabled": "text-subtle",
    "Palette.HighlightedTextDisabled": "text-subtle",
    "Palette.ButtonTextDisabled": "text-subtle",
}


def to_hex(value: str) -> str:
    if value.startswith("#"):
        return value.lower()
    m = re.fullmatch(r"oklch\(\s*([\d.]+)%\s+([\d.]+)\s+([\d.]+)\s*\)", value.strip())
    if not m:
        raise ValueError(f"not an oklch() value: {value}")
    L, C, H = float(m[1]) / 100, float(m[2]), math.radians(float(m[3]))
    a, b = C * math.cos(H), C * math.sin(H)
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )

    def encode(x: float) -> int:
        x = min(max(x, 0.0), 1.0)
        x = 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
        return round(x * 255)

    return "#{:02x}{:02x}{:02x}".format(*(encode(c) for c in rgb))


def lucide(name: str) -> str:
    cache = ROOT / ".cache" / LUCIDE_VERSION / f"{name}.svg"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(LUCIDE_URL.format(name)) as r:
            cache.write_bytes(r.read())
    return cache.read_text(encoding="utf-8")


def recolour(svg: str, colour: str, filled: bool) -> str:
    svg = re.sub(r"<!--.*?-->\s*", "", svg, flags=re.S)
    svg = re.sub(r'\s*class="[^"]*"', "", svg)
    svg = svg.replace('stroke="currentColor"', f'stroke="{colour}"')
    if filled:
        svg = svg.replace('fill="none"', f'fill="{colour}"', 1)
    return svg


def ui_glyph(body: str, colour: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{colour}" stroke-width="2.5" stroke-linecap="round" '
        f'stroke-linejoin="round">{body.format(c=colour)}</svg>\n'
    )


def parse_oklch(value: str) -> tuple[float, float, float]:
    m = re.fullmatch(r"oklch\(\s*([\d.]+)%\s+([\d.]+)\s+([\d.]+)\s*\)", value.strip())
    return float(m[1]), float(m[2]), float(m[3])


def load_tokens(theme_id: str) -> tuple[str, dict]:
    spec = json.loads((ROOT / "themes" / f"{theme_id}.json").read_text(encoding="utf-8"))
    tokens = {}
    if "extends" in spec:
        tokens.update(load_tokens(spec["extends"])[1])
    tokens.update(spec["tokens"])
    # Variants only name an accent; derive the rest of its family at fixed lightness steps.
    if "accent-fill" not in tokens and tokens.get("accent", "").startswith("oklch"):
        _, c, h = parse_oklch(tokens["accent"])
        tokens.setdefault("accent-dim", f"oklch(66% {c * 0.60:.3f} {h})")
        tokens.setdefault("accent-fill", f"oklch(58% {c * 0.77:.3f} {h})")
        tokens.setdefault("accent-tint", f"oklch(30% 0.050 {h})")
        tokens.setdefault("accent-ink", f"oklch(20% 0.030 {h})")
    return spec.get("name", theme_id), tokens


def find_rcc(explicit: str | None) -> str:
    if explicit:
        return explicit
    try:
        import PySide6
        candidate = Path(PySide6.__file__).parent / ("rcc.exe" if sys.platform == "win32" else "Qt/libexec/rcc")
        if candidate.exists():
            return str(candidate)
    except ImportError:
        pass
    found = shutil.which("rcc")
    if not found:
        sys.exit("rcc not found: pip install PySide6-Essentials, or pass --rcc <path>")
    return found


def build(theme_id: str, rcc: str) -> Path:
    name, raw = load_tokens(theme_id)
    tokens = {k: to_hex(v) for k, v in raw.items()}
    stage = ROOT / "build" / theme_id
    shutil.rmtree(stage, ignore_errors=True)
    (stage / "icons").mkdir(parents=True)
    (stage / "ui").mkdir()

    for qbt_id, (glyph, token, filled) in ICONS.items():
        (stage / "icons" / f"{qbt_id}.svg").write_text(recolour(lucide(glyph), tokens[token], filled), encoding="utf-8")
    for glyph_name, (glyph_body, token) in UI_GLYPHS.items():
        (stage / "ui" / f"{glyph_name}.svg").write_text(ui_glyph(glyph_body, tokens[token]), encoding="utf-8")

    # qBittorrent mounts a .qbtheme at :/uitheme, so stylesheet images resolve there.
    qss = (ROOT / "src" / "stylesheet.template.qss").read_text(encoding="utf-8")
    qss = qss.replace("{{DIR}}", ":/uitheme").replace("{{THEME_NAME}}", name).replace("{{THEME_ID}}", theme_id)
    qss = re.sub(r"\{\{([\w-]+)\}\}", lambda m: tokens[m[1]], qss)
    (stage / "stylesheet.qss").write_text(qss, encoding="utf-8")

    config = {"colors": {cid: tokens[tok] for cid, tok in THEME_COLORS.items()}}
    (stage / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    files = sorted(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file())
    entries = "".join(f"    <file>{f}</file>\n" for f in files)
    qrc = f'<RCC>\n  <qresource prefix="/">\n{entries}  </qresource>\n</RCC>\n'
    (stage / "resources.qrc").write_text(qrc, encoding="utf-8")

    out = ROOT / "dist" / f"{theme_id}.qbtheme"
    out.parent.mkdir(exist_ok=True)
    subprocess.run([rcc, "--binary", "-o", str(out), str(stage / "resources.qrc")], check=True)
    print(f"{name:<16} -> {out.relative_to(ROOT)}  ({out.stat().st_size // 1024} KB)")
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("themes", nargs="*", help="theme ids (default: all in ./themes)")
    p.add_argument("--rcc")
    args = p.parse_args()
    ids = args.themes or sorted(f.stem for f in (ROOT / "themes").glob("*.json") if not f.stem.startswith("_"))
    rcc = find_rcc(args.rcc)
    for theme_id in ids:
        build(theme_id, rcc)
