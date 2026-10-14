"""Cut overlays and captions back to where the picture actually ends.

The user shortened their own cut inside CapCut, which moved the end of the main picture from
82.13s to 80.33s — but the captions and the B-roll still ran to 82.17s, so the last 1.8s had
nothing behind them and rendered black.

The picture cannot be extended to meet them: the main clip carries the narration, and the
instruction is that the sound is not to be touched. So the overlays come back to the picture
instead. Nothing on the main track is altered.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time

from config import CAPCUT_ROOT, BACKUP_DIR
US = 1_000_000


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--main-media", default="Video Main.mp4")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    path = os.path.join(CAPCUT_ROOT, a.draft, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))
    by = {}
    for bucket, items in draft["materials"].items():
        if isinstance(items, list):
            for m in items:
                if isinstance(m, dict) and "id" in m:
                    by[m["id"]] = m

    picture = [t for t in draft["tracks"] if t["type"] == "video"][0]
    end_us = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
                 for s in picture["segments"])
    assert all(os.path.basename(by[s["material_id"]].get("path", "")) == a.main_media
               for s in picture["segments"]), "first video track is not the main picture"
    total = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
                for t in draft["tracks"] for s in t["segments"])
    print(f"ภาพหลักจบ {end_us / US:.2f}s, ไทม์ไลน์ยาว {total / US:.2f}s "
          f"-> ต้องตัดส่วนเกิน {(total - end_us) / US:.2f}s")

    cut, shortened = 0, 0
    for tr in draft["tracks"]:
        if tr is picture:
            continue
        keep = []
        for seg in tr["segments"]:
            q = seg["target_timerange"]
            if q["start"] >= end_us:
                cut += 1
                continue
            over = q["start"] + q["duration"] - end_us
            if over > 0:
                q["duration"] -= over
                if seg.get("source_timerange"):
                    seg["source_timerange"]["duration"] -= over
                shortened += 1
            keep.append(seg)
        tr["segments"] = keep

    print(f"ตัดทิ้ง {cut} ชิ้น, หดให้สั้นลง {shortened} ชิ้น")
    now = max(s["target_timerange"]["start"] + s["target_timerange"]["duration"]
              for t in draft["tracks"] for s in t["segments"])
    assert now <= end_us, "something still runs past the picture"
    assert all(s["target_timerange"]["duration"] > 0
               for t in draft["tracks"] for s in t["segments"]), "a segment lost all its time"
    print(f"ไทม์ไลน์ใหม่ {now / US:.2f}s")

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
