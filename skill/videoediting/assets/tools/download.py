"""Fetch source footage from a URL (YouTube, Vimeo, a Drive/Zoom share link,
hundreds of other sites via yt-dlp) so it can be edited like any local file.

Usage: python download.py <url> <out_dir> [--audio-only] [--force]

Always lands at <out_dir>/source.mp4 (or source.<ext> for --audio-only) so the
rest of the pipeline never has to parse a filename yt-dlp chose. Re-running is
a no-op unless --force is passed — do not re-download footage you already have.
"""
import os
import shutil
import subprocess
import sys

URL = sys.argv[1] if len(sys.argv) > 1 else None
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "."
AUDIO_ONLY = "--audio-only" in sys.argv
FORCE = "--force" in sys.argv

INSTALL_HINT = """yt-dlp not found. Install it:
  Windows : winget install --id yt-dlp.yt-dlp -e
  macOS   : brew install yt-dlp
  Any OS  : pip install -U yt-dlp"""


def run(cmd):
    print(" ".join(cmd)[:300], flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(p.stdout[-2000:])
        print(p.stderr[-2000:])
        sys.exit(f"yt-dlp failed (exit {p.returncode})")
    return p.stdout


def main():
    if not URL:
        sys.exit("Usage: python download.py <url> <out_dir> [--audio-only] [--force]")

    os.makedirs(OUT_DIR, exist_ok=True)
    target = os.path.join(OUT_DIR, "source.m4a" if AUDIO_ONLY else "source.mp4")
    if os.path.exists(target) and not FORCE:
        print(f"already downloaded: {target}  (pass --force to re-fetch)")
        _report(target)
        return

    if not shutil.which("yt-dlp"):
        sys.exit(INSTALL_HINT)

    template = os.path.join(OUT_DIR, "source.%(ext)s")
    if AUDIO_ONLY:
        cmd = ["yt-dlp", "-f", "ba/bestaudio", "-x", "--audio-format", "m4a",
               "--no-playlist", "-o", template, URL]
    else:
        # up to source's native quality — editing needs headroom for crop/zoom that
        # analysis-only tools (which cap at 720p) don't need
        cmd = ["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mp4",
               "--no-playlist", "-o", template, URL]
    run(cmd)

    if not os.path.exists(target):
        # yt-dlp sometimes keeps the source extension when no merge was needed
        candidates = [f for f in os.listdir(OUT_DIR) if f.startswith("source.")]
        sys.exit(f"expected {target}, found instead: {candidates or 'nothing'}")
    _report(target)


def _report(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_name",
         "-of", "default=nw=1", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    print(f"\nOK: {path}\n{out.strip()}")


if __name__ == "__main__":
    main()
