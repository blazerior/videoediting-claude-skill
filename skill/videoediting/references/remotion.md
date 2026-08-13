# Remotion — animated graphics layer

[Remotion](https://www.remotion.dev) renders React components to video. It does not replace this pipeline; it slots into it as a third graphics tier.

## Install

```bash
claude plugin marketplace add remotion-dev/claude-code-plugin
```

```bash
claude plugin install remotion@remotion
```

Restart Claude Code afterwards. The plugin exposes skills named `remotion:remotion-*` — a router plus one skill per topic (create, markup, captions, render, studio, multimedia, interactivity, maps, saas, docs, upgrade). Load them the same way as any other skill; `remotion:remotion-best-practices` is the entry point.

**On Windows the install can fail** with `No ED25519 host key is known for github.com`. The plugin clones over SSH, and the OpenSSH shipped with Windows is too old for GitHub's current key exchange, so `ssh-keyscan` cannot fetch the host key either. Get the keys over HTTPS instead:

```powershell
$meta = Invoke-RestMethod https://api.github.com/meta
foreach ($k in $meta.ssh_keys) { Add-Content "$env:USERPROFILE\.ssh\known_hosts" "github.com $k" -Encoding ascii }
```

**Licence:** free for individuals and small teams, paid for companies above a certain headcount. Check <https://remotion.pro> before shipping commercial work.

## The three graphics tiers

| Tier | Tool | Cost | Use for |
|---|---|---|---|
| Static | HTML/CSS → headless Chrome → PNG | instant | cards, badges, lower thirds, final QR frame |
| **Animated** | **Remotion → transparent video** | slow, needs Node | counters, staged reveals, spring motion, karaoke captions with real animation |
| Composite | ffmpeg | fast | cutting, grading, layering, audio |

Reach for Remotion only when the motion itself carries meaning. A card that fades in does not need React — `render_overlays.py` already does that for free. A number that counts from 0 to 200, a bar that fills, text that assembles word by word with spring physics: that is where it pays.

## How it plugs in

Render the graphics **with an alpha channel**, then treat the result as just another overlay input to ffmpeg.

```bash
npx remotion render --image-format=png --pixel-format=yuva444p10le --codec=prores --prores-profile=4444 MyOverlay overlay.mov
```

WebM is smaller if size matters:

```bash
npx remotion render --image-format=png --pixel-format=yuva420p --codec=vp9 MyOverlay overlay.webm
```

Then in the filtergraph, exactly like a PNG but without `-loop 1`:

```
-i overlay.mov
[1:v]format=rgba,setpts=PTS-STARTPTS+6.35/TB[o1];
[0:v][o1]overlay=0:0:eof_action=pass:repeatlast=0:enable='between(t,6.35,9.85)'[b1]
```

Keep the composition size identical to the reel (1080×1920) and the fps identical (30), or the overlay will drift.

## Batch: one composition, many reels

This is the real reason to bring Remotion into a ten-reel project. Define the graphics once, pass different props per reel:

```bash
npx remotion render MyOverlay out/1a.mov --props='{"headline":"200 VPN blocked","accent":"#7DDA58"}'
```

Drive it from `project.json` in a loop and the entire graphics layer for ten reels regenerates from one component. Changing the brand colour becomes a one-line edit instead of ten.

## Captions

`@remotion/captions` has `createTikTokStyleCaptions()`, which groups word-level timings into pages and exposes per-token `fromMs`/`toMs` for highlighting the active word. It consumes the same word-level data this pipeline already produces — `work/vo/<id>/transcript.json` maps onto the `Caption` format with a trivial rename.

Worth it when you want the words to animate (scale, spring, colour sweep). Not worth it for plain highlighted captions: `make_ass.py` already does those, burns them in one ffmpeg pass, and costs no Node install.

## When not to use it

- **The reel is a screencast with cards.** ffmpeg plus Chrome PNGs is faster end to end and has no build step.
- **You need it now.** First render pulls a headless browser and renders frame by frame — much slower than an ffmpeg overlay pass.
- **The project must run on a machine without Node.**

The honest split: this pipeline stays the backbone, Remotion is what you add when a client asks for motion the CSS layer cannot fake.
