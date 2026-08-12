"""Assemble the edit: EDL -> cut + grade -> overlays + subtitles -> final file.

Usage:
  python build.py base     # stage 1: cut, grade, concat  -> work/base.mp4
  python build.py final    # stage 2: overlays, subtitles, audio -> out/final.mp4

The two stages are separate on purpose: `base` is slow, `final` is fast, and
graphics get iterated far more often than the cut does.
"""
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../edit
WORK = os.path.join(ROOT, "work")
OUT = os.path.join(ROOT, "out")
OVL = os.path.join(ROOT, "overlays")

W, H, FPS = 1080, 1920, 30
AFADE = 0.03  # 30 ms at every cut edge — stops clicks

GRADE = (
    "eq=contrast=1.13:brightness=0.012:saturation=1.07:gamma=1.07,"
    "curves=all='0/0 0.22/0.285 0.75/0.795 1/1':r='0/0 0.5/0.515 1/1':b='0/0 0.5/0.492 1/1',"
    "vignette=PI/9,"
    "unsharp=5:5:0.45"
)

FONTSDIR = "C\\:/Windows/Fonts" if platform.system() == "Windows" else "/System/Library/Fonts"


def run(cmd, cwd=None):
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd)[:400], flush=True)
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(p.stderr[-4000:])
        sys.exit(p.returncode)
    return p


def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)


def build_base():
    edl = load("edl.json")
    src = edl["source"]
    segs = edl["segments"]
    parts = []
    for i, s in enumerate(segs):
        dur = s["end"] - s["start"]
        zoom = s.get("zoom", 1.0)
        vf = (
            f"[0:v]trim=start={s['start']}:end={s['end']},setpts=PTS-STARTPTS,"
            f"scale={W}:{H}:flags=lanczos,fps={FPS},{GRADE}"
        )
        if zoom != 1.0:
            cw, ch = int(W / zoom) // 2 * 2, int(H / zoom) // 2 * 2
            vf += f",crop={cw}:{ch}:(iw-{cw})/2:(ih-{ch})/2,scale={W}:{H}:flags=lanczos"
        vf += f",setsar=1,format=yuv420p[v{i}]"   # without setsar+format concat dies with -22
        af = (
            f"[0:a]atrim=start={s['start']}:end={s['end']},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={AFADE},afade=t=out:st={max(dur - AFADE, 0):.3f}:d={AFADE},"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a{i}]"
        )
        parts += [vf, af]
    concat_in = "".join(f"[v{i}][a{i}]" for i in range(len(segs)))
    parts.append(f"{concat_in}concat=n={len(segs)}:v=1:a=1[vout][aout]")

    os.makedirs(WORK, exist_ok=True)
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning", "-i", src,
        "-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        os.path.join(WORK, "base.mp4"),
    ])
    total = sum(s["end"] - s["start"] for s in segs)
    print(f"\nbase.mp4 ready: {len(segs)} segments, {total:.1f} s")


def build_final():
    tl = load("overlays.json").get("timeline", [])
    inputs = ["-i", os.path.join(WORK, "base.mp4")]
    for item in tl:
        dur = item["out"] - item["in"]
        # -t is mandatory: without it -loop 1 makes an infinite stream and eats all memory
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}",
                   "-i", os.path.join(OVL, item["id"] + ".png")]

    parts, last = [], "0:v"
    for n, item in enumerate(tl, start=1):
        f = item.get("fade", 0.25)
        tin, tout = item["in"], item["out"]
        dur = tout - tin
        parts.append(
            f"[{n}:v]format=rgba,fade=t=in:st=0:d={f}:alpha=1,"
            f"fade=t=out:st={max(dur - f, 0):.3f}:d={f}:alpha=1,"
            f"setpts=PTS-STARTPTS+{tin}/TB[o{n}]"
        )
        parts.append(
            f"[{last}][o{n}]overlay=0:0:eof_action=pass:repeatlast=0:"
            f"enable='between(t,{tin},{tout})'[b{n}]"
        )
        last = f"b{n}"

    # ffmpeg runs with cwd=ROOT: a relative path avoids the drive-letter colon in the filtergraph
    parts.append(f"[{last}]subtitles=subs.ass:fontsdir='{FONTSDIR}'[vout]")
    parts.append("[0:a]loudnorm=I=-14:TP=-1.5:LRA=11[aout]")

    os.makedirs(OUT, exist_ok=True)
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", "-shortest",
        os.path.join(OUT, "final.mp4"),
    ], cwd=ROOT)
    print("\nfinal.mp4 ready")


if __name__ == "__main__":
    {"base": build_base, "final": build_final}[sys.argv[1]]()
