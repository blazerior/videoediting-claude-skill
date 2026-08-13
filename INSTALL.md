# Installation

Two paths: the automatic one (a script does everything) and the manual one (you see every step). On a clean machine it takes about ten minutes, eight of which are downloading the speech recognition model.

## Path 1: the install script

```bash
git clone https://github.com/blazerior/videoediting-claude-skill.git
cd videoediting-claude-skill
```

**Windows:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

**macOS / Linux:**

```bash
bash scripts/install.sh
```

The script copies `skill/videoediting/` into `~/.claude/skills/videoediting/` and prints a dependency report. It does not install anything system-wide — that part is below, or Claude will do it for you on the first run.

## Path 2: manual copy

Copy the folder `skill/videoediting` into:

| OS | Destination |
|---|---|
| Windows | `%USERPROFILE%\.claude\skills\videoediting` |
| macOS / Linux | `~/.claude/skills/videoediting` |

That is all a skill needs. To scope it to a single project instead, put it in `.claude/skills/videoediting` inside that project.

Verify it was picked up — start Claude Code and type `/` : `videoediting` should appear in the list.

## Dependencies

### Windows

```powershell
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
```

```powershell
winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
```

```powershell
winget install --id Google.Chrome -e --accept-source-agreements --accept-package-agreements
```

**Restart the terminal afterwards**, otherwise PATH will not pick up the new binaries.

If `winget` is unavailable, download ffmpeg from <https://www.gyan.dev/ffmpeg/builds/> — the **full build** — unpack it and add its `bin` folder to PATH.

### macOS

```bash
brew install ffmpeg python@3.12
```

```bash
brew install --cask google-chrome
```

### Linux

```bash
sudo apt install ffmpeg python3 python3-pip chromium-browser
```

Check that your distribution's ffmpeg is built with libass — see the filter check below.

### Speech recognition, every platform

```bash
pip install faster-whisper
```

## Verifying the ffmpeg build

This is the step people skip and then wonder why nothing works. Stripped-down builds lack the filters the pipeline needs:

```bash
ffmpeg -hide_banner -filters | grep -E "subtitles|curves|colorbalance|lut3d|overlay |zoompan|xfade|vidstab|loudnorm"
```

```powershell
ffmpeg -hide_banner -filters | Select-String -Pattern "subtitles|curves|colorbalance|lut3d|overlay |zoompan|xfade|vidstab|loudnorm"
```

`subtitles` (libass) and `lut3d` are the critical ones. If they are absent, install a full build — half the pipeline will not run otherwise.

## Environment variables

Two of them matter. Set them once, in your shell profile or system settings.

```
HF_HUB_DISABLE_XET=1
```

**Mandatory.** Without it the model download from Hugging Face stalls after a few megabytes — the xet protocol does not work on some networks. The process stays alive and reports no error, so it looks like a slow connection.

```
HF_HOME=D:\ai-models\hf
```

Optional. Moves the model cache off the system drive. Useful when the largest model is 3.1 GB and `C:` is tight.

Windows, for the current user:

```powershell
[Environment]::SetEnvironmentVariable("HF_HUB_DISABLE_XET","1","User")
```

macOS / Linux, add to `~/.zshrc` or `~/.bashrc`:

```bash
echo 'export HF_HUB_DISABLE_XET=1' >> ~/.zshrc
```

## Choosing a model

The first transcription run downloads a model. Pick it with `WHISPER_MODEL`:

| Model | Size | Quality | When |
|---|---|---|---|
| `small` | 0.5 GB | acceptable | tight disk, or English-only with clean audio |
| `medium` | 1.5 GB | good | a reasonable middle ground |
| `large-v3-turbo` | 1.6 GB | near-best, noticeably faster | **the default recommendation** |
| `large-v3` | 3.1 GB | best | when accuracy matters more than time |

## Acceptance test

```bash
ffmpeg -version
```

```bash
python -c "import faster_whisper; print('faster-whisper ok')"
```

Overlay renderer — create `test.json`:

```json
{
  "css": ".t{position:absolute;left:70px;top:800px;right:70px;background:rgba(20,16,12,.88);border-radius:36px;padding:46px;color:#FFF6EC;font-size:60px;font-weight:700}",
  "items": [{ "id": "test", "html": "<div class='t'>Hello, overlay</div>" }]
}
```

```bash
python skill/videoediting/assets/tools/render_overlays.py test.json .
```

`test.png` should appear — 1080×1920 with a transparent background and one card on it. If the background is white, the `--default-background-color=00000000` flag went missing; if the file was never created, Chrome was not found.

## First run

Open Claude Code in the folder holding your footage and type:

```
/videoediting edit IMG_1234.MOV for Reels, the topic is burnout
```

Claude will inspect the source, transcribe it, show you the proposed structure and only then start rendering. Approve the structure before it renders — changes are free at that stage.

## Troubleshooting

If something breaks, the answer is very likely in `skill/videoediting/references/troubleshooting.md` — fourteen documented failures with fixes. The most common three:

1. **Model download frozen** → `HF_HUB_DISABLE_XET=1`
2. **`Cannot allocate memory` while compositing overlays** → missing `-t` on a `-loop 1` input
3. **`concat` fails with −22** → missing `setsar=1,format=yuv420p` on the video segments
