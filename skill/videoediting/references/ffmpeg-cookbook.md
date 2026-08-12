# ffmpeg cookbook

## Grading

The base grade — tested against hard backlight from a window. Lifts the face out of shadow and reconciles different locations:

```
eq=contrast=1.13:brightness=0.012:saturation=1.07:gamma=1.07,
curves=all='0/0 0.22/0.285 0.75/0.795 1/1':r='0/0 0.5/0.515 1/1':b='0/0 0.5/0.492 1/1',
vignette=PI/9,unsharp=5:5:0.45
```

What each part does: `eq` sets overall contrast and lifts the midtones; `curves` raises the shadows (the 0.22/0.285 point) and warms the skin by pushing red up and blue down; `vignette=PI/9` gently darkens the edges and keeps the eye on the face; `unsharp` compensates for the softening introduced by `scale` and `crop`.

Alternatives — drop them into `GRADE` in `build.py`:

| Look | Filter |
|---|---|
| Neutral punch | `eq=contrast=1.12:saturation=1.06:gamma=1.06,curves=all='0/0 0.22/0.28 0.75/0.79 1/1'` |
| Warm cinematic | `curves=r='0/0.015 0.5/0.535 1/1':b='0/0 0.5/0.465 1/0.97',eq=contrast=1.14:saturation=1.10,vignette=PI/5` |
| Pastel / film fade | `curves=all='0/0.055 0.3/0.35 0.7/0.73 1/0.965',eq=saturation=0.90,colorbalance=rs=0.04:bs=-0.03` |
| Ready-made LUT | `lut3d=file='look.cube'` |

`vignette=PI/5` is strong and visible; `PI/9` is subtle. Smaller denominator, stronger effect.

**Choose a grade by comparison, not by eye.** Pull one frame, run it through the candidates, stack them and open via Read:

```bash
ffmpeg -y -ss 45 -i "IMG.MOV" -frames:v 1 -vf "eq=contrast=1.12,scale=380:-1" edit/work/gA.png
```

```bash
ffmpeg -y -i edit/work/g0.png -i edit/work/gA.png -i edit/work/gB.png -filter_complex "[0][1][2]hstack=inputs=3" edit/work/grade.png
```

Mind the headroom: 8-bit bt709 phone footage takes a moderate grade. Aggressive curves will band on gradients — most visibly on the wall behind the subject.

## Framing and movement

| Task | Filter |
|---|---|
| Punch-in (static zoom) | `crop=iw/1.06:ih/1.06:(iw-ow)/2:(ih-oh)/2,scale=1080:1920:flags=lanczos` |
| Slow push-in | `zoompan=z='min(zoom+0.0006,1.15)':d=<frames>:s=1080x1920:fps=30` |
| Convert other aspect ratios to 9:16 | `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920` |
| Blurred background instead of bars | `split[a][b];[a]scale=1080:1920,boxblur=40[bg];[b]scale=1080:-1[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2` |
| Stabilisation, pass 1 | `vidstabdetect=shakiness=6:accuracy=15:result=t.trf` |
| Stabilisation, pass 2 | `vidstabtransform=input=t.trf:smoothing=30:zoom=2` |
| Horizontal flip | `hflip` |

## Transitions

A hard cut on a pause is almost invisible and beats any effect. A cross-fade earns its place where there is movement in frame — the subject sitting down, standing up, turning:

```
xfade=transition=fade:duration=0.3:offset=<second_of_the_cut>
```

Others: `wipeleft`, `slideup`, `dissolve`, `smoothleft`, `circleopen`. For a talking head, anything beyond `fade` and `dissolve` looks amateur.

**Important:** `xfade` shortens the result by the transition duration, and every subsequent timing — subtitles and overlays alike — shifts. If you add transitions, either recompute the timings or keep them at the end of the chain.

Audio across a transition — `acrossfade=d=0.3` with a matching duration.

## Overlays

```
-loop 1 -framerate 30 -t 3.5 -i card.png
[1:v]format=rgba,fade=t=in:st=0:d=0.25:alpha=1,fade=t=out:st=3.25:d=0.25:alpha=1,setpts=PTS-STARTPTS+6.35/TB[o1]
[0:v][o1]overlay=0:0:eof_action=pass:repeatlast=0:enable='between(t,6.35,9.85)'[b1]
```

`-t` is mandatory — without it `-loop 1` produces an infinite stream and eats all available memory.

A corner logo:

```
[0:v][1:v]overlay=W-w-40:H-h-260
```

## Subtitles

```
subtitles=subs.ass:fontsdir='C\:/Windows/Fonts'
```

Run ffmpeg with `cwd` set to the project folder and pass a relative path — the drive-letter colon breaks the filtergraph.

Burning an SRT directly, without ASS:

```
subtitles=subs.srt:force_style='Fontname=Arial,Fontsize=24,PrimaryColour=&H00FFFFFF,Outline=2'
```

## Audio

| Task | Filter |
|---|---|
| Normalise for social platforms | `loudnorm=I=-14:TP=-1.5:LRA=11` |
| Two-pass loudnorm (more accurate) | first `loudnorm=print_format=json`, then feed the measured values back |
| Fades at cut points | `afade=t=in:st=0:d=0.03` + `afade=t=out:st=<end-0.03>:d=0.03` |
| Noise reduction | `afftdn=nf=-25` |
| Remove low-end rumble | `highpass=f=80` |
| Tame sibilance | `deesser` |
| Add background music | `[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.15` |

The standard for Reels/TikTok is −14 LUFS. Quieter sounds amateurish; louder and the platform will turn it down itself.

## Encoding

Final:

```
-c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p -profile:v high -level 4.1
-c:a aac -b:a 192k -ar 48000 -movflags +faststart
```

Intermediates: `-crf 16 -preset medium`, so re-encoding losses do not accumulate.

CRF: 16–18 for intermediates, 19–21 for the final, 23+ already shows artefacts on gradients.

Frame rate: 30 is plenty for a talking head and keeps the file smaller. 60 only makes sense with fast movement in frame.

## Inspection and verification

```bash
ffprobe -v error -show_format -show_streams -print_format json "IMG.MOV"
```

```bash
ffmpeg -hide_banner -i "IMG.MOV" -vf "select='gt(scene,0.25)',showinfo" -an -f null -
```

```bash
ffmpeg -y -i "IMG.MOV" -vf "fps=1/9,scale=360:-1" edit/work/f_%02d.jpg
```

```bash
ffmpeg -hide_banner -i "IMG.MOV" -af volumedetect -f null -
```

Stacking frames into a strip for visual review:

```bash
ffmpeg -y -i a.png -i b.png -i c.png -filter_complex "[0][1][2]hstack=inputs=3" row.png
```

Use `vstack` for a vertical strip and `xstack` for a grid.
