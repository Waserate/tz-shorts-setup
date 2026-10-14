"""Put a centred title card over the opening shot.

The opening is a B-roll overlay of the influencer herself, so the viewer sees the subject
before the first word. This lays the title on top of it, on its own text track, so it can be
restyled or dragged without disturbing the captions.

Size is derived, not guessed: the title is split into lines on "\\n" and the size is the
largest that keeps the WIDEST line inside `--box`, using the same measured px-per-unit the
caption fitter uses. Nothing else in the draft is touched.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import time

import build_draft as B
from style_captions import room_units, width_per_px

from config import CAPCUT_ROOT, BACKUP_DIR
US = 1_000_000


def fitting_size(text: str, canvas_w: int, box: float, cap: float) -> float:
    room = room_units(canvas_w, box)
    widest = max(width_per_px(line) for line in text.split("\n"))
    return round(min(cap, room / widest), 3)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--text", required=True, help="use \\n to break the line yourself")
    p.add_argument("--at", type=float, default=0.0)
    p.add_argument("--until", type=float, required=True)
    p.add_argument("--box", type=float, default=0.86)
    p.add_argument("--max-size", type=float, default=30.0)
    p.add_argument("--y", type=float, default=0.0, help="0 = centre of frame")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    text = a.text.replace("\\n", "\n")
    path = os.path.join(CAPCUT_ROOT, a.draft, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))

    tidx = max((len(t["segments"]), i) for i, t in enumerate(draft["tracks"])
               if t["type"] == "text" and t["segments"])[1]
    caps = sorted(draft["tracks"][tidx]["segments"],
                  key=lambda s: s["target_timerange"]["start"])
    by = {m["id"]: m for m in draft["materials"]["texts"]}
    proto, pmat = caps[0], by[caps[0]["material_id"]]

    size = fitting_size(text, draft["canvas_config"]["width"], a.box, a.max_size)
    dur = int(round((a.until - a.at) * US))

    mat = copy.deepcopy(pmat)
    mat["id"] = B.uid()
    B.set_card_text(mat, text, dur, font=mat.get("font_path", ""), size=size)
    mat["line_max_width"] = a.box

    seg = copy.deepcopy(proto)
    seg["id"] = B.uid()
    seg["material_id"] = mat["id"]
    seg["extra_material_refs"] = []       # no animation carried over from a caption
    seg["common_keyframes"] = []
    seg["keyframe_refs"] = []
    seg["group_id"] = ""
    seg["target_timerange"] = {"start": int(round(a.at * US)), "duration": dur}
    seg["source_timerange"] = None
    seg["clip"] = {"alpha": 1.0, "rotation": 0.0,
                   "flip": {"horizontal": False, "vertical": False},
                   "scale": {"x": 1.0, "y": 1.0},
                   "transform": {"x": 0.0, "y": a.y}}

    print(f"title {text!r}")
    print(f"  {a.at:.2f}-{a.until:.2f}s  size {size}  box {a.box}  y {a.y}")
    if a.dry_run:
        print("dry run — nothing written")
        return

    draft["materials"]["texts"].append(mat)
    draft["tracks"].append({"type": "text", "attribute": 0, "flag": 0, "id": B.uid(),
                            "name": "", "segments": [seg], "is_default_name": True})

    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR,
                       f"{a.draft}.draft_content.json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, bak)
    json.dump(draft, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  backup {bak}")
    print(f"  wrote  {path}")


if __name__ == "__main__":
    main()
