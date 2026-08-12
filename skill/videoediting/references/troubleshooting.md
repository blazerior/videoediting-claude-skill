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
