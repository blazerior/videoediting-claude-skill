"""Transcribe the source with word-level timings via a cloud Whisper API
(Groq or OpenAI) instead of a local faster-whisper model.

Usage: python transcribe_cloud.py <audio.wav> <out_dir>
Env:   GROQ_API_KEY or OPENAI_API_KEY (Groq is tried first if both are set)
       WHISPER_LANG (en/ru/...), WHISPER_BACKEND (groq/openai, forces one)

Use this instead of transcribe.py when there is no GPU, no 4 GB to spare for
the model download, or the first-run wait (see setup.md) is not worth it for
a one-off edit. Trade-off: per-word confidence is not returned by these APIs,
so the "p" field is approximated from the segment's average log-probability —
proofreading via dump_words.py is still useful but less precise than local.

Output is byte-for-byte compatible with transcribe.py: transcript.json with
the same {language, duration, segments:[{id,start,end,text,words:[{w,s,e,p}]}]}
shape, plus transcript.srt. Every other tool in this pipeline is agnostic to
which script produced transcript.json.

Same underlying model, same hallucination risk: Whisper fabricates text over
silence, most infamously a fake subtitler credit line on Russian audio. Segments
whose own avg_logprob/no_speech_prob say they probably aren't real speech are
dropped automatically (see NO_SPEECH_CUTOFF below) — not airtight, so still
eyeball the first and last segment of transcript.json. See troubleshooting.md #17.
"""
import json
import math
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

SRC = sys.argv[1] if len(sys.argv) > 1 else "audio.wav"
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "."
LANG = os.environ.get("WHISPER_LANG") or None

MAX_UPLOAD_BYTES = 24 * 1024 * 1024  # both providers cap at 25 MB; leave headroom
MAX_ATTEMPTS = 4
MAX_429_RETRIES = 2
RETRY_BASE_DELAY = 2.0

BACKENDS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/audio/transcriptions",
        "model": "whisper-large-v3",
        "env": "GROQ_API_KEY",
    },
    "openai": {
        "url": "https://api.openai.com/v1/audio/transcriptions",
        "model": "whisper-1",
        "env": "OPENAI_API_KEY",
    },
}


def load_env_file(path):
    """Minimal .env reader — KEY=value per line, no quoting rules. No extra dependency."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def pick_backend():
    forced = os.environ.get("WHISPER_BACKEND")
    order = [forced] if forced else ["groq", "openai"]
    for name in order:
        cfg = BACKENDS.get(name)
        if cfg and os.environ.get(cfg["env"]):
            return name, cfg, os.environ[cfg["env"]]
    sys.exit(
        "No API key found. Set GROQ_API_KEY (recommended, free tier) or OPENAI_API_KEY "
        "as an environment variable, or put one in a .env file next to the audio file."
    )


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(p.stderr[-2000:])
        sys.exit(f"FAILED: {' '.join(cmd)[:200]}")
    return p.stdout


def ffprobe_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(out.strip())


def compress_for_upload(src, work_dir):
    """Re-encode to mono 64 kbps mp3 — shrinks a long recording well under the
    upload cap so most single-reel audio needs exactly one chunk."""
    dst = os.path.join(work_dir, f"_upload_{uuid.uuid4().hex[:8]}.mp3")
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-ac", "1", "-b:a", "64k", dst])
    return dst


def split_into_chunks(compressed, work_dir, duration):
    size = os.path.getsize(compressed)
    if size <= MAX_UPLOAD_BYTES:
        return [(0.0, compressed)]
    bytes_per_sec = size / duration
    segment_time = max(30, int(MAX_UPLOAD_BYTES / bytes_per_sec * 0.9))  # 10% safety margin
    pattern = os.path.join(work_dir, f"_chunk_{uuid.uuid4().hex[:8]}_%03d.mp3")
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", compressed,
        "-f", "segment", "-segment_time", str(segment_time), "-c", "copy", pattern,
    ])
    prefix = os.path.basename(pattern).split("%03d")[0]
    files = sorted(f for f in os.listdir(work_dir) if f.startswith(prefix))
    chunks, offset = [], 0.0
    for fn in files:
        path = os.path.join(work_dir, fn)
        chunks.append((offset, path))
        offset += ffprobe_duration(path)
    return chunks


def encode_multipart(fields, file_field, file_path):
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields:
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    filename = os.path.basename(file_path)
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(file_path, "rb") as f:
        data = f.read()
    parts.append(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode() + data + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", b"".join(parts)


def post_whisper(cfg, api_key, file_path):
    fields = [
        ("model", cfg["model"]),
        ("response_format", "verbose_json"),
        ("timestamp_granularities[]", "word"),
        ("timestamp_granularities[]", "segment"),
    ]
    if LANG:
        fields.append(("language", LANG))
    content_type, body = encode_multipart(fields, "file", file_path)

    last_err = None
    retries_429 = 0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(cfg["url"], data=body, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", content_type)
        req.add_header("User-Agent", "videoediting-skill/1.0")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode("utf-8", "replace")
            if e.code == 429 and retries_429 < MAX_429_RETRIES:
                retries_429 += 1
                delay = float(e.headers.get("Retry-After", RETRY_BASE_DELAY * attempt))
                print(f"rate limited, retrying in {delay:.0f}s...", flush=True)
                time.sleep(delay)
                continue
            if 400 <= e.code < 500:
                sys.exit(f"API error {e.code}: {body_txt[:500]}")
            last_err = f"{e.code}: {body_txt[:300]}"
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = str(e)
        delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
        print(f"attempt {attempt} failed ({last_err}), retrying in {delay:.0f}s...", flush=True)
        time.sleep(delay)
    sys.exit(f"All {MAX_ATTEMPTS} attempts failed: {last_err}")


def confidence_from_logprob(seg):
    return max(0.0, min(1.0, math.exp(seg.get("avg_logprob", -0.1))))


# Same guard as transcribe.py: Whisper (the model behind both APIs) hallucinates
# fabricated text over silence, most infamously a fake subtitler credit line on
# Russian audio. A segment this deep into "probably silence" while also this
# low-confidence is very rarely real speech. See troubleshooting.md #17.
NO_SPEECH_CUTOFF = 0.6
LOGPROB_CUTOFF = -0.5


def parse_response(resp, offset):
    """Groq/OpenAI return flat top-level words[] and segments[] (not nested).
    Re-nest words under their segment and offset every timestamp by the chunk start."""
    words = resp.get("words", [])
    segments = resp.get("segments") or [{
        "id": 0, "start": 0.0, "end": words[-1]["end"] if words else 0.0,
        "text": resp.get("text", ""), "avg_logprob": -0.1,
    }]
    out = []
    for seg in segments:
        no_speech = seg.get("no_speech_prob", 0.0)
        avg_logprob = seg.get("avg_logprob", 0.0)
        if no_speech > NO_SPEECH_CUTOFF and avg_logprob < LOGPROB_CUTOFF:
            print(f"HALLUCINATION SUSPECTED, DROPPED [{seg['start']+offset:6.2f} -> {seg['end']+offset:6.2f}] "
                  f"(no_speech={no_speech:.2f} logprob={avg_logprob:.2f}): {seg['text'].strip()!r}", flush=True)
            continue
        p = confidence_from_logprob(seg)
        seg_words = [
            {"w": w["word"].strip(), "s": round(w["start"] + offset, 3),
             "e": round(w["end"] + offset, 3), "p": round(p, 3)}
            for w in words
            if seg["start"] <= (w["start"] + w["end"]) / 2 < seg["end"]
        ]
        out.append({
            "start": round(seg["start"] + offset, 3),
            "end": round(seg["end"] + offset, 3),
            "text": seg["text"].strip(),
            "words": seg_words,
        })
    return out


def ts(sec: float) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


def main():
    load_env_file(os.path.join(os.path.dirname(os.path.abspath(SRC)), ".env"))
    load_env_file(os.path.join(os.getcwd(), ".env"))
    backend_name, cfg, api_key = pick_backend()
    os.makedirs(OUT_DIR, exist_ok=True)

    duration = ffprobe_duration(SRC)
    compressed = compress_for_upload(SRC, OUT_DIR)
    chunks = split_into_chunks(compressed, OUT_DIR, duration)
    print(f"backend={backend_name} chunks={len(chunks)} duration={duration:.1f}s", flush=True)

    all_segments = []
    for offset, chunk_path in chunks:
        resp = post_whisper(cfg, api_key, chunk_path)
        for seg in parse_response(resp, offset):
            all_segments.append(seg)
            print(f"[{seg['start']:6.2f} -> {seg['end']:6.2f}] {seg['text']}", flush=True)

    # clean up temp files
    os.remove(compressed)
    for _, chunk_path in chunks:
        if chunk_path != compressed and os.path.exists(chunk_path):
            os.remove(chunk_path)

    all_segments.sort(key=lambda s: s["start"])
    data = {"language": LANG or "auto", "duration": duration, "segments": [
        {"id": i, **seg} for i, seg in enumerate(all_segments)
    ]}

    with open(os.path.join(OUT_DIR, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    with open(os.path.join(OUT_DIR, "transcript.srt"), "w", encoding="utf-8") as f:
        for i, seg in enumerate(data["segments"], 1):
            f.write(f"{i}\n{ts(seg['start'])} --> {ts(seg['end'])}\n{seg['text']}\n\n")

    print(f"\nOK: {len(data['segments'])} segments -> {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
