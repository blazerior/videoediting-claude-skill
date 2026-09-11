# Known failures

Every one of these was hit on a real build. Read before your first ffmpeg run — it will save hours.

## 1. Model download stalls after a few megabytes

Hugging Face fetches files over the xet protocol by default, and on some networks it simply does not work: the download starts and then freezes. The process stays alive and reports no error.

```
HF_HUB_DISABLE_XET=1
```

With this variable the speed is normal, around 2–3 MB/s. Set it **always**.

Diagnosis: if the cache folder has not grown for two minutes, this is it — not a slow connection.

```powershell
"{0:N0} MB" -f ((Get-ChildItem "D:\ai-models\hf" -Recurse -File | Measure-Object Length -Sum).Sum/1MB)
```

## 2. Out of space on the system drive

`large-v3` is 3.1 GB and lands in `C:\Users\<name>\.cache\huggingface` by default. With no room the download dies with `os error 112` after several minutes of waiting.

```
HF_HOME=D:\ai-models\hf
```

Check free space **before** starting, not after. If less than 4 GB is free and there is nowhere to move the cache, use `small` and proofread through `corrections.json`.

## 3. `drawtext` fails with "Fontconfig error: Cannot load default config file"

ffmpeg on Windows has no fontconfig setup, so `drawtext` needs an explicit font file:

```
drawtext=fontfile='C\:/Windows/Fonts/arial.ttf':text='...'
```

The `subtitles` filter (libass) works fine regardless — which is why all text in this pipeline goes through ASS rather than `drawtext`.

## 4. `subtitles=` breaks on paths containing a colon

Inside a filtergraph the colon separates parameters, so `subtitles=D:/path/subs.ass` parses as garbage:

```
Unable to parse "original_size" option value "/path/subs.ass" as image size
```

Fix: run ffmpeg with `cwd` set to the project folder and pass the relative path `subs.ass`. Non-ASCII characters in the path are not a problem. `build.py` already does this via `run(..., cwd=ROOT)`.

## 5. "Cannot allocate memory" when compositing overlays

`-loop 1 -i overlay.png` creates an **infinite** video stream. A dozen such inputs and ffmpeg consumes all available memory.

```
-loop 1 -framerate 30 -t 3.5 -i card.png
...,setpts=PTS-STARTPTS+6.35/TB[o1]
```

Bound the length with `-t`, position it in time with `setpts`.

## 6. `concat` fails with code −22

```
Could not open encoder before EOF
Task finished with error code: -22 (Invalid argument)
```

Every input to concat must match exactly. Append to each video segment:

```
setsar=1,format=yuv420p
```

And to each audio segment:

```
aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo
```

## 7. Subtitles overlapping each other

If an event has not ended before the next one starts, libass draws both lines on top of each other. `make_ass.py` handles this in a post-processing pass that clips each event's end to the next event's start — do not remove it.

Check:

```bash
python -c "
ev=[l for l in open('edit/subs.ass',encoding='utf-8-sig') if l.startswith('Dialogue')]
sec=lambda t:(lambda h,m,s:int(h)*3600+int(m)*60+float(s))(*t.split(':'))
bad=0;prev=0
for l in ev:
    p=l.split(',',4)
    if sec(p[1])<prev-0.001: bad+=1
    prev=sec(p[2])
print(len(ev),'events, overlaps:',bad)"
```

## 8. Subtitles running off the edge of the frame

With `WrapStyle: 2` a long line does not wrap, it simply leaves the screen. Keep `WrapStyle: 0`, the size at 72 or below with three words per line, and `MarginL/R` around 70.

## 9. PowerShell mangles decimal numbers

Under a non-English locale `$t = 5.95` becomes `5,95` when interpolated into a string, and ffmpeg does not understand that timecode — the file is silently never created.

```powershell
$times = @("5.95","6.10")   # strings, not numbers
```

## 10. PNG transparency is lost

Chrome paints a white background by default. Both pieces are required: the `--default-background-color=00000000` flag and `background:transparent` on `html, body` in the CSS.

## 11. A flash of the wrong scene on a cut

If an EDL segment ends inside a scene change in the source (the scene changes at 62.30 and the segment ends at 62.36), two frames of the next scene will flash in the output. Cross-check EDL boundaries against the scene list from `select='gt(scene,0.25)'`.

## 12. Clicks in the audio at cut points

A waveform truncated away from zero crossing produces a click. Fixed by 30 ms fades on each segment edge — the `AFADE` constant in `build.py`. Below 20 ms the click survives; above 50 ms the audio audibly dips.

## 13. Motion in frame at a cut point

Not an ffmpeg bug but a property of the material: the subject stands up, sits down or fixes their hair exactly where the cut lands, so the frame is smeared. Options, in order of effort: move the cut point; cover the moment with an infographic card; add a 0.3 s `xfade` (which shifts every subsequent timing).

This is exactly why the contact sheet must be reviewed **before** the EDL is built.

## 14. Speech recognised, but the text is wrong

Normal behaviour for `small`: compound words fuse, prefixes swap, inflections drift. Do not try to fix it by switching models mid-flight — proofread through `corrections.json` by word index. For a minute of speech that is about ten fixes and five minutes of work.

## 15. `transcribe_cloud.py` exits with "API error 413" or hangs on upload

413 means the compressed chunk still exceeds the provider's limit — check that `ffmpeg` actually produced the 64 kbps mono re-encode (`_upload_*.mp3` briefly appears in the output dir; if `ffmpeg` itself failed the script would have already exited, so this points at an unusually long single chunk). A hang on upload for several minutes with no output is normal for a long file on a slow connection — the compressed audio for an hour of speech is still only ~30 MB.

A 401 means the key is wrong or unset in the shell that actually runs the script — `.env` is only read from the audio file's folder and the current directory, not `~/.config`.

## 16. `download.py` fails or produces the wrong file

"yt-dlp not found" — installed but not on PATH after install; restart the terminal, same as ffmpeg in setup.md.

A private link, a geo-blocked video, or a login-walled page fails with yt-dlp's own error message printed to stderr — there is no workaround inside this pipeline; get a direct file instead.

If `source.mp4` exists from a previous run, the script skips the download and reports the old file — pass `--force` when the URL content actually changed.

## 17. A fabricated line appears in the subtitles that nobody said

The tell: a phrase like "Субтитры создал DimaTorzhok" (or "Subtitles by ...", "thanks for watching, don't forget to subscribe", any other YouTube-outro-shaped sentence) sitting over a stretch of the video where the speaker is silent or has already stopped talking — usually right at the end of the clip, sometimes at the start.

This is Whisper hallucinating, not a bug in the recognised speech. Both `large-v3` and `large-v3-turbo` were trained partly on YouTube's own auto-captions, which are full of community-subtitler credit lines and outro boilerplate; fed a stretch of silence or room tone, the model sometimes free-associates one of those instead of reporting "no speech." It does this on both the local (`transcribe.py`) and cloud (`transcribe_cloud.py`) path, because it is the same family of model either way.

Both scripts now guard against it and print `HALLUCINATION SUSPECTED, DROPPED [...]` when they catch one — that line in the console output is not an error, it is the safety net working. It is not airtight: a fluently-hallucinated line can score confident enough on both `no_speech_prob` and `avg_logprob` to slip through. **Always read the first and last segment of `transcript.json` yourself** before building subtitles — this is the one blind spot proofreading-by-confidence-score (Step 3) does not cover, because the fabricated text can carry a perfectly normal-looking confidence.

If one slips through anyway: remove it from `transcript.json` (or null it out via `corrections.json` by word index) and rebuild subtitles — do not just delete it from the finished `.srt`, or it will come back the next time anything upstream is rebuilt.
