"""Re-lay the picture: clear stale split-screen framing, then pair split windows properly.

The user rebuilt their cut from an older draft that had been reframed for split-screen, so 13
of the 25 main clips were still cropped to the middle 50% and pushed to the bottom half —
but the B-roll over them is full-frame now, so the top half rendered BLACK.

This resets every main clip to full frame first (stale crop and transform are the bug), then
re-derives the split windows from the B-roll plan and reframes both halves together, so a
bottom-half main clip always has a top-half B-roll above it. The pairing is asserted, not
assumed: any split main piece without B-roll over it is exactly the black-frame defect.

Audio is never touched — only `clip` framing and material `crop`.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import time

import build_draft as B
from enrich_draft import caption_cards, index, reframe_main_for_splits

from config import CAPCUT_ROOT, BACKUP_DIR
US = 1_000_000
FULL_CROP = {"upper_left_x": 0.0, "upper_left_y": 0.0, "upper_right_x": 1.0,
             "upper_right_y": 0.0, "lower_left_x": 0.0, "lower_left_y": 1.0,
             "lower_right_x": 1.0, "lower_right_y": 1.0}


def av_signature(draft) -> list:
    """What the viewer HEARS, independent of how the picture is sliced.

    Reframing splits a clip into pieces, so a plain segment-by-segment comparison always
    differs. Adjacent pieces that continue the same media at the same volume are merged back
    first, which makes the signature invariant to slicing but sensitive to any real change of
    source, timing or volume.
    """
    by = index(draft)
    out = []
    for t in draft["tracks"]:
        if t["type"] not in ("video", "audio"):
            continue
        run = None
        for s in sorted(t["segments"], key=lambda x: x["target_timerange"]["start"]):
            tr, sr = s["target_timerange"], s["source_timerange"] or {"start": 0, "duration": 0}
            key = (by[s["material_id"]][1].get("path", ""), s.get("volume"))
            cur = [key, tr["start"], tr["start"] + tr["duration"],
                   sr["start"], sr["start"] + sr["duration"]]
            if run and run[0] == key and abs(run[2] - cur[1]) <= 1 and abs(run[4] - cur[3]) <= 1:
                run[2], run[4] = cur[2], cur[4]
            else:
                if run:
                    out.append(tuple(run))
                run = cur
        if run:
            out.append(tuple(run))
    return sorted(out)


def reset_full_frame(draft) -> int:
    """Undo any leftover split framing on the main picture track."""
    by = index(draft)
    track = [t for t in draft["tracks"] if t["type"] == "video"][0]
    fixed = 0
    for seg in track["segments"]:
        mat = by[seg["material_id"]][1]
        cl = seg["clip"]
        cropped = mat.get("crop", FULL_CROP)["lower_left_y"] < 0.999 or \
            mat.get("crop", FULL_CROP)["upper_left_y"] > 0.001
        if abs(cl["transform"]["y"]) > 1e-6 or cropped:
            mat["crop"] = dict(FULL_CROP)
            mat["crop_ratio"] = "free"
            mat["crop_scale"] = 1.0
            cl["transform"] = {"x": cl["transform"]["x"], "y": 0.0}
            # a scale under 1 came from the reframe; a deliberate push-in above 1 is theirs
            if cl["scale"]["x"] < 1.0 + 1e-6 and cl["scale"]["y"] < 1.0 + 1e-6:
                cl["scale"] = {"x": 1.0, "y": 1.0}
            fixed += 1
    return fixed


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--broll-plan", default=None)
    p.add_argument("--split-anchors", default=None,
                   help="json list of anchors that should share the frame")
    p.add_argument("--main-bottom", action="store_true",
                   help="the presenter always goes in the BOTTOM half, B-roll on top")
    p.add_argument("--follow-draft", action="store_true",
                   help="take the split windows from how the B-roll is arranged NOW, not "
                        "from the plan — use this once the user has moved things by hand")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    path = os.path.join(CAPCUT_ROOT, a.draft, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))
    audio_before = json.dumps([t for t in draft["tracks"] if t["type"] == "audio"],
                              sort_keys=True)
    sound_before = av_signature(draft)

    n = reset_full_frame(draft)
    print(f"reset {n} main clips back to full frame")

    btrack0 = [t for t in draft["tracks"] if t["type"] == "video"][1]
    if a.follow_draft:
        # The draft is the truth once the user has dragged clips around: a B-roll sitting in
        # a half of the frame IS the instruction to put the main picture in the other half.
        # Re-deriving from the plan would silently undo their edits.
        wins = sorted((s["target_timerange"]["start"] / US,
                       (s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / US)
                      for s in btrack0["segments"]
                      if abs(abs(s["clip"]["transform"]["y"]) - B.SPLIT_TOP) <= 0.12)
        print(f"split windows: {len(wins)} taken from the B-roll as it stands")
    else:
        plan = json.load(open(a.broll_plan, encoding="utf-8"))
        want = set(json.load(open(a.split_anchors, encoding="utf-8")))
        for it in plan:
            it["layout"] = "split" if it.get("anchor") in want else "full"
        tidx = max((len(t["segments"]), i) for i, t in enumerate(draft["tracks"])
                   if t["type"] == "text" and t["segments"])[1]
        plan = B.resolve_anchors(plan, caption_cards(draft, tidx), "B-roll")
        wins = B.split_windows(plan)
        print(f"split windows: {len(wins)} of {len(plan)} inserts")

    reframe_main_for_splits(draft, wins)
    if a.follow_draft:
        opposite = {}
        for s in btrack0["segments"]:
            y = s["clip"]["transform"]["y"]
            if abs(abs(y) - B.SPLIT_TOP) > 0.12:
                continue
            tr = s["target_timerange"]
            opposite[(tr["start"] / US, (tr["start"] + tr["duration"]) / US)] = (
                -B.SPLIT_TOP if a.main_bottom or y > 0 else B.SPLIT_TOP)
        for s in [t for t in draft["tracks"] if t["type"] == "video"][0]["segments"]:
            tr = s["target_timerange"]
            t0 = tr["start"] / US
            t1 = t0 + tr["duration"] / US
            for (lo, hi), y in opposite.items():
                if lo <= t0 + 1e-6 and t1 <= hi + 1e-6:
                    s["clip"]["transform"] = {"x": 0.0, "y": y}
                    break

    # the B-roll track carries the other half of every window
    by = index(draft)
    btrack = [t for t in draft["tracks"] if t["type"] == "video"][1]
    paired = 0
    for seg in btrack["segments"]:
        tr = seg["target_timerange"]
        s, e = tr["start"] / US, (tr["start"] + tr["duration"]) / US
        is_split = any(abs(s - lo) < 0.01 and abs(e - hi) < 0.01 for lo, hi in wins)
        mat = by[seg["material_id"]][1]
        if is_split:
            B.set_crop(mat, B.SPLIT_CROP, 1 - B.SPLIT_CROP)
            half = seg["clip"]["transform"]["y"] if a.follow_draft else B.SPLIT_TOP
            half = B.SPLIT_TOP if half >= 0 else -B.SPLIT_TOP
            if a.main_bottom:
                half = B.SPLIT_TOP          # presenter below, B-roll above, every time
            seg["clip"]["transform"] = {"x": 0.0, "y": half}
            paired += 1
        else:
            mat["crop"] = dict(FULL_CROP)
            seg["clip"]["transform"] = {"x": 0.0, "y": 0.0}
    print(f"B-roll: {paired} to the top half, {len(btrack['segments']) - paired} full frame")

    # invariant: a main clip in the bottom half with nothing above it IS the black frame bug
    mtrack = [t for t in draft["tracks"] if t["type"] == "video"][0]
    bspans = [(s["target_timerange"]["start"] / US,
               (s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / US)
              for s in btrack["segments"]
              if abs(abs(s["clip"]["transform"]["y"]) - B.SPLIT_TOP) < 1e-6]
    for s in mtrack["segments"]:
        if abs(abs(s["clip"]["transform"]["y"]) - B.SPLIT_TOP) > 1e-6:
            continue
        t0 = s["target_timerange"]["start"] / US
        t1 = t0 + s["target_timerange"]["duration"] / US
        covered = any(lo <= t0 + 1e-6 and t1 <= hi + 1e-6 for lo, hi in bspans)
        assert covered, f"bottom-half main clip at {t0:.2f}-{t1:.2f}s has no B-roll above it"
    print(f"main picture: {len(mtrack['segments'])} segments, top/bottom pairing asserted")

    assert json.dumps([t for t in draft["tracks"] if t["type"] == "audio"],
                      sort_keys=True) == audio_before, "audio track was modified"
    assert av_signature(draft) == sound_before, "what plays, or when, changed"
    print("audio: untouched (asserted)")

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
