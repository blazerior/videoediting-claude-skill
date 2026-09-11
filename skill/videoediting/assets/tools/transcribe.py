"""Transcribe the source with word-level timings (faster-whisper).

Usage: python transcribe.py <audio.wav> <out_dir>
Env:   WHISPER_MODEL (default large-v3), WHISPER_LANG (en/ru/...), WHISPER_DEVICE (cpu/cuda)

Always export HF_HUB_DISABLE_XET=1 before the first run, otherwise the model
download stalls after a few megabytes. See references/troubleshooting.md.

Whisper hallucinates fabricated text over silence and trailing dead air —
most infamously, on Russian audio, a fake subtitler credit line ("Субтитры
создал DimaTorzhok" and close variants). This is a known artefact of its
YouTube-caption training data, not a bug in this script, and it will keep
happening on some fraction of clips no matter what model or version is used.
Three layers guard against it below: hallucination_silence_threshold (skips
decoding into long silences), condition_on_previous_text=False (stops one
hallucinated segment from seeding another), and a post-filter that drops any
segment whose own confidence scores say it probably isn't real speech. None
of the three is airtight — always eyeball the first and last segment of
transcript.json before it goes anywhere near subtitles. See
references/troubleshooting.md #17.
"""
import json
import os
import sys

from faster_whisper import WhisperModel

SRC = sys.argv[1] if len(sys.argv) > 1 else "audio.wav"
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "."
MODEL = os.environ.get("WHISPER_MODEL", "large-v3")
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")

# A segment this deep into "probably silence" (no_speech_prob) while also
# this low-confidence (avg_logprob) is very rarely real speech worth keeping.
NO_SPEECH_CUTOFF = 0.6
LOGPROB_CUTOFF = -0.5

os.makedirs(OUT_DIR, exist_ok=True)

model = WhisperModel(MODEL, device=DEVICE, compute_type="int8" if DEVICE == "cpu" else "float16")
segments, info = model.transcribe(
    SRC,
    language=os.environ.get("WHISPER_LANG") or None,
    word_timestamps=True,
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 300},
    beam_size=5,
    condition_on_previous_text=False,
    hallucination_silence_threshold=2.0,
)

print(f"language={info.language} prob={info.language_probability:.2f}", flush=True)

data = {"language": info.language, "duration": info.duration, "segments": []}
for seg in segments:
    if seg.no_speech_prob > NO_SPEECH_CUTOFF and seg.avg_logprob < LOGPROB_CUTOFF:
        print(f"HALLUCINATION SUSPECTED, DROPPED [{seg.start:6.2f} -> {seg.end:6.2f}] "
              f"(no_speech={seg.no_speech_prob:.2f} logprob={seg.avg_logprob:.2f}): {seg.text.strip()!r}",
              flush=True)
        continue
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
