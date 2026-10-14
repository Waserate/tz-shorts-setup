"""Apply the face preset to every picture segment, then cut the draft down.

Made for a draft that is one long take plus a caption track (CapCut Auto Caption). It:

  1. copies the face-retouch preset onto every video material and segment, taking both the
     `beauty_face_preset_infos` id AND the figure/makeup effects from a donor draft — the
     preset id alone does nothing without the effects it switches on;
  2. builds the cut from the CAPTIONS, not from a fresh transcription, so the words the
     user already corrected are what decides what is a repeat;
  3. splits the single video segment along the keep list and remaps every caption onto the
     new timeline, dropping the ones whose audio is gone.

Captions keep their own material, so the per-run font sizes set by `match_script_heights`
survive: only their time is rewritten, never their text or styling.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cut_plan import plan
from speech_mask import SpeechMask

from config import CAPCUT_ROOT, BACKUP_DIR
US = 1_000_000
MIN_CARD_AFTER_CUT = 0.30


def uid():
    return str(uuid.uuid4()).upper()


def load(name_or_path):
    if os.path.sep in name_or_path or name_or_path.endswith(".json"):
        return json.load(open(name_or_path, encoding="utf-8"))
    return json.load(open(os.path.join(CAPCUT_ROOT, name_or_path, "draft_content.json"),
                          encoding="utf-8"))


def index(draft):
    by = {}
    for bucket, items in draft["materials"].items():
        if isinstance(items, list):
            for m in items:
                if isinstance(m, dict) and "id" in m:
                    by[m["id"]] = (bucket, m)
    return by


def face_preset_from(donor):
    """(preset_infos, [figure/makeup effect materials]) as the donor has them."""
    by = index(donor)
    vseg = [t for t in donor["tracks"] if t["type"] == "video"][0]["segments"][0]
    mat = by[vseg["material_id"]][1]
    infos = mat.get("beauty_face_preset_infos") or []
    effects = [copy.deepcopy(by[r][1]) for r in vseg["extra_material_refs"]
               if r in by and by[r][1].get("type") in ("figure", "makeup_root")]
    return copy.deepcopy(infos), effects


def apply_face_preset(draft, infos, effects):
    """Put the preset on every video material + segment that does not already carry it."""
    by = index(draft)
    n = 0
    for tr in draft["tracks"]:
        if tr["type"] != "video":
            continue
        for seg in tr["segments"]:
            mat = by[seg["material_id"]][1]
            mat["beauty_face_preset_infos"] = copy.deepcopy(infos)
            have = {by[r][1].get("resource_id") for r in seg["extra_material_refs"]
                    if r in by and by[r][1].get("type") in ("figure", "makeup_root")}
            for eff in effects:
                if eff.get("resource_id") in have:
                    continue
                e2 = copy.deepcopy(eff)
                e2["id"] = uid()
                draft["materials"].setdefault("effects", []).append(e2)
                seg["extra_material_refs"].append(e2["id"])
            n += 1
    return n


def cards_from_captions(draft, idx):
    by = index(draft)
    segs = sorted(draft["tracks"][idx]["segments"],
                  key=lambda s: s["target_timerange"]["start"])
    out = []
    for i, s in enumerate(segs):
        t = s["target_timerange"]
        out.append({"start": t["start"] / US, "end": (t["start"] + t["duration"]) / US,
                    "text": json.loads(by[s["material_id"]][1]["content"])["text"],
                    "_i": i})
    return segs, out


def remap(a, b, keeps):
    """source [a,b] -> timeline span, or None if all of it was cut."""
    lo = hi = None
    acc = 0.0
    for s, e in keeps:
        x, y = max(a, s), min(b, e)
        if y > x:
            p, q = acc + (x - s), acc + (y - s)
            lo = p if lo is None else lo
            hi = q
        acc += e - s
    return None if lo is None or hi - lo < MIN_CARD_AFTER_CUT else (lo, hi)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--media", required=True, help="the video file, for the speech mask")
    p.add_argument("--preset-donor", default="0813")
    p.add_argument("--min-silence", type=float, default=0.35)
    p.add_argument("--no-preset", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    path = os.path.join(CAPCUT_ROOT, a.draft, "draft_content.json")
    draft = load(a.draft)

    if not a.no_preset:
        infos, effects = face_preset_from(load(a.preset_donor))
        if not infos:
            raise SystemExit(f"{a.preset_donor} has no face preset to copy")
        n = apply_face_preset(draft, infos, effects)
        print(f"face preset {infos[0]['preset_id']} -> {n} video segment(s), "
              f"{len(effects)} retouch effects each")

    tidx = max((len(t["segments"]), i) for i, t in enumerate(draft["tracks"])
               if t["type"] == "text" and t["segments"])[1]
    cap_segs, cards = cards_from_captions(draft, tidx)

    mask = SpeechMask(a.media)
    keeps, report = plan(mask, cards, min_silence=a.min_silence)
    for line in report.lines():
        print("  " + line)

    # ---- video: one segment per keep
    vtrack = [t for t in draft["tracks"] if t["type"] == "video"][0]
    proto = copy.deepcopy(vtrack["segments"][0])
    by = index(draft)
    proto_mat = by[proto["material_id"]][1]
    new_v, t = [], 0.0
    for s, e in keeps:
        dur = int(round((e - s) * US))
        seg = copy.deepcopy(proto)
        seg["id"] = uid()
        m2 = copy.deepcopy(proto_mat)
        m2["id"] = uid()
        draft["materials"]["videos"].append(m2)
        seg["material_id"] = m2["id"]
        refs = []
        for r in proto["extra_material_refs"]:
            if r in by:
                bucket, em = by[r]
                e2 = copy.deepcopy(em)
                e2["id"] = uid()
                draft["materials"].setdefault(bucket, []).append(e2)
                refs.append(e2["id"])
        seg["extra_material_refs"] = refs
        seg["source_timerange"] = {"start": int(round(s * US)), "duration": dur}
        seg["target_timerange"] = {"start": int(round(t * US)), "duration": dur}
        seg["common_keyframes"] = []
        seg["keyframe_refs"] = []
        seg["group_id"] = ""
        new_v.append(seg)
        t += e - s
    span = int(round(t * US))
    old_v = {s["material_id"] for s in vtrack["segments"]}
    draft["materials"]["videos"] = [m for m in draft["materials"]["videos"]
                                    if m["id"] not in old_v]
    vtrack["segments"] = new_v

    # ---- captions: keep the material, move the time, drop what was cut
    kept, dropped = [], 0
    for seg, card in zip(cap_segs, cards):
        r = remap(card["start"], card["end"], keeps)
        if r is None:
            dropped += 1
            continue
        s2 = copy.deepcopy(seg)
        s2["target_timerange"] = {"start": int(round(r[0] * US)),
                                  "duration": int(round((r[1] - r[0]) * US))}
        kept.append(s2)
    kept.sort(key=lambda s: s["target_timerange"]["start"])
    for i, s in enumerate(kept):
        s["render_index"] = 14000 + i
    live = {s["material_id"] for s in kept}
    draft["materials"]["texts"] = [m for m in draft["materials"]["texts"]
                                   if m["id"] in live]
    draft["tracks"][tidx]["segments"] = kept
    draft["duration"] = span

    # ---- invariants
    prev = -1
    for s in kept:
        tr = s["target_timerange"]
        assert tr["duration"] > 0, "zero-length caption"
        assert tr["start"] >= prev, "overlapping captions"
        prev = tr["start"] + tr["duration"]
    prev = -1
    for s in new_v:
        tr = s["target_timerange"]
        assert tr["start"] >= prev, "overlapping video segments"
        prev = tr["start"] + tr["duration"]
    assert prev == span, "video does not cover the timeline"

    print(f"  video 1 -> {len(new_v)} segments | timeline {span/US:.2f}s")
    print(f"  captions {len(cap_segs)} -> {len(kept)} ({dropped} dropped with their audio)")

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
