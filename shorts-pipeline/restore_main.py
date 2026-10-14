"""Put the main picture track back exactly as the user cut it, from a reference draft.

Somewhere in the processing 1.8s of the main clip (source 28.57-30.37s) was dropped. The
timeline did not get a hole — everything after 13.37s simply slid 1.8s earlier, so the whole
second half of the video played 1.8s ahead of its own captions, and the tail ended at 80.33s
instead of 82.33s. Patching that by hand would be guesswork on top of guesswork.

So the picture is taken wholesale from a reference copy of the draft: its segments, its
source mapping and its effect materials. Framing (split halves, face crops) is deliberately
NOT carried over — it is re-derived afterwards, from a picture that is correct again.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import time

from config import CAPCUT_ROOT, BACKUP_DIR
US = 1_000_000


def index(draft):
    out = {}
    for bucket, items in draft["materials"].items():
        if isinstance(items, list):
            for m in items:
                if isinstance(m, dict) and "id" in m:
                    out[m["id"]] = (bucket, m)
    return out


def main_track(draft, name):
    by = index(draft)
    for t in draft["tracks"]:
        if t["type"] != "video" or not t["segments"]:
            continue
        paths = [by[s["material_id"]][1].get("path", "") for s in t["segments"]]
        if sum(os.path.basename(q) == name for q in paths) > len(paths) / 2:
            return t
    raise SystemExit("no main picture track")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--reference", required=True, help="a draft_content.json to copy from")
    p.add_argument("--main-media", default="Video Main.mp4")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    path = os.path.join(CAPCUT_ROOT, a.draft, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))
    ref = json.load(open(a.reference, encoding="utf-8"))

    cur, good = main_track(draft, a.main_media), main_track(ref, a.main_media)
    span = lambda t: (min(s["target_timerange"]["start"] for s in t["segments"]) / US,
                      max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
                          for s in t["segments"]) / US)
    print(f"ของเดิมในดราฟ {len(cur['segments'])} ชิ้น {span(cur)[0]:.2f}-{span(cur)[1]:.2f}s")
    print(f"จากคัตต้นฉบับ {len(good['segments'])} ชิ้น {span(good)[0]:.2f}-{span(good)[1]:.2f}s")

    ref_by = index(ref)
    have = set(index(draft))
    added = 0
    segs = []
    for s in good["segments"]:
        s2 = copy.deepcopy(s)
        for mid in [s2["material_id"]] + list(s2.get("extra_material_refs") or []):
            if mid in have or mid not in ref_by:
                continue
            bucket, m = ref_by[mid]
            draft["materials"].setdefault(bucket, []).append(copy.deepcopy(m))
            have.add(mid)
            added += 1
        segs.append(s2)
    cur["segments"] = segs
    print(f"คัดลอกวัสดุมาเพิ่ม {added} รายการ")

    src_total = sum(s["source_timerange"]["duration"] for s in segs) / US
    tl_total = sum(s["target_timerange"]["duration"] for s in segs) / US
    print(f"เสียงรวม {src_total:.2f}s บนไทม์ไลน์ {tl_total:.2f}s")
    assert abs(src_total - tl_total) < 0.05, "picture and timeline lengths disagree"

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
