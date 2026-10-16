"""Render wiring SVGs to PNG with headless Edge or Chrome (no Python packages needed).

Run:  python tools/render_png.py              -> every */docs/*.svg in the repo
      python tools/render_png.py a.svg b.svg  -> only these
The PNG has the SVG's own width x height.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = [
    os.environ.get("BROWSER_BIN", ""),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    shutil.which("chromium") or "", shutil.which("google-chrome") or "", shutil.which("chrome") or "",
]


def browser():
    for c in CANDIDATES:
        if c and Path(c).exists():
            return c
    raise SystemExit("no Edge/Chrome found: set BROWSER_BIN")


def render(svg, exe):
    head = svg.read_text(encoding="utf-8")[:400]
    w, h = (int(v) for v in re.search(r'width="(\d+)" height="(\d+)"', head).groups())
    png = svg.resolve().with_suffix(".png")
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
                        "--force-device-scale-factor=1", f"--window-size={w},{h}", f"--screenshot={png}",
                        svg.resolve().as_uri()], check=True, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"{png.relative_to(ROOT)}  {w}x{h}")


def main():
    exe = browser()
    svgs = [Path(a).resolve() for a in sys.argv[1:]] or sorted(ROOT.glob("*/docs/*.svg"))
    for svg in svgs:
        render(svg, exe)


if __name__ == "__main__":
    main()
