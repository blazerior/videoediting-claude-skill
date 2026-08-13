# Batch pipeline — editing many reels without burning context

One reel is a conversation. Ten reels is a pipeline. The difference is not the ffmpeg work — that scales fine — it is **context**: doing ten reels the conversational way costs roughly ten times the tokens of doing one, and most of that spend buys nothing.

`assets/tools/pipeline.py` runs each stage once over the whole project, caches by input hash, and prints one line per reel.

## Stages

```
ingest      inventory every media file                -> work/media.json
transcribe  every voiceover in ONE model load         -> work/vo/<id>/transcript.json
probe       scene cuts + one contact sheet per source -> work/shots.json, work/sheets/
overlays    graphics for every reel                   -> overlays/<reel>/
subs        subtitles for every reel                  -> subs-<reel>.ass
base        cut + grade video track for every reel    -> work/<reel>_base.mp4
final       composite everything                      -> out/<reel>.mp4
qa          ONE contact strip for all reels + report  -> work/qa.png
```

```bash
python tools/pipeline.py all
```

```bash
python tools/pipeline.py final --only 2a,3b
```

```bash
python tools/pipeline.py overlays --force
```

Every stage is idempotent. Re-running costs nothing when inputs are unchanged — the cache key is the mtime+size of every input plus the relevant config.

## The manifest

`project.json` holds only what is short and shared:

```json
{
  "media_dir": "D:\\path\\to\\footage",
  "qr": "D:\\path\\to\\qr.jpg",
  "lang": "ru",
  "whisper_model": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
  "voices": { "vo1": { "file": "…mp3" } },
  "reels": {
    "1a": { "voice": "vo1", "title": "1A-tutorial", "mute": [[0, 2.35], [31.3, 34.3]] }
  }
}
```

Per-reel detail stays in `edl-<name>.json` and `overlays-<name>.json`. **Do not merge them into the manifest** — see the next section for why.

## Where the tokens actually go

Measured on a real ten-reel project, in descending order of waste:

### 1. Editing large JSON files — the biggest leak by far

Every `Edit` on a file echoes the whole file back into context. An EDL with ten segments and comments is ~4 KB ≈ 1.5k tokens. Touch ten of them twice and that is 30k tokens spent on re-reading your own data.

**Rules:**

- **Never let a tool mutate a config file.** The old `make_reel.py` wrote the overlay timeline and output directory back into the EDL, doubling its size and making every subsequent edit twice as expensive. `build_vo.py` now reads the timeline from `overlays-<name>.json` directly and leaves the EDL alone.
- **Generated data goes in `work/`**, never next to hand-edited config.
- **Write config files whole** with `Write` rather than patching them with several `Edit` calls.
- **Keep the `_note` fields short.** They are useful, but they are also tokens on every echo.

### 2. Looking at frames one reel at a time

Each image costs roughly 1–2k tokens. Checking ten reels at six frames each, as separate strips, is twenty-plus images.

The `qa` stage stacks every reel into a single `work/qa.png` — ten rows, six frames per row. One image, one look, the whole project verified. When something looks wrong, only then pull that one reel in detail.

### 3. Re-probing the same source for every reel

Ten reels usually draw on the same handful of clips. Probing scene cuts and building contact sheets per reel repeats identical work and identical images.

The `probe` stage does it once per **source file**, writes `work/shots.json`, and puts one 8-frame sheet per source in `work/sheets/`. Read those sheets once at planning time; after that work from the timecodes in `shots.json`, which is text.

### 4. Reloading the speech model

`faster-whisper` spends most of its wall clock loading the model, not transcribing. `batch_vo.py` loads it once and walks every voiceover. Seven voiceovers: one load instead of seven.

### 5. Verbose command echo

Printing the full ffmpeg command line for every reel is a few hundred tokens each and tells you nothing you didn't already know. The pipeline prints `overlays : 3 rebuilt, 7 cached` and nothing more. Failures still dump stderr — that is the case where the detail is worth paying for.

## Working order for a new batch project

1. `ingest` — then read `work/media.json`. It is text, and it already tells you resolution, duration, rotation and codecs for everything.
2. `transcribe` — read the transcripts. Text again.
3. `probe` — **this is the one place to spend images.** Look at `work/sheets/` once, note what is where, and write it down as timecodes. Every later decision references those numbers instead of re-opening frames.
4. Write all EDLs and overlay specs in one pass, from the notes.
5. `overlays subs base final` — or just `all`.
6. `qa` — one image, one report. Fix what is broken, re-run only the affected stage.

The shape that matters: **look once, write once, build many.** The conversational shape — plan a reel, build it, look at it, fix it, repeat — is what multiplies cost by ten.

## When a reel needs fixing

Change only its own files and re-run the narrow stage:

```bash
python tools/pipeline.py overlays --only 3b && python tools/pipeline.py final --only 3b
```

`base` is the slow stage; it only re-runs when the EDL or the grade changed. Graphics and subtitles iterate in seconds.
