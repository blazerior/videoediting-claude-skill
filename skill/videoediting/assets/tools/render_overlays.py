"""HTML -> PNG with a transparent background, rendered by headless Chrome.

Usage: python render_overlays.py <overlays.json> <out_dir>

overlays.json:
{
  "css": "shared CSS for every card",
  "items": [ {"id": "hook", "html": "<div class='hook'>...</div>"}, ... ]
}
Each item is rendered to <out_dir>/<id>.png at 1080x1920 with alpha.
"""
import json
import os
import platform
import subprocess
import sys
import tempfile

W, H = 1080, 1920

CANDIDATES = {
    "Windows": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "Darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ],
    "Linux": ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"],
}


def find_chrome():
    for p in CANDIDATES.get(platform.system(), []):
        if os.path.exists(p):
            return p
    sys.exit("Chrome not found — install Google Chrome or edit CANDIDATES")


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:{w}px; height:{h}px; background:transparent; overflow:hidden; }}
body {{ font-family:'Bahnschrift','Segoe UI','Helvetica Neue',Arial,sans-serif; -webkit-font-smoothing:antialiased; }}
{css}
</style></head><body>{body}</body></html>"""


def main():
    spec_path, out_dir = sys.argv[1], sys.argv[2]
    chrome = find_chrome()
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    css = spec.get("css", "")

    tmpdir = tempfile.mkdtemp(prefix="ovl_")
    for item in spec["items"]:
        html_path = os.path.join(tmpdir, f"{item['id']}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(PAGE.format(w=W, h=H, css=css, body=item["html"]))
        out_png = os.path.join(out_dir, f"{item['id']}.png")
        cmd = [
            chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
            "--force-device-scale-factor=1",
            "--default-background-color=00000000",   # without this the background renders white
            f"--window-size={W},{H}",
            f"--screenshot={out_png}",
            "--virtual-time-budget=2000",
            f"file:///{html_path.replace(os.sep, '/')}",
        ]
        subprocess.run(cmd, capture_output=True, check=False)
        print(f"{'OK ' if os.path.exists(out_png) else 'FAIL'} {item['id']}.png", flush=True)


if __name__ == "__main__":
    main()
