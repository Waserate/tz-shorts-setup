"""Reflow the title card to a fixed number of lines, keeping the styling it already has.

The user restyled the title inside CapCut (colour, weight) and then asked for it to sit on
exactly two lines. Rebuilding it from a donor would throw that styling away, so this edits
the card in place: same material, same colour, same stroke — only the line break and the size
change.

The break is chosen to make the two lines as even as possible, because the size a title can
take is set by its WIDEST line: an even split is the largest the words can be drawn.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time

from style_captions import room_units, width_per_px
from thai_subtitle import tokenize


from config import CAPCUT_ROOT, BACKUP_DIR


def best_break(text: str, lines: int):
    """Split into `lines` pieces so the widest piece is as narrow as possible."""
    # Thai does not space its words, so splitting on spaces leaves one huge unbreakable
    # piece and forces the title small. Tokenising gives real break points — but the pieces
    # are cut out of the ORIGINAL string by offset, because re-joining tokens loses the
    # spaces around the Latin words ("เมื่อ Vegan 14 ปี" came back as "เมื่อVegan14ปี").
    flat = text.replace("\n", " ")
    offsets, at = [], 0
    for tok in tokenize(flat):
        offsets.append(at)
        at += len(tok)
    cuts = [o for o in offsets[1:] if flat[:o].strip() and flat[o:].strip()]
    if lines <= 1 or len(cuts) < lines - 1:
        return [flat.strip()]

    best, out = None, None

    def walk(start, acc):
        nonlocal best, out
        if len(acc) == lines - 1:
            pieces = acc + [flat[start:].strip()]
            if not all(pieces):
                return
            widest = max(width_per_px(p) for p in pieces)
            if best is None or widest < best:
                best, out = widest, pieces
            return
        for c in cuts:
            if c > start:
                walk(c, acc + [flat[start:c].strip()])

    walk(0, [])
    return out or [flat.strip()]


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--lines", type=int, default=2)
    p.add_argument("--box", type=float, default=0.94)
    p.add_argument("--max-size", type=float, default=34.0)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    path = os.path.join(CAPCUT_ROOT, a.draft, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))
    by = {m["id"]: m for m in draft["materials"]["texts"]}

    titles = [(t, s) for t in draft["tracks"] if t["type"] == "text"
              and len(t["segments"]) == 1 for s in t["segments"]]
    if not titles:
        raise SystemExit("no title track (a text track holding a single card)")
    _, seg = titles[0]
    mat = by[seg["material_id"]]
    content = json.loads(mat["content"])
    old_text = content["text"]

    pieces = best_break(old_text, a.lines)
    text = "\n".join(pieces)
    room = room_units(draft["canvas_config"]["width"], a.box)
    size = round(min(a.max_size, room / max(width_per_px(p) for p in pieces)), 3)

    fill = (content.get("styles") or [{}])[0].get("fill", {})
    colour = fill.get("content", {}).get("solid", {}).get("color")
    print(f"เดิม {old_text!r}")
    print(f"ใหม่ {text!r}")
    print(f"  {a.lines} บรรทัด  ขนาด {size}  กรอบ {a.box}  สีเดิม {colour}")

    content["text"] = text
    for st in content.get("styles", []):
        st["range"] = [0, len(text)]
        st["size"] = size
    mat["font_size"] = float(size)
    mat["line_max_width"] = a.box
    mat["content"] = json.dumps(content, ensure_ascii=False)
    mat["base_content"] = mat["content"]
    mat["words"] = {"start_time": [0],
                    "end_time": [int(seg["target_timerange"]["duration"] / 1000)],
                    "text": [text]}

    if a.dry_run:
        print("dry run — nothing written")
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR,
                       f"{a.draft}.draft_content.json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, bak)
    json.dump(draft, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  backup {bak}")
    print(f"  wrote  {path}")


if __name__ == "__main__":
    main()
