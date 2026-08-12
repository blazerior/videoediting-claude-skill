#!/usr/bin/env bash
# Installs the videoediting skill into the user's Claude Code skills folder
# Usage: bash scripts/install.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/skill/videoediting"
DST="$HOME/.claude/skills/videoediting"

[ -d "$SRC" ] || { echo "skill/videoediting not found - run this from inside the cloned repo"; exit 1; }

echo
echo "Installing the videoediting skill"
echo

if [ -d "$DST" ]; then
  echo "  A skill already exists at $DST"
  read -r -p "  Overwrite? (y/N) " answer
  [ "$answer" = "y" ] || { echo "  Cancelled."; exit 0; }
  rm -rf "$DST"
fi

mkdir -p "$(dirname "$DST")"
cp -R "$SRC" "$DST"
find "$DST" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "  Installed to $DST"
echo
echo "Dependency check"
echo

missing=()

for t in ffmpeg ffprobe python3; do
  if command -v "$t" >/dev/null 2>&1; then
    echo "  [ok]      $t"
  else
    echo "  [MISSING] $t"
    missing+=("$t")
  fi
done

chrome_found=0
for p in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         "/Applications/Chromium.app/Contents/MacOS/Chromium" \
         "/usr/bin/google-chrome" "/usr/bin/chromium" "/usr/bin/chromium-browser"; do
  [ -f "$p" ] && chrome_found=1 && break
done
if [ "$chrome_found" = 1 ]; then echo "  [ok]      chrome"; else echo "  [MISSING] chrome"; missing+=("chrome"); fi

if python3 -c "import faster_whisper" >/dev/null 2>&1; then
  echo "  [ok]      faster-whisper"
else
  echo "  [MISSING] faster-whisper   (pip install faster-whisper)"
  missing+=("faster-whisper")
fi

if command -v ffmpeg >/dev/null 2>&1; then
  filters="$(ffmpeg -hide_banner -filters 2>/dev/null || true)"
  for f in subtitles lut3d vidstabtransform loudnorm; do
    if echo "$filters" | grep -qE "\s$f\s"; then
      echo "  [ok]      filter: $f"
    else
      echo "  [MISSING] filter: $f  - you need a full ffmpeg build"
    fi
  done
fi

if [ "${HF_HUB_DISABLE_XET:-}" != "1" ]; then
  echo
  echo "  [warn] HF_HUB_DISABLE_XET is not set. Without it the model download can stall."
  echo "         Fix: echo 'export HF_HUB_DISABLE_XET=1' >> ~/.zshrc"
fi

echo
if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing: ${missing[*]}"
  echo "Install them per INSTALL.md, or just start the skill - Claude will offer to do it."
else
  echo "Everything is in place."
fi
echo
echo "Open Claude Code in the folder with your footage and run:"
echo "  /videoediting edit IMG_1234.MOV for Reels"
echo
