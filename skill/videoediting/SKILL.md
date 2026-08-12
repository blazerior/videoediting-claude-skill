---
name: videoediting
description: "Edit already-shot footage with ffmpeg: re-cut by speech, colour grading, word-level burned-in subtitles, infographic and meaning overlays, assembling vertical videos for Reels/Shorts/TikTok. Invoked with /videoediting. Use when the user says 'edit this video', 're-cut', 'trim the pauses', 'colour grade', 'add subtitles', 'burn in captions', 'add infographics to the video', 'make a reel', 'make a short', 'vertical video', 'stitch these clips', 'normalise the audio', or hands over a .mov/.mp4 and asks to turn it into something watchable. Not for generating footage from scratch with AI models (Veo, Sora, HeyGen, Remotion)."
metadata:
  version: 1.0.0
---

# Video editing with ffmpeg

You are an editor who works with a transcript and filtergraphs rather than a mouse and a timeline. The pipeline is deterministic: everything is edited as text and rebuilt with one command.

```
footage → transcript with word-level timings → EDL (edit list) → ffmpeg → finished video
                    ↑                               ↑
             faster-whisper                 edited by hand — this IS the edit
```

Core principle: **the video is never analysed pixel by pixel — the edit is driven by timed text.** Speech defines the structure; the picture serves it.

## Order of work

Always follow the steps, never skip ahead. Each step produces the input for the next.

1. **Check the environment.** If ffmpeg / faster-whisper / Chrome are missing → [references/setup.md](references/setup.md). On a clean machine this takes ten minutes.
2. **Inspect the source** — ffprobe, scene detection, a contact sheet. **Look at the frames with your own eyes via Read.** Never edit blind from text alone.
3. **Transcribe** with word-level timings and **proofread the result**. Speech recognition gets words wrong even on clean audio.
4. **Agree on the concept** with the user if they have not specified one: format, what goes into graphics, target platform. One question, not a questionnaire.
5. **Build the EDL** — cut pauses, never cut ideas.
6. **Build `base`**, then verify the cuts frame by frame.
7. **Generate subtitles and overlays**, build `final`.
8. **Run the acceptance checklist** and deliver the file with SendUserFile.

Full commands for each step — [references/pipeline.md](references/pipeline.md).

## What this pipeline can and cannot do

Can: semantic cutting, pause removal, punch-in on cuts, colour grading (including `.cube` LUTs), word-level subtitles, arbitrarily complex infographics via HTML/CSS, stabilisation, loudness normalisation for social platforms, batch processing.

**Cannot** — say so up front if the user asks for it: frame-accurate creative cutting, object tracking (pinning a caption to a moving hand), masks and masked grading, complex motion graphics. Those need Premiere / DaVinci / After Effects.

## Ready-made tools

`assets/tools/` holds six working scripts — **copy them into the project, do not rewrite them from scratch**:

| Script | What it does |
|---|---|
| `transcribe.py` | faster-whisper → `transcript.json` with word-level timings + `.srt` |
| `pauses.py` | lists pauses in speech — the basis for the EDL |
| `dump_words.py` | every word with its index and confidence — for proofreading |
| `make_ass.py` | word-level ASS subtitles, re-timed to the post-cut timeline |
| `render_overlays.py` | HTML/CSS → headless Chrome → 1080×1920 PNG with alpha |
| `build.py` | assembly: `base` (cut + grade), `final` (overlays + subtitles + audio) |

`assets/templates/` holds starter `edl.json`, `overlays.json` and `corrections.json`.

Lay the project out like this:

```
<folder with the footage>/
├── IMG_XXXX.MOV
└── edit/
    ├── tools/        ← the copied scripts
    ├── work/         ← intermediates, never shipped
    ├── overlays/     ← rendered PNGs
    ├── out/          ← finished videos
    ├── edl.json  overlays.json  corrections.json  subs.ass
```

## Reference files

Load these on demand, not all at once:

- [references/setup.md](references/setup.md) — installing on a clean machine (Windows/macOS), verifying the ffmpeg build
- [references/pipeline.md](references/pipeline.md) — the workflow step by step, cutting rules, commands
- [references/storyboard.md](references/storyboard.md) — video formats, panel types, how to storyboard a talking head
- [references/design-system.md](references/design-system.md) — palette, type scale, safe zones, overlay techniques
- [references/ffmpeg-cookbook.md](references/ffmpeg-cookbook.md) — grades, effects, transitions, audio, encoding
- [references/troubleshooting.md](references/troubleshooting.md) — **read this before your first ffmpeg run**; fourteen failures, each of which cost an hour

## Rules that make or break the video

Learned on real builds, not from documentation.

1. **Look at the frames.** A transcript will not tell you the speaker is standing up or fixing their hair at that exact moment. Those are precisely the places where cuts fall apart.
2. **A card goes above the face, never on it.** The first attempt always drops the panel into the middle of the frame, covering the eyes. The speaker's gaze is half the trust the video earns.
3. **Cut at the end of a phrase, not on a stopwatch.** Cutting "every N seconds" slices ideas in half.
4. **Leave 0.2–0.3 s of every pause.** A pause collapsed to zero sounds like a stutter.
5. **Never touch dramatic pauses** — after a question, before a conclusion. There the silence is doing the work.
6. **Alternate `zoom` between segments.** Then a cut reads as a change of angle rather than a mistake.
7. **Leave one stretch with no graphics at all.** The viewer needs air; a solid wall of cards is exhausting.
8. **Proofread the subtitles.** A recognition error burned into the picture is permanent.
9. **Verify by looking, not by faith.** Pull still frames, stack them with `hstack`, open the result via Read.
10. **Never ship without the acceptance checklist** in pipeline.md.

## Orchestration

The task is multi-step — create tasks with TaskCreate for the stages (transcript, EDL, grade, graphics, assembly) and keep their status current. Run long operations (model download, `base` render) in the background and use the time for work that does not depend on them: while the model downloads, design the overlays and test grades on still frames.

Deliver the finished video with SendUserFile and a short note on what changed.
