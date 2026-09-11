# Changelog

All notable changes to the `videoediting` skill.

## 1.3.0

### Added

- **`references/fablecut.md`** — a reference for the optional timeline tier. [FableCut](https://github.com/ronak-create/FableCut) is a browser-based non-linear editor an agent drives over MCP, where the timeline is a single `project.json`. The reference covers which tool to reach for per job, how the two pipelines hand off in both directions, and where FableCut stops.

  *Credit where it is due:* FableCut is written by Ronak Parmar and published under the MIT licence at <https://github.com/ronak-create/FableCut>. Nothing in it is vendored here — the reference only documents how to use it alongside this pipeline, and everything stated was checked against **v1.7.0, commit `e423338`** (September 2026).

### Changed

- `SKILL.md` splits its "cannot" list in two: what nothing here does at all (object tracking, masked grading — still Premiere / DaVinci / After Effects), and what FableCut covers (frame-accurate cutting, keyframed motion, transitions, speed ramps, chroma key, cutting to a music beat).
- Both READMEs gained a *A timeline when you need one* section, with the two caveats stated plainly: FableCut has no speech recognition whatsoever, and its export runs in the browser, so an agent cannot render unattended. Speech-driven structure and batch runs stay in this pipeline.

## 1.2.0

Everything below is new since `1.0.0`, the version published in the first release.

### Added

- **`download.py`** — fetches source footage from a URL through yt-dlp and always lands it at `<out_dir>/source.mp4`, so the rest of the pipeline never has to parse a filename yt-dlp chose. Re-running is a no-op unless `--force` is passed.
- **`transcribe_cloud.py`** — produces the same word-level `transcript.json` through the Groq or OpenAI Whisper API. No 1.6 GB model download, at the cost of an API key and of sending the audio off the machine.
- **Three layers of hallucination defence in both transcription scripts.** Whisper fabricates text over silence and trailing dead air — most infamously a fake subtitler credit line on Russian audio — and hands it an ordinary confidence score. `1.0.0` had no guard against this at all. There are now `hallucination_silence_threshold`, a `condition_on_previous_text` reset so one fabricated segment cannot seed the next, and a post-filter that drops suspect segments and prints what it dropped.
- **Rule 12 in `SKILL.md`:** read the first and last line of every transcript yourself. The filters catch the obvious cases; they are not airtight.
- **Three new entries in `troubleshooting.md`** (14 → 17): `transcribe_cloud.py` returning API error 413 or hanging on upload, `download.py` failing or producing the wrong file, and a fabricated line appearing in the subtitles that nobody said.

### Changed

- `SKILL.md` now documents twelve scripts instead of ten, and carries twelve rules instead of ten.
- `pipeline.md`, `setup.md` and `batch-pipeline.md` updated for the two new scripts and the cloud transcription route.
- `README.md` and `README.ru.md` brought back in step with what actually ships. The Russian README had drifted furthest: it was still listing six scripts, was missing `batch-pipeline.md` and `remotion.md` from the file tree, and had no section on batch processing or animated graphics.
- `INSTALL.md` gained an optional-extras section covering yt-dlp and the cloud transcription key, including the plain statement that cloud transcription sends your audio off the machine — so NDA footage should stay on the local model.

## 1.0.0

First public release: the ffmpeg pipeline, word-level subtitles, HTML/CSS infographics, colour grading, batch processing, and ten working scripts.
