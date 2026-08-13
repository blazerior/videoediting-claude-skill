"""Batch pipeline: run every stage over every reel in the project, with caching.

Usage:
  python pipeline.py <stage> [--only 1a,2b] [--force] [--project project.json]

Stages, in order:
  ingest      inventory every media file            -> work/media.json
  transcribe  all voiceovers at once                -> work/vo/<id>/transcript.json
  probe       scene cuts + contact sheets           -> work/shots.json, work/sheets/
  overlays    render graphics for every reel        -> overlays/<reel>/
  subs        build subtitles for every reel        -> subs-<reel>.ass
  base        cut + grade video track for every reel-> work/<reel>_base.mp4
  final       composite everything                  -> out/<reel>.mp4
  qa          one contact strip for ALL reels       -> work/qa.png + text report
  all         every stage in order

Why it exists: editing ten reels one at a time burns context — every file edit
echoes the whole file back, every check costs an image. Here each stage runs
once over the whole project, caches by input hash, and prints one line per reel.
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
WORK = os.path.join(ROOT, "work")
CACHE = os.path.join(WORK, ".cache")
OUT = os.path.join(ROOT, "out")

STAGES = ["ingest", "transcribe", "probe", "overlays", "subs", "base", "final", "qa"]


# ---------------------------------------------------------------- helpers

def log(msg):
    print(msg, flush=True)


def sh(args, cwd=None, quiet=True):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(p.stdout[-2000:])
        print(p.stderr[-3000:])
        sys.exit(f"FAILED: {' '.join(str(a) for a in args)[:200]}")
    return p.stdout


def py(script, *args, cwd=None):
    return sh([sys.executable, os.path.join(TOOLS, script), *[str(a) for a in args]], cwd=cwd)


def digest(*parts):
    h = hashlib.sha1()
    for p in parts:
        if isinstance(p, str) and os.path.exists(p):
            h.update(str(os.path.getmtime(p)).encode())
            h.update(str(os.path.getsize(p)).encode())
        else:
            h.update(json.dumps(p, sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()[:16]


def cached(key, sig):
    """True if this step already ran with the same inputs."""
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, key + ".sig")
    if os.path.exists(f) and open(f, encoding="utf-8").read().strip() == sig:
        return True
    return False


def mark(key, sig):
    open(os.path.join(CACHE, key + ".sig"), "w", encoding="utf-8").write(sig)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- stages

def stage_ingest(proj, reels, force):
    """One inventory pass over the whole media folder — never repeat per reel."""
    src_dir = proj["media_dir"]
    sig = digest(sorted(os.listdir(src_dir)))
    if not force and cached("ingest", sig):
        log("ingest    : cached")
        return
    exts = {".mov", ".mp4", ".webm", ".mkv", ".m4v", ".mp3", ".wav", ".m4a"}
    items = []
    for dirpath, _, files in os.walk(src_dir):
        for fn in sorted(files):
            if os.path.splitext(fn)[1].lower() not in exts:
                continue
            p = os.path.join(dirpath, fn)
            out = sh(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                      "-print_format", "json", p])
            d = json.loads(out)
            v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
            a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
            rot = 0
            if v:
                for sd in v.get("side_data_list", []):
                    if "rotation" in sd:
                        rot = int(sd["rotation"])
            w, h = (v["width"], v["height"]) if v else (0, 0)
            if abs(rot) == 90:      # display size, not stream size
                w, h = h, w
            items.append({
                "path": os.path.relpath(p, src_dir),
                "abs": p,
                "dur": round(float(d["format"].get("duration", 0)), 2),
                "w": w, "h": h, "rotation": rot,
                "vcodec": v["codec_name"] if v else None,
                "acodec": a["codec_name"] if a else None,
            })
    dump(os.path.join(WORK, "media.json"), {"dir": src_dir, "items": items})
    mark("ingest", sig)
    vert = sum(1 for i in items if i["h"] > i["w"])
    log(f"ingest    : {len(items)} файлов, вертикальных {vert}, -> work/media.json")


def stage_transcribe(proj, reels, force):
    """Every voiceover in one model load."""
    voices = proj.get("voices", {})
    todo = {}
    for vid, v in voices.items():
        sig = digest(v["file"], proj.get("whisper_model", ""))
        if force or not cached(f"tr-{vid}", sig):
            todo[vid] = v["file"]
    if not todo:
        log(f"transcribe: cached ({len(voices)})")
        return
    dump(os.path.join(WORK, "vo-map.json"), todo)
    env = dict(os.environ)
    env.setdefault("HF_HUB_DISABLE_XET", "1")
    if proj.get("whisper_model"):
        env["WHISPER_MODEL"] = proj["whisper_model"]
    if proj.get("lang"):
        env["WHISPER_LANG"] = proj["lang"]
    p = subprocess.run([sys.executable, os.path.join(TOOLS, "batch_vo.py"),
                        os.path.join(WORK, "vo-map.json"), os.path.join(WORK, "vo")],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(p.stderr[-3000:])
        sys.exit("transcribe failed")
    for vid in todo:
        mark(f"tr-{vid}", digest(voices[vid]["file"], proj.get("whisper_model", "")))
    log(f"transcribe: {len(todo)} новых, {len(voices) - len(todo)} из кэша")


def stage_probe(proj, reels, force):
    """Scene cuts + one contact sheet per source. Read the sheets ONCE, not per reel."""
    media = load(os.path.join(WORK, "media.json"))
    sheets = os.path.join(WORK, "sheets")
    os.makedirs(sheets, exist_ok=True)
    shots = {}
    made = 0
    for it in media["items"]:
        if not it["vcodec"] or it["dur"] < 1:
            continue
        key = os.path.splitext(os.path.basename(it["path"]))[0]
        sig = digest(it["abs"])
        sheet = os.path.join(sheets, key + ".jpg")
        if not force and cached(f"probe-{key}", sig) and os.path.exists(sheet):
            shots[it["path"]] = load(os.path.join(WORK, "shots.json")).get(it["path"], []) \
                if os.path.exists(os.path.join(WORK, "shots.json")) else []
            continue
        out = sh(["ffmpeg", "-hide_banner", "-i", it["abs"], "-vf",
                  "select='gt(scene,0.25)',showinfo", "-an", "-f", "null", "-"])
        cuts = []
        for line in out.splitlines():
            if "pts_time:" in line:
                try:
                    cuts.append(round(float(line.split("pts_time:")[1].split()[0]), 2))
                except (IndexError, ValueError):
                    pass
        shots[it["path"]] = cuts
        step = max(it["dur"] / 8, 1.0)
        sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", it["abs"],
            "-vf", f"fps=1/{step:.2f},scale=160:-2,tile=8x1", "-frames:v", "1", "-q:v", "4", sheet])
        mark(f"probe-{key}", sig)
        made += 1
    dump(os.path.join(WORK, "shots.json"), shots)
    log(f"probe     : {made} новых раскадровок, всего {len(shots)} -> work/sheets/")


def stage_overlays(proj, reels, force):
    made = 0
    for name in reels:
        spec = os.path.join(ROOT, f"overlays-{name}.json")
        if not os.path.exists(spec):
            log(f"overlays  : {name} — нет overlays-{name}.json, пропуск")
            continue
        sig = digest(spec, proj.get("qr", ""))
        if not force and cached(f"ovl-{name}", sig):
            continue
        py("render_overlays.py", *_prep_overlays(proj, name, spec))
        mark(f"ovl-{name}", sig)
        made += 1
    log(f"overlays  : {made} пересобрано, {len(reels) - made} из кэша")


def _prep_overlays(proj, name, spec):
    """Inline the QR as a data URI, write the built spec into work/."""
    import base64
    import io
    from PIL import Image
    s = load(spec)
    qr = proj.get("qr")
    if qr:
        im = Image.open(qr).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        for it in s["items"]:
            it["html"] = it["html"].replace("QR_SRC", uri)
    built = os.path.join(WORK, f"ovl-{name}.built.json")
    dump(built, s)
    return built, os.path.join(ROOT, "overlays", name)


def stage_subs(proj, reels, force):
    made = 0
    for name, r in reels.items():
        vo = r.get("voice")
        if not vo:
            continue
        tr = os.path.join(WORK, "vo", vo, "transcript.json")
        corr = os.path.join(ROOT, f"corrections-{name}.json")
        edl = os.path.join(ROOT, f"edl-{name}.json")
        sig = digest(tr, corr if os.path.exists(corr) else "", edl, r.get("mute", []))
        if not force and cached(f"subs-{name}", sig):
            continue
        total = sum(s["end"] - s["start"] for s in load(edl)["segments"])
        span = os.path.join(WORK, f"span-{name}.json")
        dump(span, {"segments": [{"start": 0.0, "end": round(total + 0.2, 2)}]})
        subs = os.path.join(ROOT, f"subs-{name}.ass")
        args = [tr, span, subs] + ([corr] if os.path.exists(corr) else [])
        py("make_ass.py", *args)
        mute = r.get("mute", [])
        if mute:
            py("mute_subs.py", subs, *[f"{a}-{b}" for a, b in mute])
        mark(f"subs-{name}", sig)
        made += 1
    log(f"subs      : {made} пересобрано, {len(reels) - made} из кэша")


def stage_base(proj, reels, force):
    made = 0
    for name in reels:
        edl = os.path.join(ROOT, f"edl-{name}.json")
        sig = digest(edl, proj.get("grade", ""))
        if not force and cached(f"base-{name}", sig):
            continue
        py("build_vo.py", "base", edl)
        mark(f"base-{name}", sig)
        made += 1
    log(f"base      : {made} пересобрано, {len(reels) - made} из кэша")


def stage_final(proj, reels, force):
    made = 0
    for name, r in reels.items():
        edl = os.path.join(ROOT, f"edl-{name}.json")
        base = os.path.join(WORK, f"edl-{name}_base.mp4")
        subs = os.path.join(ROOT, f"subs-{name}.ass")
        ovl = os.path.join(ROOT, f"overlays-{name}.json")
        sig = digest(base, subs if os.path.exists(subs) else "", ovl if os.path.exists(ovl) else "")
        if not force and cached(f"final-{name}", sig):
            continue
        py("build_vo.py", "final", edl)
        made += 1
        mark(f"final-{name}", sig)
        title = r.get("title", name)
        src = os.path.join(OUT, f"edl-{name}.mp4")
        if r.get("title") and os.path.exists(src):
            import shutil
            shutil.copyfile(src, os.path.join(OUT, f"{title}.mp4"))
    log(f"final     : {made} пересобрано, {len(reels) - made} из кэша")


def stage_qa(proj, reels, force):
    """One strip for every reel + a text report. Read ONE image instead of N."""
    tmp = os.path.join(WORK, "qa")
    os.makedirs(tmp, exist_ok=True)
    rows, report = [], []
    for name, r in reels.items():
        f = os.path.join(OUT, f"edl-{name}.mp4")
        if not os.path.exists(f):
            continue
        dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", f]).strip())
        picks = [dur * x for x in (0.05, 0.22, 0.40, 0.58, 0.76, 0.94)]
        tiles = []
        for i, t in enumerate(picks):
            png = os.path.join(tmp, f"{name}_{i}.png")
            sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}",
                "-i", f, "-frames:v", "1", "-vf",
                "scale=150:267,setsar=1,pad=iw+4:ih+4:0:0:color=0x101010", png])
            tiles.append(png)
        row = os.path.join(tmp, f"row_{name}.png")
        args = []
        for t in tiles:
            args += ["-i", t]
        sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args,
            "-filter_complex", f"hstack=inputs={len(tiles)}", row])
        rows.append(row)
        # volumedetect пишет в stderr, а не в stdout
        vol = subprocess.run(["ffmpeg", "-hide_banner", "-i", f, "-af", "volumedetect",
                              "-f", "null", "-"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stderr
        mean = next((l.split("mean_volume:")[1].strip() for l in vol.splitlines()
                     if "mean_volume:" in l), "?")
        size = os.path.getsize(f) / 1024 / 1024
        report.append(f"  {name:<6} {dur:6.1f}s  {size:5.1f} MB  {mean}")
    if rows:
        args = []
        for r in rows:
            args += ["-i", r]
        sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args,
            "-filter_complex", f"vstack=inputs={len(rows)}", os.path.join(WORK, "qa.png")])
    log("qa        : work/qa.png — одна картинка на все ролики")
    log("\n  ролик  длит   размер   звук")
    for line in report:
        log(line)


# ---------------------------------------------------------------- main

FUNCS = {
    "ingest": stage_ingest, "transcribe": stage_transcribe, "probe": stage_probe,
    "overlays": stage_overlays, "subs": stage_subs, "base": stage_base,
    "final": stage_final, "qa": stage_qa,
}


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(f"stages: {', '.join(STAGES)}, all")
    stage = args[0]
    force = "--force" in args
    proj_path = os.path.join(ROOT, "project.json")
    if "--project" in args:
        proj_path = args[args.index("--project") + 1]
    proj = load(proj_path)
    reels = proj["reels"]
    if "--only" in args:
        keep = set(args[args.index("--only") + 1].split(","))
        reels = {k: v for k, v in reels.items() if k in keep}

    todo = STAGES if stage == "all" else [stage]
    for s in todo:
        if s not in FUNCS:
            sys.exit(f"unknown stage: {s}")
        FUNCS[s](proj, reels, force)


if __name__ == "__main__":
    main()
