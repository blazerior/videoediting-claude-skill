"""Print every word with its index and recognition confidence — for proofreading.

Usage: python dump_words.py <transcript.json>
Indices printed here are the keys used in corrections.json.
"""
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
ws = [w for s in d["segments"] for w in s["words"]]
for i, w in enumerate(ws):
    print(f"{i:3d} {w['s']:6.2f}-{w['e']:6.2f} p={w['p']:.2f}  {w['w']}")
