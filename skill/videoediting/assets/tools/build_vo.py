"""Сборка рилса под закадровую озвучку: видеоряд из разных клипов + отдельная аудиодорожка.

Usage:
  python build_vo.py base   <edl.json>       # нарезка + грейд + склейка -> work/<name>_base.mp4
  python build_vo.py final  <edl.json>       # оверлеи + субтитры + озвучка -> out/<name>.mp4

Отличие от build.py из скилла: звук берётся не из исходника, а из файла `voice`.
Видеоряд подгоняется под длительность озвучки.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../edit
WORK = os.path.join(ROOT, "work")
OUT = os.path.join(ROOT, "out")
OVL = os.path.join(ROOT, "overlays")

W, H, FPS = 1080, 1920, 30

GRADE = (
    "eq=contrast=1.10:brightness=0.020:saturation=1.05:gamma=1.10,"
    "curves=all='0/0 0.25/0.33 0.75/0.80 1/1',"
    "unsharp=5:5:0.40"
)


def run(cmd, cwd=None):
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd)[:300], flush=True)
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(p.stderr[-4000:])
        sys.exit(p.returncode)
    return p


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def base_path(edl_path):
    name = os.path.splitext(os.path.basename(edl_path))[0]
    return os.path.join(WORK, f"{name}_base.mp4"), name


def build_base(edl_path):
    edl = load(edl_path)
    segs = edl["segments"]
    srcs = []            # уникальные исходники -> индекс входа
    for s in segs:
        if s["src"] not in srcs:
            srcs.append(s["src"])

    inputs = []
    for p in srcs:
        inputs += ["-i", p]

    parts = []
    for i, s in enumerate(segs):
        idx = srcs.index(s["src"])
        zoom = s.get("zoom", 1.0)
        vf = (
            f"[{idx}:v]trim=start={s['start']}:end={s['end']},setpts=PTS-STARTPTS,"
            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},{GRADE}"
        )
        if zoom != 1.0:
            cw, ch = int(W / zoom) // 2 * 2, int(H / zoom) // 2 * 2
            vf += f",crop={cw}:{ch}:(iw-{cw})/2:(ih-{ch})/2,scale={W}:{H}:flags=lanczos"
        vf += f",setsar=1,format=yuv420p[v{i}]"
        parts.append(vf)

    concat_in = "".join(f"[v{i}]" for i in range(len(segs)))
    parts.append(f"{concat_in}concat=n={len(segs)}:v=1:a=0[vout]")

    os.makedirs(WORK, exist_ok=True)
    out, _ = base_path(edl_path)
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning", *inputs,
        "-filter_complex", ";".join(parts), "-map", "[vout]", "-an",
        "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
        out,
    ])
    total = sum(s["end"] - s["start"] for s in segs)
    print(f"\n{os.path.basename(out)}: {len(segs)} сегментов, {total:.2f} c")


def build_final(edl_path):
    """Собирает финал. Тайминг оверлеев берётся из overlays-<name>.json, а НЕ из EDL:
    EDL остаётся маленьким и не мутирует — иначе каждая правка тянет весь файл в контекст."""
    edl = load(edl_path)
    base, name = base_path(edl_path)
    short = name[4:] if name.startswith("edl-") else name

    ovl_spec = os.path.join(ROOT, f"overlays-{short}.json")
    if os.path.exists(ovl_spec):
        tl = load(ovl_spec).get("timeline", [])
        ovl_dir = os.path.join(OVL, short)
    else:                                  # запасной путь: старый формат
        tl = edl.get("overlays", [])
        ovl_dir = edl.get("ovl_dir", OVL)

    subs_path = os.path.join(ROOT, f"subs-{short}.ass")
    subs = f"subs-{short}.ass" if os.path.exists(subs_path) else edl.get("subs")

    inputs = ["-i", base, "-i", edl["voice"]]
    for item in tl:
        dur = item["out"] - item["in"]
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}",
                   "-i", os.path.join(ovl_dir, item["id"] + ".png")]

    parts, last = [], "0:v"
    for n, item in enumerate(tl, start=2):   # 0 = base, 1 = voice
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

    if subs:
        parts.append(f"[{last}]subtitles={subs}:fontsdir='C\\:/Windows/Fonts'[vout]")
    else:
        parts.append(f"[{last}]null[vout]")
    parts.append("[1:a]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")

    os.makedirs(OUT, exist_ok=True)
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", "-shortest",
        os.path.join(OUT, f"{name}.mp4"),
    ], cwd=ROOT)
    print(f"\nout/{name}.mp4 готов")


if __name__ == "__main__":
    mode, path = sys.argv[1], sys.argv[2]
    {"base": build_base, "final": build_final}[mode](path)
