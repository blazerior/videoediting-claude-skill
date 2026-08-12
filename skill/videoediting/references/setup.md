# Setting up the workstation

Goal: on a machine that has nothing but Claude Code, get a working editing environment. Takes about ten minutes, eight of which are downloading the speech recognition model.

## 1. What is already there

Windows (PowerShell):

```powershell
foreach ($t in 'ffmpeg','ffprobe','python','node') { $c = Get-Command $t -ErrorAction SilentlyContinue; if ($c) { "$t => $($c.Source)" } else { "$t => MISSING" } }
```

macOS / Linux:

```bash
for t in ffmpeg ffprobe python3 node; do command -v $t >/dev/null && echo "$t => $(command -v $t)" || echo "$t => MISSING"; done
```

Chrome (needed to render the infographics):

```powershell
foreach ($p in "C:\Program Files\Google\Chrome\Application\chrome.exe","C:\Program Files (x86)\Google\Chrome\Application\chrome.exe","$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") { if (Test-Path $p) { "CHROME: $p" } }
```

And free space on the system drive — at least 4 GB is needed for the model:

```powershell
Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}} | Format-Table -AutoSize
```

## 2. Windows

Install one package at a time and check the result:

```powershell
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
```

```powershell
winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
```

```powershell
winget install --id Google.Chrome -e --accept-source-agreements --accept-package-agreements
```

**Restart the terminal afterwards** — otherwise PATH will not pick the new binaries up.

If `winget` is unavailable, download ffmpeg manually from <https://www.gyan.dev/ffmpeg/builds/> — you need the **full build**; unpack it and add `bin` to PATH.

## 3. macOS

```bash
brew install ffmpeg python@3.12
```

```bash
brew install --cask google-chrome
```

## 4. Verify the ffmpeg build

Stripped-down builds are missing the filters this pipeline needs:

```powershell
ffmpeg -hide_banner -filters | Select-String -Pattern "drawtext|subtitles|curves|colorbalance|lut3d|overlay |zoompan|xfade|vidstab|loudnorm"
```

```bash
ffmpeg -hide_banner -filters | grep -E "drawtext|subtitles|curves|colorbalance|lut3d|overlay |zoompan|xfade|vidstab|loudnorm"
```

`subtitles` (that is libass) and `lut3d` are the critical ones. Without them half the pipeline will not run — install a full build.

## 5. Speech recognition

```bash
pip install faster-whisper
```

Pulls in `ctranslate2`, `onnxruntime` and `tokenizers` — roughly 200 MB. The model itself is downloaded separately on first run.

**Set this environment variable before the first run:**

```
HF_HUB_DISABLE_XET=1
```

Without it the model download from Hugging Face stalls after a few megabytes — the xet protocol simply does not work on some networks. Details and the other traps are in troubleshooting.md.

Choosing a model:

| Model | Size | Quality |
|---|---|---|
| `small` | 0.5 GB | acceptable; will need manual proofreading |
| `medium` | 1.5 GB | good |
| `large-v3-turbo` | 1.6 GB | close to large-v3 but noticeably faster — **the sweet spot** |
| `large-v3` | 3.1 GB | best |

If the system drive is tight, move the cache:

```
HF_HOME=D:\ai-models\hf
```

## 6. Project layout

```powershell
New-Item -ItemType Directory -Force "edit\tools","edit\work","edit\overlays","edit\out" | Out-Null
```

Copy the six scripts from this skill's `assets/tools/` into `edit/tools/`, and the templates from `assets/templates/` into `edit/`.

## 7. Acceptance test

```bash
ffmpeg -version
```

```bash
python -c "import faster_whisper; print('faster-whisper ok')"
```

Test the overlay renderer — create `edit/work/test.json`:

```json
{
  "css": ".t{position:absolute;left:70px;top:800px;right:70px;background:rgba(20,16,12,.88);border-radius:36px;padding:46px;color:#FFF6EC;font-size:60px;font-weight:700}",
  "items": [{ "id": "test", "html": "<div class='t'>Hello, overlay</div>" }]
}
```

```bash
python edit/tools/render_overlays.py edit/work/test.json edit/work
```

`edit/work/test.png` should appear — 1080×1920, transparent background, one card. Open it via Read. If the background is white rather than transparent, the `--default-background-color=00000000` flag went missing.

## 8. Optional third-party tools

**None of these are required.** They just save time:

**claude-real-video** — one command does the whole source breakdown: scene detection, frame de-duplication, transcript, HTML viewer. Replaces the "inspect the source" step entirely:

```bash
pip install "claude-real-video[fast]"
```

```bash
crv "IMG_XXXX.MOV" -o edit/crv --lang en --grid
```

**claude-video** (`/watch`) — a plugin that lets Claude look at video frame by frame. Needs a Groq or OpenAI key:

```bash
npx skills add bradautomates/claude-video -g
```

**digitalsamba/claude-code-video-toolkit** — a toolkit for generative video (Remotion, AI voice-over, scene generation, cloud GPU). Overkill for editing shot footage; useful when a video is assembled from code rather than from a camera. Worth borrowing its transition library and its `brands/` idea — a brand profile holding palette and fonts.

MCP servers are not needed for editing — everything runs as local commands.
