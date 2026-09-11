# FableCut — the timeline layer

[FableCut](https://github.com/ronak-create/FableCut) is a browser-based non-linear editor that an agent can drive. The whole timeline is one `project.json`; patch it and the open editor hot-reloads in about 150 ms. It does not replace this pipeline — it covers the half of the job ffmpeg filtergraphs are bad at.

**Source and credit.** Written by Ronak Parmar, MIT licence, zero npm dependencies. Everything below was checked against **v1.7.0, commit `e423338`** (September 2026). It is a young project — created July 2026 — so treat the `project.json` schema as something that can still move between versions, and re-read `fablecut_docs` rather than trusting a remembered field name.

## Install

```bash
/plugin marketplace add ronak-create/FableCut
```

```bash
/plugin install fablecut@fablecut
```

Restart Claude Code afterwards. Requirements: Node 18+, a Chromium browser, and ffmpeg on PATH (optional, but without it export falls back to a realtime MediaRecorder capture, which is slower and worse). The editor runs at `http://localhost:7777` and binds to `127.0.0.1` only.

The plugin brings eight MCP tools — `fablecut_status`, `fablecut_docs`, `fablecut_get_project`, `fablecut_set_project`, `fablecut_patch_project`, `fablecut_import_media`, `fablecut_analyze_reference`, `fablecut_encode_profiles` — and two skills, `fablecut:edit-video` and `fablecut:remake-reel`.

## Which tool for which job

| Job | Tool | Why |
|---|---|---|
| Cut by speech, kill pauses | **this pipeline** | the transcript *is* the edit; FableCut has no speech recognition at all |
| Word-level burned-in subtitles | **this pipeline** | `make_ass.py` + libass, one pass, no browser |
| Ten reels as a batch | **this pipeline** | `pipeline.py` is headless and caches; FableCut needs a human click per export |
| Frame-accurate trimming by eye | **FableCut** | a real timeline with snapping beats nudging numbers in `edl.json` |
| Keyframed motion, speed ramps | **FableCut** | ~25 animatable properties with easing curves; ffmpeg cannot do this sanely |
| Transitions between clips | **FableCut** | 17 built-in types against `xfade`'s awkward offset arithmetic |
| Editing to a music beat | **FableCut** | `fablecut_analyze_reference` gives beats, BPM and an energy curve |
| Chroma key, background removal | **FableCut** | MediaPipe in-browser, no green-screen filtergraph to tune |
| Colour grade with a `.cube` LUT | **this pipeline** | `lut3d` is exact and reproducible |

The short version: **speech-driven structure stays here, hand-and-eye work goes to FableCut.**

## How the two hand off

The natural split is to let this pipeline do what it is good at first, then import the result.

1. Transcribe and build the EDL as usual — the transcript is still the cheapest way to find the structure.
2. Render `base` (cut + grade) with `build.py`. That is a single clean MP4.
3. `fablecut_import_media` that file, then work the timeline for the things filtergraphs make painful: transitions, keyframed punch-ins, speed ramps, animated titles.
4. Export from FableCut, then burn subtitles over the export with the existing ffmpeg pass if you want the word-level ASS captions rather than FableCut's kinetic ones.

Going the other way also works: cut in FableCut, export, then run the export through `transcribe.py` and `make_ass.py`. It costs one extra encode.

**Concurrency.** If a human edits a clip in the UI while the agent is mid-write, the agent's next write is rejected with a 409 instead of silently overwriting. Do not defeat this by re-sending the patch blindly — re-read the project with `fablecut_get_project` and rebase the change.

## Remaking a reel you like

`fablecut:remake-reel` is the genuinely novel piece and has no equivalent in this pipeline. Feed it a reference video — a reel, a montage, an ad — and it returns an edit blueprint: shot boundaries, music beats and BPM, an energy curve, where the drop lands. Then it rebuilds that structure with your own footage.

That is the one thing worth installing FableCut for even if you never touch its timeline by hand. Cutting to a beat grid is something the transcript-driven approach here simply cannot see.

## When not to use it

- **You need it headless.** The compositor *is* the browser, so export runs there. The agent cannot render on its own — it asks you to press Export, or you render straight from `media/` with ffmpeg and skip FableCut's compositing. This is what rules it out for a ten-reel batch.
- **You need subtitles from speech.** There is no ASR anywhere in it. That stays here.
- **You need object tracking or masks.** Neither tool does these. That is still Premiere, DaVinci or After Effects.
- **You need Cyrillic titles and have not checked the font.** The UI ships in English, Chinese, Japanese, Spanish and Brazilian Portuguese, and bundles 20 Google Fonts (OFL) — not all of them cover Cyrillic. Load a font that does before typing Russian into a title, or it will render as boxes.

The honest split: this pipeline stays the backbone for anything driven by speech and anything that has to run ten times unattended. FableCut is what you open when the edit needs a pair of eyes on a timeline.
