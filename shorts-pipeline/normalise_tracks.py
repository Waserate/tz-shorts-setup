"""Put the picture tracks back into a shape the rest of the pipeline can rely on.

CapCut reorganises a project when it opens it: if two segments on one track overlap in time
it moves one onto a NEW track. That produced a second "Video Main" track holding a duplicate
of 13.33-15.17s, and every script that finds the main picture as `video tracks[0]` and the
B-roll as `video tracks[1]` then read the duplicate as the B-roll — one run later the whole
split-screen layout was gone.

So: identify tracks by what is ON them, drop main-picture duplicates that the real main track
already covers, and order them main, B-roll, stills, captions. Indexes are only safe once
this has run, and the invariants below say so out loud rather than hoping.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time

from config import CAPCUT_ROOT, BACKUP_DIR
US = 1_000_000
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")


def media(draft):
    out = {}
    for bucket, items in draft["materials"].items():
        if isinstance(items, list):
            for m in items:
                if isinstance(m, dict) and "id" in m:
                    out[m["id"]] = m
    return out


def spans(track):
    return [(s["target_timerange"]["start"] / US,
             (s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / US)
            for s in track["segments"]]


def covered(inner, outer):
    """Is every span of `inner` inside the union of `outer`?"""
    merged = []
    for lo, hi in sorted(outer):
        if merged and lo <= merged[-1][1] + 1e-6:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return all(any(m[0] <= lo + 1e-6 and hi <= m[1] + 1e-6 for m in merged)
               for lo, hi in inner)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--main-media", default="Video Main.mp4")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    path = os.path.join(CAPCUT_ROOT, a.draft, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))
    by = media(draft)

    def kind(track):
        if track["type"] != "video":
            return track["type"]
        paths = [by[s["material_id"]].get("path", "") for s in track["segments"]]
        if not paths:
            return "empty"
        if sum(os.path.basename(q) == a.main_media for q in paths) > len(paths) / 2:
            return "main"
        if all(q.lower().endswith(IMAGE_EXT) for q in paths):
            return "stills"
        return "broll"

    tagged = [(kind(t), t) for t in draft["tracks"]]
    mains = [t for k, t in tagged if k == "main"]
    if not mains:
        raise SystemExit("no main picture track found")
    mains.sort(key=lambda t: -len(t["segments"]))
    keep, dropped = mains[0], []
    for extra in mains[1:]:
        if covered(spans(extra), spans(keep)):
            dropped.append(extra)
            print(f"ทิ้งแทร็ก Video Main ซ้ำ {len(extra['segments'])} ชิ้น "
                  f"({spans(extra)[0][0]:.2f}-{spans(extra)[-1][1]:.2f}s) — แทร็กหลักคลุมอยู่แล้ว")
        else:
            raise SystemExit("a second Video Main track holds picture the main track does "
                             "not cover — resolve by hand, do not guess")

    order = {"main": 0, "broll": 1, "stills": 2, "empty": 3, "text": 4, "audio": -1}
    rest = [(k, t) for k, t in tagged if t not in dropped]
    rest.sort(key=lambda p: (order.get(p[0], 3), [t for _, t in tagged].index(p[1])))
    draft["tracks"] = [t for _, t in rest]
    for i, t in enumerate(draft["tracks"]):
        for s in t["segments"]:
            s["track_render_index"] = i
    print("ลำดับแทร็ก:", [(k, len(t["segments"])) for k, t in rest])

    # invariants the index-based scripts depend on
    vids = [t for t in draft["tracks"] if t["type"] == "video"]
    assert kind(vids[0]) == "main", "the main picture must be the first video track"
    assert len(vids) < 2 or kind(vids[1]) == "broll", "the B-roll must be the second"
    for t in draft["tracks"]:
        for s in t["segments"]:
            assert s["target_timerange"]["duration"] > 0, \
                f"zero-length segment at {s['target_timerange']['start'] / US:.2f}s"
    prev = -1.0
    for lo, hi in sorted(spans(vids[0])):
        assert lo >= prev - 1e-6, f"main picture overlaps itself at {lo:.2f}s"
        prev = hi
    outside = [t for t in draft["tracks"][1:] if kind(t) == "main"]
    assert not outside, "Video Main still appears outside the main track"
    assert draft["tracks"][-1]["type"] == "text", "captions must stay on top"
    print("ตรวจแล้ว: แทร็กหลักไม่ซ้อนตัวเอง, ไม่มี Video Main หลงไปแทร็กอื่น, ซับอยู่บนสุด")

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
