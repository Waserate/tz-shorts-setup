"""Aim every split-screen crop at the face instead of the middle of the frame.

A split shot shows 50% of the source height. That window was hard-coded to the MIDDLE of the
frame, which is where the face happens to be in some shots and where the chest is in others —
the user's own head was cut off in the bottom half while the influencer's was fine in the top.

So the window is placed by measurement: sample frames across each split segment, find the
face, and centre the 50% window on it. Shots where no face is found keep the middle window,
which is the old behaviour, so a detection failure can never make the framing worse.

Only the material `crop` moves. The window keeps its height, so the composition, the timings
and the sound are all untouched.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import time

import build_draft as B

from config import CAPCUT_ROOT, BACKUP_DIR
US = 1_000_000
WINDOW = 0.5             # a split half shows this fraction of the source height
SAMPLES = 5


def face_centre(path: str, t0: float, t1: float, samples: int = SAMPLES):
    """Median vertical centre of the face over the segment, as a fraction of frame height."""
    import cv2
    cascade = cv2.CascadeClassifier(
        os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None, 0
    found = []
    for i in range(samples):
        t = t0 + (t1 - t0) * (i + 0.5) / samples
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        scale = 480 / max(w, 1)
        small = cv2.resize(frame, (int(w * scale), int(h * scale)))
        grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(grey, 1.1, 5, minSize=(30, 30))
        if len(faces):
            # the biggest face is the speaker; a bystander in the background is not
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            found.append((y + fh / 2) / small.shape[0])
    cap.release()
    return (statistics.median(found) if found else None), len(found)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--headroom", type=float, default=0.42,
                   help="where the face should sit inside the window, 0=top 0.5=centre")
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

    todo = []
    for tr in draft["tracks"]:
        if tr["type"] != "video":
            continue
        for seg in tr["segments"]:
            if abs(abs(seg["clip"]["transform"]["y"]) - B.SPLIT_TOP) > 0.02:
                continue           # not a split half, so nothing is cropped away
            todo.append(seg)
    print(f"{len(todo)} split halves to aim")

    moved, blind = 0, 0
    for seg in todo:
        mat = by[seg["material_id"]]
        src = seg["source_timerange"]
        t0, t1 = src["start"] / US, (src["start"] + src["duration"]) / US
        cy, hits = face_centre(mat.get("path", ""), t0, t1)
        name = os.path.basename(mat.get("path", ""))[:34]
        if cy is None:
            blind += 1
            print(f"  {name:36s} {t0:6.1f}s  ไม่พบใบหน้า — คงกรอบกลางไว้")
            continue
        top = min(max(cy - a.headroom * WINDOW, 0.0), 1.0 - WINDOW)
        old = mat.get("crop", {}).get("upper_left_y", 0.25)
        B.set_crop(mat, top, top + WINDOW)
        moved += 1
        print(f"  {name:36s} {t0:6.1f}s  หน้าอยู่ที่ {cy:.2f} -> กรอบ {top:.2f}"
              f"-{top + WINDOW:.2f} (เดิม {old:.2f})  [{hits}/{SAMPLES} เฟรม]")

    print(f"เล็งใหม่ {moved} ชิ้น, หาใบหน้าไม่เจอ {blind} ชิ้น")
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
