"""Транскрипт с пословными таймкодами для всех озвучек разом (одна загрузка модели).

Usage: python batch_vo.py <map.json> <out_dir>
map.json: {"vo3": "путь.mp3", ...}
Для каждого ключа кладёт <out_dir>/<key>/transcript.json
"""
import json
import os
import subprocess
import sys

from faster_whisper import WhisperModel

files = json.load(open(sys.argv[1], encoding="utf-8"))
out_dir = sys.argv[2]
model_name = os.environ.get("WHISPER_MODEL", "mobiuslabsgmbh/faster-whisper-large-v3-turbo")

model = WhisperModel(model_name, device="cpu", compute_type="int8")

for key, path in files.items():
    d = os.path.join(out_dir, key)
    os.makedirs(d, exist_ok=True)
    wav = os.path.join(d, "audio.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", wav], check=False)
    segs, info = model.transcribe(wav, language="ru", word_timestamps=True, vad_filter=True,
                                  vad_parameters={"min_silence_duration_ms": 300}, beam_size=5)
    data = {"language": info.language, "duration": info.duration, "segments": []}
    for s in segs:
        data["segments"].append({
            "id": s.id, "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
            "words": [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3),
                       "p": round(w.probability, 3)} for w in (s.words or [])],
        })
    json.dump(data, open(os.path.join(d, "transcript.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    end = data["segments"][-1]["end"] if data["segments"] else 0
    print(f"\n=== {key}  (речь до {end:.2f}) ===", flush=True)
    for s in data["segments"]:
        print(f"  [{s['start']:6.2f} -> {s['end']:6.2f}] {s['text']}", flush=True)

print("\nготово")
