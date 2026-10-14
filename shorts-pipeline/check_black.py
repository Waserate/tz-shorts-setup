"""Find the parts of the frame that render BLACK, and say when.

The JSON-level check only asked "does a bottom-half clip have something above it". That
misses the other way a frame goes black: a clip whose picture does not FILL the area it was
put in. CapCut fits a clip inside its box without cropping, so a 4:3 source dropped into a
9:16 canvas paints the middle and leaves bars — the Vegan Teacher clip is 768x576.

So this works in geometry, not in hope: every segment is turned into the rectangle it
actually paints, the rectangles are stacked per moment, and whatever is left over is black.
"""
from __future__ import annotations

import argparse
import json
import os

import build_draft as B

from config import CAPCUT_ROOT
US = 1_000_000


def painted_rect(seg, mat, canvas_w, canvas_h, probe):
    """Vertical span (top, bottom) in canvas pixels that this segment actually covers."""
    dur = probe(mat.get("path", ""))
    if dur is None:
        return None
    w, h = dur
    crop = mat.get("crop") or {}
    frac = (crop.get("lower_left_y", 1.0) - crop.get("upper_left_y", 0.0)) or 1.0
    src_w, src_h = w, h * frac

    cl = seg["clip"]
    sx = cl["scale"]["x"]
    # CapCut fits the source inside the canvas, then applies the clip scale
    fit = min(canvas_w / src_w, canvas_h / src_h)
    draw_h = src_h * fit * sx
    draw_w = src_w * fit * sx
    centre = canvas_h / 2 - cl["transform"]["y"] * canvas_h / 2
    return (centre - draw_h / 2, centre + draw_h / 2, draw_w >= canvas_w - 0.5)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--step", type=float, default=0.1)
    a = p.parse_args()

    path = os.path.join(CAPCUT_ROOT, a.draft, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))
    cw, ch = draft["canvas_config"]["width"], draft["canvas_config"]["height"]
    by = {}
    for bucket, items in draft["materials"].items():
        if isinstance(items, list):
            for m in items:
                if isinstance(m, dict) and "id" in m:
                    by[m["id"]] = m

    sizes = {}

    def probe(q):
        if q not in sizes:
            try:
                if q.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    from PIL import Image
                    with Image.open(q) as im:
                        sizes[q] = im.size
                else:
                    import av
                    with av.open(q) as c:
                        st = c.streams.video[0]
                        sizes[q] = (st.codec_context.width, st.codec_context.height)
            except Exception:
                sizes[q] = None
        return sizes[q]

    pics = [t for t in draft["tracks"] if t["type"] == "video"]
    end = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
              for t in draft["tracks"] for s in t["segments"]) / US

    holes, t = [], 0.0
    while t < end:
        rows = [False] * 96          # sample the canvas height in 96 bands
        for tr in pics:
            for seg in tr["segments"]:
                q = seg["target_timerange"]
                s0 = q["start"] / US
                s1 = s0 + q["duration"] / US
                if not (s0 <= t < s1):
                    continue
                r = painted_rect(seg, by[seg["material_id"]], cw, ch, probe)
                if not r or not r[2]:
                    continue         # narrower than the canvas: leaves side bars, not rows
                top, bot, _ = r
                for i in range(96):
                    y = (i + 0.5) * ch / 96
                    if top - 0.5 <= y <= bot + 0.5:
                        rows[i] = True
        dark = sum(1 for r in rows if not r) / 96
        if dark > 0.02:
            holes.append((round(t, 2), round(dark * 100)))
        t += a.step

    if not holes:
        print("ไม่พบจอดำเลยตลอดคลิป")
        return
    runs, start, last, worst = [], holes[0][0], holes[0][0], holes[0][1]
    for tt, d in holes[1:]:
        if tt - last <= a.step * 1.5:
            last, worst = tt, max(worst, d)
        else:
            runs.append((start, last, worst))
            start, last, worst = tt, tt, d
    runs.append((start, last, worst))
    print(f"พบจอดำ {len(runs)} ช่วง:")
    for s0, s1, d in runs:
        print(f"   {s0:6.2f}-{s1:6.2f}s   ดำ {d}% ของเฟรม")


if __name__ == "__main__":
    main()
