# Overlay design system

## Safe zones for 1080×1920

| Zone | Coordinates | What may go there |
|---|---|---|
| Platform UI, top | 0–150 | nothing |
| **Working area for graphics** | **200–1250** | titles, cards, diagrams, CTA |
| Speaker's face | usually 700–1300 | keep out |
| **Subtitles** | 1380–1520 | subtitles only |
| Platform UI, bottom | 1600–1920 | nothing |

**A card goes above the face, never on it.** This rule is broken on nearly every first attempt: the panel lands in the middle of the frame and covers the eyes. The speaker's gaze is half the trust the video earns. Check still frames and move cards up until the eyes are clear.

Account for `zoom` from the EDL: on a segment at 1.09 the face is larger and higher, so a card that sat fine at 1.00 will start clipping the forehead.

## Palette

Warm and calm — suited to expert talking-head content:

| Role | Colour |
|---|---|
| Panel | `rgba(20,16,12,.88)` |
| Text | `#FFF6EC` |
| Secondary text | `#CDBBA5` |
| Accent | `#E8A33D` (amber) |
| Negative, struck through | `#C7523B` (terracotta) |

Pick the accent from what is already in frame — the subject's clothing, the wall, the light. If the user has brand colours, only this block changes; the layout stays.

## Type scale

| Element | Size | Weight |
|---|---|---|
| Hook headline | 100 | 700 |
| Pull quote | 82 | 700 |
| Card body | 58 | 600 |
| List item | 50 | 600 |
| Caption | 36 | 400 |
| Kicker | 29 | 600, uppercase, `letter-spacing:.22em` |
| Subtitles | 72 | bold |

Font stack: `'Bahnschrift','Segoe UI','Helvetica Neue',Arial,sans-serif`. Bahnschrift ships with every Windows and looks contemporary. For a custom face, drop the `.ttf` into `edit/fonts/` and point `fontsdir=fonts` in `build.py`.

## Techniques

**Scrim under text.** A bright background (a window behind the subject) destroys legibility. A gradient fixes it:

```css
.scrim-top{position:absolute;left:0;right:0;top:0;height:820px;
  background:linear-gradient(180deg,rgba(14,11,8,.72) 0%,rgba(14,11,8,.45) 55%,rgba(14,11,8,0) 100%)}
```

**Strike-through** as a pseudo-element with a slight tilt — livelier than a straight line:

```css
.strike{position:relative;color:#C7523B}
.strike:after{content:'';position:absolute;left:-6px;right:-6px;top:52%;height:7px;
  background:#C7523B;transform:rotate(-3deg);border-radius:4px}
```

**Bullets appearing one at a time** — two cards with identical markup, placed back to back in time:

```html
<div class='row off'>...</div>   <!-- opacity:0 -->
<div class='row hi'>...</div>    <!-- revealed and highlighted -->
```

**Accent border** on the left edge of a panel (`border-left:9px solid #E8A33D`) — a cheap way to make a card feel designed.

**A shadow is mandatory**, otherwise the panel looks pasted on: `box-shadow:0 26px 70px rgba(0,0,0,.42)`.

## Subtitles

The style lives in the constants at the top of `make_ass.py`:

| Constant | Value | Meaning |
|---|---|---|
| `FONT_SIZE` | 72 | any larger and lines start to clip |
| `MARGIN_V` | 420 | bottom offset, clears the platform UI |
| `MARGIN_H` | 70 | side margins |
| `MAX_WORDS` | 3 | words per line |
| `MAX_GAP` | 0.7 | pause that forces a line break |
| `ACCENT` | `&H00A9F5FF` | the active word |

**ASS colours are BGR, not RGB.** `&H00A9F5FF` is yellow. It is easy to get backwards and end up with blue.

`WrapStyle: 0` is mandatory — at `2` a long line runs off the screen instead of wrapping.

The active word is tinted and scaled up by 8 % (`\fscx108\fscy108`). Beyond 110 % the line starts jumping around as its width changes.

## What not to do

- Neon colours and four-pixel outlines. They work for entertainment content and destroy credibility in expert content.
- More than two accent colours.
- A card for every sentence — that produces a slide deck, not a video.
- Animation for its own sake: a 0.25 s `fade` is enough; fly-ins and bounces pull attention away from the speech.
- Small type. This is watched on a phone held in one hand; 36 px is the floor, and only for captions.
