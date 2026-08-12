"""Word-level ASS subtitles (karaoke style) built from transcript.json, re-timed via the EDL.

Usage: python make_ass.py <transcript.json> <edl.json> <out.ass> [corrections.json]

The EDL lists source timecodes; this script keeps only the words that survive the
cut and shifts them onto the final timeline.
"""
import json
import os
import platform
import sys

W, H = 1080, 1920
FONT = "Bahnschrift SemiBold" if platform.system() == "Windows" else "Helvetica Neue"
FONT_SIZE = 72
MARGIN_H = 70
MARGIN_V = 420           # bottom offset — clears the Reels/Shorts UI
ACCENT = "&H00A9F5FF"    # active word. NOTE: ASS colours are BGR, not RGB
BASE = "&H00FFFFFF"      # the other words: white
MAX_WORDS = 3            # words per line
MAX_GAP = 0.7            # a pause this long forces a line break


def esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def ts(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):d}:{int(m):02d}:{s:05.2f}"


def load_words(transcript_path, corrections_path=None):
    with open(transcript_path, encoding="utf-8") as f:
        data = json.load(f)
    fixes = {}
    if corrections_path and os.path.exists(corrections_path):
        with open(corrections_path, encoding="utf-8") as f:
            fixes = {k: v for k, v in json.load(f).items() if k.isdigit()}
    words = []
    idx = 0
    for seg in data["segments"]:
        for w in seg.get("words", []):
            text = fixes.get(str(idx), w["w"])
            idx += 1
            if text:
                item = dict(w)
                item["w"] = text
                words.append(item)
    return words


def remap(words, edl):
    """Keep only words inside EDL segments and shift them onto the final timeline."""
    out = []
    offset = 0.0
    for seg in edl["segments"]:
        s, e = seg["start"], seg["end"]
        for w in words:
            mid = (w["s"] + w["e"]) / 2
            if s <= mid < e:
                out.append({
                    "w": w["w"],
                    "s": round(w["s"] - s + offset, 3),
                    "e": round(min(w["e"], e) - s + offset, 3),
                })
        offset += e - s
    return out


def group(words):
    lines, cur = [], []
    for w in words:
        if cur and (len(cur) >= MAX_WORDS or w["s"] - cur[-1]["e"] > MAX_GAP):
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return lines


HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{FONT},{FONT_SIZE},{BASE},{BASE},&H00181818,&H90000000,-1,0,0,0,100,100,1,0,1,5,3,2,{MARGIN_H},{MARGIN_H},{MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def main():
    transcript_path, edl_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    corrections = sys.argv[4] if len(sys.argv) > 4 else None
    words = load_words(transcript_path, corrections)
    with open(edl_path, encoding="utf-8") as f:
        edl = json.load(f)
    words = remap(words, edl)

    events = []
    lines = group(words)
    for li, line in enumerate(lines):
        next_line_start = lines[li + 1][0]["s"] if li + 1 < len(lines) else None
        for i, active in enumerate(line):
            parts = []
            for j, w in enumerate(line):
                colour = ACCENT if j == i else BASE
                scale = r"\fscx108\fscy108" if j == i else ""
                parts.append(rf"{{\c{colour}{scale}}}{esc(w['w'])}")
            start = active["s"]
            if i + 1 < len(line):
                end = line[i + 1]["s"]
            else:
                end = active["e"] + 0.35
                if next_line_start is not None:
                    end = min(end, next_line_start - 0.02)
            if end - start < 0.08:
                end = start + 0.08
            events.append([start, end, " ".join(parts)])

    # no event may run into the next one, or libass draws both lines on top of each other
    events.sort(key=lambda e: e[0])
    for a, b in zip(events, events[1:]):
        if a[1] > b[0]:
            a[1] = b[0]

    lines_out = [f"Dialogue: 0,{ts(s)},{ts(e)},Cap,,0,0,0,,{t}" for s, e, t in events if e > s]

    with open(out_path, "w", encoding="utf-8-sig") as f:
        f.write(HEADER)
        f.write("\n".join(lines_out) + "\n")
    print(f"OK: {len(lines_out)} events, {len(words)} words -> {out_path}")


if __name__ == "__main__":
    main()
