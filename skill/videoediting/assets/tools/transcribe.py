"""Transcribe the source with word-level timings (faster-whisper).

Usage: python transcribe.py <audio.wav> <out_dir>
Env:   WHISPER_MODEL (default large-v3), WHISPER_LANG (en/ru/...), WHISPER_DEVICE (cpu/cuda)

Always export HF_HUB_DISABLE_XET=1 before the first run, otherwise the model
download stalls after a few megabytes. See references/troubleshooting.md.
"""
import json
import os
import sys

from faster_whisper import WhisperModel

SRC = sys.argv[1] if len(sys.argv) > 1 else "audio.wav"
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "."
MODEL = os.environ.get("WHISPER_MODEL", "large-v3")
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")

os.makedirs(OUT_DIR, exist_ok=True)

model = WhisperModel(MODEL, device=DEVICE, compute_type="int8" if DEVICE == "cpu" else "float16")
segments, info = model.transcribe(
    SRC,
    language=os.environ.get("WHISPER_LANG") or None,
    word_timestamps=True,
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 300},
    beam_size=5,
)

print(f"language={info.language} prob={info.language_probability:.2f}", flush=True)

data = {"language": info.language, "duration": info.duration, "segments": []}
for seg in segments:
    words = [
        {"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3), "p": round(w.probability, 3)}
        for w in (seg.words or [])
    ]
    data["segments"].append(
        {"id": seg.id, "start": round(seg.start, 3), "end": round(seg.end, 3),
         "text": seg.text.strip(), "words": words}
    )
    print(f"[{seg.start:6.2f} -> {seg.end:6.2f}] {seg.text.strip()}", flush=True)

with open(os.path.join(OUT_DIR, "transcript.json"), "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)


def ts(sec: float) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


with open(os.path.join(OUT_DIR, "transcript.srt"), "w", encoding="utf-8") as f:
    for i, seg in enumerate(data["segments"], 1):
        f.write(f"{i}\n{ts(seg['start'])} --> {ts(seg['end'])}\n{seg['text']}\n\n")

print(f"\nOK: {len(data['segments'])} segments -> {OUT_DIR}", flush=True)
