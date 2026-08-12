# Storyboarding and video formats

## Why storyboard at all

The temptation after transcribing is to jump straight into `overlays.json` and start laying out cards. Don't: you end up with a pile of panels and no rhythm. Map the video out in panels first — it is cheap, it edits as plain text, and it can be shown to the user before anything renders.

A **panel** is the state of the screen over a stretch of time: what is in frame, what the text says, what graphics are up. A one-minute video is 12–20 panels.

Order: transcript → semantic blocks → panels inside blocks → `overlays.json`. One block is one idea, usually 5–15 seconds and 1–3 panels.

## Panel types

| Type | On screen | When |
|---|---|---|
| **Clean speaker** | just the person and subtitles | connective tissue, transitions between ideas, breathing room |
| **Hook title** | large headline on top + scrim | first 3–6 seconds, the opening question |
| **Thesis card** | panel above the face, kicker + 1–2 lines | a key claim |
| **Rebuttal** | same, with a word struck through | "it isn't laziness", myth-busting |
| **List** | 2–4 bullets appearing one at a time | enumeration, mechanism |
| **Split / diagram** | two columns with a relation between them | contrast, before/after, innate vs acquired |
| **Pull quote** | large centred text, no panel | the climax, the strongest line |
| **Big number** | one huge figure + caption | statistics, duration, quantity |
| **CTA** | panel with an icon and an action | the ending |

Limitation of this pipeline: a panel is a PNG overlay on top of live footage. Full-screen inserts of other video and picture-in-picture circles are not available unless you have a second source. If you truly need one, it becomes another ffmpeg input rather than an overlay.

## The "thesis breakdown" format

Validated on a talking-head monologue, 73 s → 68 s. Works for any expert content.

| Share of runtime | Block | Panel |
|---|---|---|
| 0–8 % | Hook | Hook title with a question |
| 8–13 % | Rebuttal | Card with a struck-through word |
| 13–23 % | Cause | Thesis card |
| 23–38 % | Mechanism | Two-column diagram, second column appears separately |
| 38–54 % | Breakdown | List, bullets appearing one at a time |
| 54–64 % | Turn | **Clean speaker** — breathing room |
| 64–77 % | Consequences | Two-bullet list |
| 77–86 % | Climax | Pull quote + maximum zoom |
| 86–100 % | Ending | Two CTA panels back to back |

## Other formats

**"The list"** — "5 signs that…". Hook → numbered points, each with its own card and its own punch-in → conclusion. The easiest to assemble and trivially re-cut into separate clips.

**"The story"** — setup → problem → turning point → outcome. Minimal graphics, only subtitles and 2–3 accents: the story carries itself and cards smother it.

**"The case study"** — question → what was done → the number → how to repeat it. The key panel is the big number: one large figure filling the screen.

**"Reply to a comment"** — a screenshot of the question for the first 3 seconds, then the talking head. The screenshot is laid out as just another card in `overlays.json`.

## How to build the storyboard

1. Split the transcript into semantic blocks and write down their boundaries in source seconds.
2. Assign a panel type to each block. **Never repeat the same type back to back** — a list after a list reads as one long wall of text.
3. Convert the timings to the final timeline (the cut shifts everything left; see below).
4. Show the user the storyboard as a table: time, type, text. Changes are free at this stage and expensive after rendering.
5. Build the first panel, check it on a still frame, and only then produce the rest. Otherwise a positioning mistake will repeat itself twelve times.

## Converting timings

After cutting, time in the finished video no longer matches the source. The shift for a segment is:

```
offset_i = final_segment_start − source_segment_start
```

A word spoken at 44.81 in the source lands at 41.76 in the final cut when `offset = −3.05`. `make_ass.py` does this conversion for subtitles automatically; **for overlays you do it yourself** — write out the cumulative segment boundaries right after building `base` and keep them at hand.

To print the actual boundaries:

```bash
python -c "import json;s=json.load(open('edit/edl.json',encoding='utf-8'))['segments'];t=0
for i,x in enumerate(s):
    d=x['end']-x['start'];print(f\"seg{i+1}: {t:6.2f}-{t+d:6.2f}  (source {x['start']}-{x['end']}, shift {t-x['start']:+.2f})\");t+=d"
```

## Rhythm

- A panel lives **no less than 2 and no more than 8 seconds**. Less and it cannot be read; more and it becomes wallpaper.
- Leave 0.3–1 s of clean frame between panels, otherwise they smear into each other.
- For a one-minute video: 8–12 panels and at least one 4–6 second stretch with no graphics at all.
- Bullets appearing one at a time: two cards with identical markup, the extra bullet hidden by `opacity:0` in the first and revealed and highlighted in the second. Placed back to back, so the bullet "arrives" while nothing else moves.

## One take, many videos

A single source yields several different pieces with no reshoot: the full version, a 15-second teaser made of the hook and the climax, a separate clip per list item. The transcript and the proofreading are reused; only the EDL and the storyboard change. The visual style changes the same way — palette and typography live in one CSS block inside `overlays.json`, so restyling is a single-file edit rather than a rebuild.

## The generative branch

There is an approach where, after cutting, the pieces are sent to a video model (Google Flow / Veo) together with the storyboard and a prompt along the lines of "edit exactly to this storyboard, smooth transitions, leave the original audio untouched", and ffmpeg only stitches the results. It produces imagery that was never shot, but it requires paid access, manual work in someone else's UI, and it gives up frame-level control.

When it is worth it: you need visuals that do not exist in the footage, or you want to try a dozen radically different styles quickly. Otherwise the local pipeline is more predictable and edits as text. If the user wants that branch, the storyboard built from this file is exactly what gets fed to the model.
