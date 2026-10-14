"""Scale up any clip that does not fill the space it was given, so no black bars remain.

CapCut fits a clip inside its box without cropping. A 9:16 source in a 9:16 canvas fills it
exactly, which is why this never mattered before — but the Vegan Teacher clip is 768x576, and
fitting that into a portrait frame paints a band across the middle and leaves the rest black.

Filling means cropping the sides instead, which is the right trade for a B-roll insert: the
subject is in the middle of a 4:3 frame, the edges are not.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time

from config import CAPCUT_ROOT, BACKUP_DIR
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")


def source_size(path: str):
    if path.lower().endswith(IMAGE_EXT):
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    import av
    with av.open(path) as c:
        st = c.streams.video[0]
        return st.codec_context.width, st.codec_context.height


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--skip-track", type=int, default=None,
                   help="a track to leave alone (the stills sit small on purpose)")
    p.add_argument("--dry-run", action="store_true")
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

    sizes, raised = {}, 0
    for ti, tr in enumerate(draft["tracks"]):
        if tr["type"] != "video" or ti == a.skip_track:
            continue
        for seg in tr["segments"]:
            mat = by[seg["material_id"]]
            q = mat.get("path", "")
            if q not in sizes:
                try:
                    sizes[q] = source_size(q)
                except Exception:
                    sizes[q] = None
            if not sizes[q]:
                continue
            w, h = sizes[q]
            crop = mat.get("crop") or {}
            frac = (crop.get("lower_left_y", 1.0) - crop.get("upper_left_y", 0.0)) or 1.0
            src_w, src_h = w, h * frac

            # the box this clip has to fill: the whole canvas, or one half of it
            half = abs(seg["clip"]["transform"]["y"]) > 0.02
            box_w, box_h = cw, ch / 2 if half else ch
            fit = min(cw / src_w, ch / src_h)          # CapCut fits against the CANVAS
            need = max(box_w / (src_w * fit), box_h / (src_h * fit))
            have = seg["clip"]["scale"]["x"]
            if need > have + 1e-3:
                seg["clip"]["scale"] = {"x": round(need, 4), "y": round(need, 4)}
                raised += 1
                print(f"  {os.path.basename(q)[:34]:36s} {src_w:.0f}x{src_h:.0f} "
                      f"-> scale {have:.3f} เป็น {need:.3f}")

    print(f"ขยายให้เต็มกรอบ {raised} ชิ้น")
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
