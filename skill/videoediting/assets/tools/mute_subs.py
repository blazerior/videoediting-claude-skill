"""Убрать субтитры на заданных интервалах — там, где на экране полноэкранная карточка.

Usage: python mute_subs.py <subs.ass> <start-end> [<start-end> ...]
Пример: python mute_subs.py subs-1a.ass 0-2.30 31.30-34.30
"""
import sys


def sec(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


path = sys.argv[1]
ranges = []
for a in sys.argv[2:]:
    lo, hi = a.split("-")
    ranges.append((float(lo), float(hi)))

lines = open(path, encoding="utf-8-sig").read().splitlines()
out, dropped = [], 0
for line in lines:
    if line.startswith("Dialogue:"):
        p = line.split(",", 4)
        s, e = sec(p[1]), sec(p[2])
        if any(s < hi and e > lo for lo, hi in ranges):
            dropped += 1
            continue
    out.append(line)

open(path, "w", encoding="utf-8-sig").write("\n".join(out) + "\n")
print(f"убрано событий: {dropped}")
