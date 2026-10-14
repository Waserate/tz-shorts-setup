"""Shrink the Latin runs inside a caption so they stand the same height as the Thai.

Thai and Latin at the same nominal font size are not the same size on screen. Measured in
the fonts CapCut actually uses here, at one nominal size:

    Thai base letter (ก น ม)   112 px
    Latin capital   (C S T)    143 px

so an English word set at the caption's size renders about 28 % taller than the Thai around
it and reads as a different, louder typeface. 'กลาง Clip' is the example the user caught.

CapCut already stores one style per script run — 'กิน Steak' comes back as ranges [0,4] and
[4,9] — so the fix is to keep the ranges and give the Latin ones a smaller size. Nothing
about the layout or the timing changes, and since the Latin gets narrower the no-wrap
guarantee from `fit_caption_sizes` still holds.

`--scale` is the ratio; 0.78 matches Thai base height to Latin cap height. Tune it by eye.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import time

from config import CAPCUT_ROOT, BACKUP_DIR, FONT_DIR


def measure_ratio(thai_font="NotoSansThai-Regular.ttf", latin_font="en.ttf", size=200):
    """Thai base-letter height / Latin cap height, in the real fonts."""
    from PIL import ImageFont
    th = ImageFont.truetype(os.path.join(FONT_DIR, thai_font), size)
    en = ImageFont.truetype(os.path.join(FONT_DIR, latin_font), size)

    def h(f, ch):
        b = f.getbbox(ch)
        return b[3] - b[1]

    thai = max(h(th, c) for c in "กนม")          # flat-topped, no ascender
    cap = max(h(en, c) for c in "CST")
    return thai / cap, thai, cap


def is_latin(ch: str) -> bool:
    return ch.isascii() and (ch.isalnum() or ch in "%&/+-.,'\"()")


def runs(text: str):
    """(start, end, is_latin) spans. A space joins the run on its left, which is how
    CapCut itself splits them."""
    out = []
    i = 0
    while i < len(text):
        lat = is_latin(text[i])
        j = i + 1
        while j < len(text):
            c = text[j]
            if c == " ":
                k = j + 1
                while k < len(text) and text[k] == " ":
                    k += 1
                if k < len(text) and is_latin(text[k]) == lat:
                    j = k + 1
                    continue
                break
            if is_latin(c) != lat:
                break
            j += 1
        out.append((i, j, lat))
        i = j
    return out


def restyle(draft, idx, scale):
    by = {m["id"]: m for m in draft["materials"]["texts"]}
    segs = sorted(draft["tracks"][idx]["segments"],
                  key=lambda s: s["target_timerange"]["start"])
    touched, sizes = 0, collections.Counter()
    for s in segs:
        m = by[s["material_id"]]
        content = json.loads(m["content"])
        text = content["text"]
        base_style = content["styles"][0]
        base_size = m["font_size"]
        spans = runs(text)
        if not any(lat for _, _, lat in spans):
            content["styles"] = [{**base_style, "range": [0, len(text)],
                                  "size": base_size}]
        else:
            styles = []
            for a, b, lat in spans:
                size = round(base_size * scale, 3) if lat else base_size
                styles.append({**base_style, "range": [a, b], "size": size})
                sizes[size] += 1
            content["styles"] = styles
            touched += 1
        m["content"] = json.dumps(content, ensure_ascii=False)
        m["base_content"] = m["content"]
    return touched, sizes


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--scale", type=float, default=None,
                   help="Latin size / Thai size (default: measured from the fonts)")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    ratio, thai_h, cap_h = measure_ratio()
    scale = a.scale if a.scale is not None else round(ratio, 3)
    print(f"measured: thai base {thai_h}px vs latin cap {cap_h}px at the same size "
          f"-> ratio {ratio:.3f}")
    print(f"using scale {scale}")

    folder = os.path.join(CAPCUT_ROOT, a.draft)
    path = os.path.join(folder, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))
    cands = [(len(t["segments"]), i) for i, t in enumerate(draft["tracks"])
             if t["type"] == "text" and t["segments"]]
    if not cands:
        raise SystemExit("no text track")
    idx = max(cands)[1]

    touched, sizes = restyle(draft, idx, scale)
    print(f"  {touched} captions contain Latin and were restyled")
    print(f"  sizes now in use: {dict(sorted(sizes.items()))}")

    by = {m["id"]: m for m in draft["materials"]["texts"]}
    for s in sorted(draft["tracks"][idx]["segments"],
                    key=lambda x: x["target_timerange"]["start"]):
        c = json.loads(by[s["material_id"]]["content"])
        if len(c["styles"]) > 1:
            print(f"   e.g. {c['text']!r} -> "
                  + ", ".join(f"{st['range']}@{st['size']}" for st in c["styles"]))
            break

    if a.dry_run:
        print("dry run — nothing written")
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR,
                       f"{a.draft}.draft_content.json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, bak)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False)
    print(f"  backup {bak}")
    print(f"  wrote  {path}")


if __name__ == "__main__":
    main()
