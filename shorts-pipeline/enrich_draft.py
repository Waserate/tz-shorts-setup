"""Add the look and the overlays to a draft that already has its captions and its cut.

`build_draft.py` can do all of this, but only while building a draft from scratch out of
our own ASR. The agreed flow now starts from CapCut's Auto Caption, so the draft already
exists — this applies the same features to it in place:

  * the colour grade preset + `hsl` from the donor, on every picture segment
  * Enhance voice at the donor's intensity, on every picture segment
  * B-roll inserts, `full` (takes the frame) or `split` (B-roll top, main bottom)
  * comment-card stills on their own track
  * a slow push in/out on a share of the full-frame main clips

Everything that positions itself in time does so by **caption anchor**, never by absolute
seconds, so a later re-cut cannot silently move the inserts.

Helpers are imported from `build_draft` rather than copied: the crop geometry, the zoom
keyframe shape and the anchor resolver all have to stay identical between the two paths or
the two lineages drift apart.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_draft as B

CAPCUT_ROOT = B.CAPCUT_ROOT
BACKUP_DIR = B.BACKUP_DIR
US = B.US


def index(draft):
    by = {}
    for bucket, items in draft["materials"].items():
        if isinstance(items, list):
            for m in items:
                if isinstance(m, dict) and "id" in m:
                    by[m["id"]] = (bucket, m)
    return by


def donor_look(donor):
    """The colour grade + hsl + Enhance-voice materials, as the donor carries them."""
    by = index(donor)
    seg = [t for t in donor["tracks"] if t["type"] == "video"][0]["segments"][0]
    grade, hsl, beautify = [], [], None
    for r in seg["extra_material_refs"]:
        if r not in by:
            continue
        bucket, m = by[r]
        if bucket == "effects" and m.get("type") in (
                "brightness", "contrast", "saturation", "highlight", "shadow",
                "black", "clear", "temperature", "tone"):
            grade.append(copy.deepcopy(m))
        elif bucket == "hsl":
            hsl.append(copy.deepcopy(m))
        elif bucket == "vocal_beautifys":
            beautify = copy.deepcopy(m)
    return grade, hsl, beautify


def apply_look(draft, grade, hsl, beautify, enhance_level=None):
    by = index(draft)
    n = 0
    for tr in draft["tracks"]:
        if tr["type"] != "video":
            continue
        for seg in tr["segments"]:
            have_types = {by[r][1].get("type") for r in seg["extra_material_refs"]
                          if r in by}
            add = []
            for m in grade:
                if m.get("type") in have_types:
                    continue
                add.append(("effects", m))
            if "hsl" not in {by[r][0] for r in seg["extra_material_refs"] if r in by}:
                add += [("hsl", m) for m in hsl]
            # A draft may already carry Enhance voice at some other intensity — CapCut's
            # own default here was 75. "Already present" must mean "correct the level",
            # not "skip", or the requested intensity is silently ignored.
            existing = [by[r][1] for r in seg["extra_material_refs"]
                        if r in by and by[r][0] == "vocal_beautifys"]
            for m in existing:
                m["enable"] = True
                if enhance_level is not None:
                    m["ambient_sound_level"] = int(enhance_level)
                    m["production_path"] = ""      # level changed, cached render is stale
            if beautify is not None and not existing:
                b2 = copy.deepcopy(beautify)
                b2["enable"] = True
                if enhance_level is not None:
                    b2["ambient_sound_level"] = int(enhance_level)
                # the donor's cached render is for a different clip length; let CapCut redo it
                b2["production_path"] = ""
                b2["time_range"] = {"start": 0,
                                    "duration": seg["source_timerange"]["duration"]}
                add.append(("vocal_beautifys", b2))
            for bucket, m in add:
                m2 = copy.deepcopy(m)
                m2["id"] = B.uid()
                draft["materials"].setdefault(bucket, []).append(m2)
                seg["extra_material_refs"].append(m2["id"])
            for k in ("enable_adjust", "enable_lut", "enable_hsl", "enable_color_curves"):
                if k in seg:
                    seg[k] = True
            n += 1
    return n


def caption_cards(draft, idx):
    by = index(draft)
    segs = sorted(draft["tracks"][idx]["segments"],
                  key=lambda s: s["target_timerange"]["start"])
    out = []
    for s in segs:
        t = s["target_timerange"]
        out.append({"start": t["start"] / US,
                    "end": (t["start"] + t["duration"]) / US,
                    "text": json.loads(by[s["material_id"]][1]["content"])["text"]})
    return out


def snap_ends(pieces, seg):
    """Make the pieces of one clip start and end exactly where the clip did.

    The slice points come back as floats, so rounding can move the first start or the last
    end by a microsecond. On its own that is inaudible, but it means a re-slice of the same
    cut no longer compares equal to the original — the drift accumulates every pass.
    """
    if not pieces:
        return
    for key in ("source_timerange", "target_timerange"):
        first, last = pieces[0][key], pieces[-1][key]
        end = seg[key]["start"] + seg[key]["duration"]
        last["duration"] += end - (last["start"] + last["duration"])
        first["duration"] += first["start"] - seg[key]["start"]
        first["start"] = seg[key]["start"]


def reframe_main_for_splits(draft, wins):
    """Cut the main clips at every split boundary and drop the ones inside to the bottom."""
    by = index(draft)
    track = [t for t in draft["tracks"] if t["type"] == "video"][0]
    new = []
    for seg in sorted(track["segments"], key=lambda s: s["target_timerange"]["start"]):
        # Work in whole microseconds from the start. Every earlier version cut in floats and
        # rounded each piece on its own, so consecutive pieces landed 1-2 us apart and the
        # clip no longer added up to what it replaced. Cutting a list of integer offsets and
        # taking consecutive pairs makes the pieces exactly contiguous by construction —
        # there is nothing left to snap or to tolerate.
        t0 = seg["target_timerange"]["start"]
        span = seg["target_timerange"]["duration"]
        src0 = seg["source_timerange"]["start"]
        src_span = seg["source_timerange"]["duration"]
        marks = {0, span}
        for lo, hi in wins:
            for m in (int(round(lo * US)) - t0, int(round(hi * US)) - t0):
                if 0 < m < span:
                    marks.add(m)
        cuts = sorted(marks)
        pieces = []
        for off, nxt in zip(cuts, cuts[1:]):
            mid = t0 + (off + nxt) / 2
            is_split = any(lo * US <= mid < hi * US for lo, hi in wins)
            piece = copy.deepcopy(seg)
            piece["id"] = B.uid()
            mat = copy.deepcopy(by[seg["material_id"]][1])
            mat["id"] = B.uid()
            if is_split:
                B.set_crop(mat, B.SPLIT_CROP, 1 - B.SPLIT_CROP)
            draft["materials"]["videos"].append(mat)
            piece["material_id"] = mat["id"]
            refs = []
            for r in seg["extra_material_refs"]:
                if r in by:
                    bucket, em = by[r]
                    e2 = copy.deepcopy(em)
                    e2["id"] = B.uid()
                    draft["materials"].setdefault(bucket, []).append(e2)
                    refs.append(e2["id"])
            piece["extra_material_refs"] = refs
            # CapCut does not store source and timeline durations as the same number even
            # at speed 1, so the offset is mapped through the clip's own ratio instead of
            # copied. off=0 and off=span then land exactly on the clip's own ends.
            a_us = src0 + round(off * src_span / span)
            b_us = src0 + round(nxt * src_span / span)
            piece["source_timerange"] = {"start": a_us, "duration": b_us - a_us}
            piece["target_timerange"] = {"start": t0 + off, "duration": nxt - off}
            piece["common_keyframes"] = []
            piece["clip"] = copy.deepcopy(seg["clip"])
            if is_split:
                piece["clip"]["transform"] = {"x": 0.0, "y": -B.SPLIT_TOP}
            pieces.append(piece)
        new.extend(pieces)
    old = {s["material_id"] for s in track["segments"]}
    draft["materials"]["videos"] = [m for m in draft["materials"]["videos"]
                                    if m["id"] not in old]
    track["segments"] = new
    return new


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--look-donor", default="0813")
    p.add_argument("--text-donor", default="Vegan V6")
    p.add_argument("--enhance", type=int, default=25)
    p.add_argument("--skip-look", action="store_true",
                   help="leave the picture alone (grade/retouch/Enhance already applied)")
    p.add_argument("--broll", default=None)
    p.add_argument("--broll-plan", default=None)
    p.add_argument("--comments", default=None)
    p.add_argument("--zoom-share", type=float, default=0.6)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    path = os.path.join(CAPCUT_ROOT, a.draft, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))
    donor = json.load(open(os.path.join(CAPCUT_ROOT, a.look_donor,
                                        "draft_content.json"), encoding="utf-8"))
    text_donor = B.Donor(os.path.join(CAPCUT_ROOT, a.text_donor, "draft_content.json"))

    if a.skip_look:
        print("look: skipped — the draft already carries grade + retouch + Enhance")
    else:
        grade, hsl, beautify = donor_look(donor)
        n = apply_look(draft, grade, hsl, beautify, a.enhance)
        print(f"look: {len(grade)} grade + {len(hsl)} hsl + enhance {a.enhance} -> {n} segments")

    tidx = max((len(t["segments"]), i) for i, t in enumerate(draft["tracks"])
               if t["type"] == "text" and t["segments"])[1]
    cards = caption_cards(draft, tidx)

    broll_plan = json.load(open(a.broll_plan, encoding="utf-8")) if a.broll_plan else []
    comments = json.load(open(a.comments, encoding="utf-8")) if a.comments else []
    if broll_plan:
        broll_plan = B.resolve_anchors(broll_plan, cards, "B-roll")
    if comments:
        comments = B.resolve_anchors(comments, cards, "comment")
    wins = B.split_windows(broll_plan)

    main_segs = reframe_main_for_splits(draft, wins) if wins else \
        sorted([t for t in draft["tracks"] if t["type"] == "video"][0]["segments"],
               key=lambda s: s["target_timerange"]["start"])
    print(f"main picture: {len(main_segs)} segments, {len(wins)} split windows")

    # ---- zoom on a share of the full-frame clips
    rng = random.Random(20260818)
    full = [s for s in main_segs if s["clip"]["transform"]["y"] == 0.0]
    want = round(a.zoom_share * len(full))
    eligible = sorted((s for s in full if s["target_timerange"]["duration"] >= 1_000_000),
                      key=lambda s: -s["target_timerange"]["duration"])
    for s in eligible[:want]:
        B.add_zoom(s, s["target_timerange"]["duration"], rng.random() < 0.5)
    print(f"zoom: {min(want, len(eligible))}/{len(full)} full-frame clips")

    tracks_added = 0
    if broll_plan and (a.broll or any(it.get("file") for it in broll_plan)):
        durs = {}

        def source_of(item):
            path_i = item.get("file") or a.broll
            if path_i not in durs:
                durs[path_i] = B.probe_duration_us(path_i)
            return path_i, durs[path_i]

        vproto = copy.deepcopy(main_segs[0])
        segs = []
        for item in sorted(broll_plan, key=lambda x: x["at"]):
            bpath, bdur = source_of(item)
            dur = int(round((item["until"] - item["at"]) * US))
            src = int(round(item["from"] * US))
            if dur <= 0 or src + dur > bdur:
                print(f"    [WARN] B-roll at {item['at']:.2f}s reads past the source, skipped")
                continue
            seg = copy.deepcopy(vproto)
            seg["id"] = B.uid()
            mat = copy.deepcopy(index(draft)[vproto["material_id"]][1])
            mat["id"] = B.uid()
            B.set_media(mat, bpath, bdur)
            if item.get("layout") == "split":
                B.set_crop(mat, B.SPLIT_CROP, 1 - B.SPLIT_CROP)
            else:
                mat.pop("crop", None)
            draft["materials"]["videos"].append(mat)
            seg["material_id"] = mat["id"]
            seg["extra_material_refs"] = []          # no grade, no retouch, no enhance
            vol = float(item.get("sound", 0.0))
            seg["volume"] = vol
            seg["last_nonzero_volume"] = vol or 1.0
            seg["render_index"] = 1
            seg["track_render_index"] = 1
            seg["common_keyframes"] = []
            seg["source_timerange"] = {"start": src, "duration": dur}
            seg["target_timerange"] = {"start": int(round(item["at"] * US)),
                                       "duration": dur}
            seg["clip"] = {"scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0,
                           "transform": {"x": 0.0,
                                         "y": B.SPLIT_TOP if item.get("layout") == "split" else 0.0},
                           "flip": {"horizontal": False, "vertical": False}, "alpha": 1.0}
            segs.append(seg)
        if segs:
            draft["tracks"].append({"type": "video", "attribute": 0, "flag": 0,
                                    "id": B.uid(), "name": "", "segments": segs,
                                    "is_default_name": True})
            tracks_added += 1
        print(f"B-roll: {len(segs)} inserts "
              f"({sum(1 for s in segs if s['volume'] > 0)} with sound)")

    if comments:
        photos = {m["id"] for m in text_donor.d["materials"]["videos"]
                  if m.get("type") == "photo"}
        proto = None
        for tr in text_donor.d["tracks"]:
            for sg in tr.get("segments", []):
                if sg.get("material_id") in photos:
                    proto = copy.deepcopy(sg)
                    break
            if proto:
                break
        segs = []
        if proto is None:
            print("    [WARN] no photo segment in the text donor; comment cards skipped")
        else:
            tby = text_donor.by_id
            for item in sorted(comments, key=lambda x: x["at"]):
                dur = int(round((item["until"] - item["at"]) * US))
                if dur <= 0 or not os.path.exists(item["file"]):
                    print(f"    [WARN] comment {item.get('file')} skipped")
                    continue
                seg = copy.deepcopy(proto)
                seg["id"] = B.uid()
                mat = copy.deepcopy(tby[proto["material_id"]][1])
                mat["id"] = B.uid()
                B.set_media(mat, item["file"], 10800000000)
                draft["materials"]["videos"].append(mat)
                seg["material_id"] = mat["id"]
                refs = []
                for r in proto["extra_material_refs"]:
                    if r in tby:
                        bucket, em = tby[r]
                        e2 = copy.deepcopy(em)
                        e2["id"] = B.uid()
                        draft["materials"].setdefault(bucket, []).append(e2)
                        refs.append(e2["id"])
                seg["extra_material_refs"] = refs
                sc = float(item.get("scale", 0.8))
                seg["volume"] = 0.0
                seg["render_index"] = 2
                seg["track_render_index"] = 2
                seg["common_keyframes"] = []
                seg["source_timerange"] = {"start": 0, "duration": dur}
                seg["target_timerange"] = {"start": int(round(item["at"] * US)),
                                           "duration": dur}
                seg["clip"] = {"alpha": 1.0, "rotation": 0.0,
                               "flip": {"horizontal": False, "vertical": False},
                               "scale": {"x": sc, "y": sc},
                               "transform": {"x": 0.0, "y": float(item.get("y", 0.3))}}
                segs.append(seg)
            if segs:
                draft["tracks"].append({"type": "video", "attribute": 0, "flag": 0,
                                        "id": B.uid(), "name": "", "segments": segs,
                                        "is_default_name": True})
                tracks_added += 1
            print(f"comments: {len(segs)} cards")

    # ---- invariants
    for tr in draft["tracks"]:
        prev = -1
        for s in sorted(tr["segments"], key=lambda x: x["target_timerange"]["start"]):
            t = s["target_timerange"]
            assert t["duration"] > 0, f"{tr['type']}: zero-length segment"
            assert t["start"] >= prev, f"{tr['type']}: overlapping segments"
            prev = t["start"] + t["duration"]
    ids = {m["id"] for b, items in draft["materials"].items() if isinstance(items, list)
           for m in items if isinstance(m, dict) and "id" in m}
    for tr in draft["tracks"]:
        for s in tr["segments"]:
            assert s["material_id"] in ids, f"dangling material in {tr['type']}"
            for r in s.get("extra_material_refs", []):
                assert r in ids, f"dangling extra ref in {tr['type']}"
    print(f"tracks now: {[(t['type'], len(t['segments'])) for t in draft['tracks']]}")

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
