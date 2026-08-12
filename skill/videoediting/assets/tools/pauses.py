"""List the pauses between words — the basis for the edit list.

Usage: python pauses.py <transcript.json> [threshold_seconds]
"""
import json
import sys

path = sys.argv[1]
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.30

d = json.load(open(path, encoding="utf-8"))
ws = [w for s in d["segments"] for w in s["words"]]
print(f"words: {len(ws)}  speech ends at {ws[-1]['e']:.2f}")
print(f"--- pauses longer than {thr:.2f} ---")
prev = None
total = 0.0
for w in ws:
    if prev and w["s"] - prev["e"] > thr:
        gap = w["s"] - prev["e"]
        total += gap
        print(f"{prev['e']:6.2f} -> {w['s']:6.2f}  ({gap:4.2f})   ...{prev['w']}  ||  {w['w']}...")
    prev = w
print(f"total time in pauses: {total:.2f} s")
