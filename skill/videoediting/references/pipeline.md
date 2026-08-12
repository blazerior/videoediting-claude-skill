# Workflow

## Step 1. Inspect the source

```bash
ffprobe -v error -show_format -show_streams -print_format json "IMG_XXXX.MOV"
```

Note the resolution, fps, duration, codecs and audio bitrate. A typical vertical iPhone clip is 1080×1920 (sometimes 1072×1920, which `scale` will fix) at 60 fps.

Find the cuts that already exist inside the source — it is good practice to align your edit points with them:

```bash
ffmpeg -hide_banner -i "IMG_XXXX.MOV" -vf "select='gt(scene,0.25)',showinfo" -an -f null -
```

Pull a contact sheet and **open the frames via Read**:

```bash
ffmpeg -y -i "IMG_XXXX.MOV" -vf "fps=1/9,scale=360:-1" edit/work/f_%02d.jpg
```

Do not look for "what the video is about" — look for specifics: where the subject moves, sits down, stands up, fixes their hair; where the light and background change. Those places break cuts, and you need to know about them **before** you build the EDL.

Check the audio level:

```bash
ffmpeg -hide_banner -i "IMG_XXXX.MOV" -af volumedetect -f null -
```

## Step 2. Transcribe

```bash
ffmpeg -y -i "IMG_XXXX.MOV" -vn -ac 1 -ar 16000 -c:a pcm_s16le edit/work/audio.wav
```

Windows:

```powershell
$env:HF_HUB_DISABLE_XET="1"; $env:HF_HOME="D:\ai-models\hf"; $env:WHISPER_MODEL="large-v3-turbo"; $env:WHISPER_LANG="en"; python edit\tools\transcribe.py edit\work\audio.wav edit
```

macOS / Linux:

```bash
HF_HUB_DISABLE_XET=1 WHISPER_MODEL=large-v3-turbo WHISPER_LANG=en python3 edit/tools/transcribe.py edit/work/audio.wav edit
```

Set `WHISPER_LANG` to the language actually spoken, or leave it unset for auto-detection. The first run downloads the model — run it in the background and use the time for grading and overlay design.

## Step 3. Proofread the text

```bash
python edit/tools/dump_words.py edit/transcript.json
```

Look at words with confidence `p` below 0.7, then read the whole thing. Collect fixes in `edit/corrections.json` — the key is the word index, an empty string deletes the word:

```json
{
  "_note": "Recognition fixes: word index -> correct text. Empty string removes the word.",
  "22": "",
  "26": "burnout",
  "77": "unrealised",
  "105": "In"
}
```

Usual casualties: compound words fused together, prefixes swapped, proper nouns mangled. Expect around ten fixes per minute of speech with `small`, one or two with `large-v3`.

## Step 4. Agree on the concept

If the user has not specified a format, ask **in a single pass** — do not run a questionnaire: platform and length limit, the topic and what should go into graphics, brand colours and logo if any. Then pick a format from [storyboard.md](storyboard.md) and show the block structure before rendering anything.

## Step 5. The EDL is the edit

```bash
python edit/tools/pauses.py edit/transcript.json 0.28
```

Create `edit/edl.json`:

```json
{
  "source": "D:\\path\\to\\IMG_XXXX.MOV",
  "segments": [
    { "start": 0.00,  "end": 2.11,  "zoom": 1.00,  "t": "first line — note to self" },
    { "start": 2.36,  "end": 6.28,  "zoom": 1.045, "t": "second line" }
  ]
}
```

On Windows escape the backslashes in `source`: `D:\\video\\file.MOV`.

Cutting rules:

- **Cut pauses, not ideas.** In talking-head content every sentence carries meaning; aggressive cutting destroys the logic.
- **Cut at the end of a phrase.** Cutting on a stopwatch ("every 10 seconds") slices ideas in half.
- **Leave 0.2–0.3 s of each pause.**
- **Never touch dramatic pauses** — after a question, before a conclusion.
- **Alternate `zoom`** between neighbouring segments (1.00 / 1.05 / 1.09). Maximum on the climax.
- **Do not cut where the subject is moving.** If the cut is unavoidable, cover it with an infographic card.
- **Check that a segment does not end inside a scene change** in the source: if the scene changes 0.1 s before your cut, two frames of the next scene will flash in the output.

For reference: 73 seconds of talking-head monologue yields about 5 seconds of pauses to remove without losing a single idea.

```bash
python edit/tools/build.py base
```

Verify the cuts — pull frames either side of each one, stack them, open via Read:

```bash
ffmpeg -y -ss 6.10 -i edit/work/base.mp4 -frames:v 1 -vf "scale=300:-1" edit/work/cut1.png
```

```bash
ffmpeg -y -i edit/work/cut1.png -i edit/work/cut2.png -i edit/work/cut3.png -filter_complex "[0][1][2]hstack=inputs=3" edit/work/row.png
```

## Step 6. Subtitles

```bash
python edit/tools/make_ass.py edit/transcript.json edit/edl.json edit/subs.ass edit/corrections.json
```

The script re-times every word onto the post-cut timeline and separates events so lines cannot overlap.

## Step 7. Infographics

Write `edit/overlays.json` — a single file holding the CSS, the card markup and the timing. Template in `assets/templates/overlays.json`; techniques and palette in [design-system.md](design-system.md).

```bash
python edit/tools/render_overlays.py edit/overlays.json edit/overlays
```

## Step 8. Assembly and acceptance

```bash
python edit/tools/build.py final
```

Pull a frame on every card, stack them into rows of six with `hstack`, open via Read. Then the checklist:

- [ ] No card covers the speaker's eyes
- [ ] Subtitles stay inside the frame and never overlap each other
- [ ] Subtitle text has been proofread
- [ ] No flashes of the wrong scene on cuts, no clicks in the audio
- [ ] The change of framing is noticeable but not jarring — the cut reads as a deliberate choice
- [ ] There is at least one stretch with no graphics
- [ ] Technical parameters are correct:

```bash
ffprobe -v error -show_entries format=duration,size:stream=width,height,r_frame_rate -of default=nw=1 edit/out/final.mp4
```

```bash
ffmpeg -hide_banner -i edit/out/final.mp4 -af volumedetect -f null -
```

Expect 1080×1920, `+faststart`, and a mean around −18 dB after `loudnorm` to −14 LUFS.

Deliver the file with SendUserFile.

## What to rebuild after a change

```bash
python edit/tools/build.py base && python edit/tools/build.py final
```

| Changed | Rebuild |
|---|---|
| `edl.json` (cuts, zoom) | `base` → `make_ass.py` → `final` |
| `GRADE` in `build.py` | `base` → `final` |
| `overlays.json` | `render_overlays.py` → `final` |
| `corrections.json` | `make_ass.py` → `final` |

`final` is fast, `base` is noticeably slower. That is why graphics and subtitles can be iterated freely without touching the cut — the two-stage split exists precisely for this.

## Batch: several videos from one source

One transcript, several EDLs. Keep `edl-hook.json`, `edl-full.json`, `edl-teaser.json` and build each into its own output, swapping the filename in `build.py` or copying the chosen EDL over `edl.json` before building. The transcript and `corrections.json` are reused as they are.
