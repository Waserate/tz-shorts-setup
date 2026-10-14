"""Write a real, editable CapCut draft from the subtitle cards this pipeline generated.

Productionised from `spike/build_spike.py` (which stays frozen as the proof-of-concept).
Input is the `out.json` written by `run_subs.py`: a list of {start, end, text} in
SECONDS, measured against the audio file — not against the timeline.

Method is unchanged from the spike: **clone-from-donor**. Every segment and every
material is deep-copied out of a draft CapCut itself wrote, then re-id'd, re-timed and
re-pathed. Nothing is invented, because the 9.2 schema is far too large to synthesise.

Layout written (each one a separate track the user can edit or delete on its own):

    track 0  video   camera file, one uncut segment
    track 1  audio   external mic, one uncut segment, Enhancing voice ON
    track 2  text    one segment per subtitle card

A/V offset
----------
`--av-offset` is `video_time - audio_time`: the clock reading in the camera file for
content that sits at t=0 in the audio file. Negative means the recorder was rolling
before the camera started. Whichever file leads is trimmed at the head so both start
together at timeline 0, and the cards are shifted by the same amount.
"""
from __future__ import annotations

import argparse
import copy
import random
import json
import os
import shutil
import time
import uuid

from config import CAPCUT_ROOT, BACKUP_DIR, APP_VER, FONT_DIR
# A draft is only ever deleted if it carries this marker, i.e. only if WE wrote it.
# The user's own projects can never match, so pruning cannot reach their work.
MARKER = ".shorts-pipeline"
THAI_FONT = os.path.join(FONT_DIR, "th.ttf").replace("\\", "/")

US = 1_000_000


def uid() -> str:
    return str(uuid.uuid4()).upper()


def probe_duration_us(path: str) -> int:
    """Container duration. PyAV comes with faster-whisper; there is no ffmpeg on this box."""
    import av
    with av.open(path) as c:
        if not c.duration:
            raise RuntimeError(f"cannot read duration of {path}")
        return int(c.duration)          # AV_TIME_BASE is already microseconds


# --------------------------------------------------------------------------- donor


class Donor:
    """Index a CapCut-written draft so we can lift prototype segments + their materials."""

    def __init__(self, path: str):
        self.path = path
        self.d = json.load(open(path, encoding="utf-8"))
        self.by_id = {}
        for bucket, items in self.d["materials"].items():
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict) and "id" in it:
                        self.by_id[it["id"]] = (bucket, it)

    def track(self, ttype: str) -> dict:
        for tr in self.d["tracks"]:
            if tr["type"] == ttype and tr.get("segments"):
                return tr
        raise KeyError(f"no {ttype} track with segments in donor {self.path}")

    def proto(self, ttype: str) -> dict:
        return copy.deepcopy(self.track(ttype)["segments"][0])

    def media_path(self, ttype: str) -> str:
        seg = self.track(ttype)["segments"][0]
        return self.by_id[seg["material_id"]][1].get("path", "")


class Builder:
    def __init__(self, donor: Donor):
        self.donor = donor
        self.materials: dict[str, list] = {}
        self.tracks: list[dict] = []

    def _add(self, bucket: str, mat: dict) -> None:
        self.materials.setdefault(bucket, []).append(mat)

    def clone_segment(self, proto, *, target_start, target_dur, source_start=None,
                      mutate_material=None, mutate_extra=None, donor=None,
                      drop_buckets=()):
        """Deep-copy a donor segment + every material it references, with fresh ids.

        mutate_extra: {bucket: fn(mat)} applied to cloned extra materials by bucket.
        donor: which draft to resolve the material ids against. Picture and captions can
        come from different projects — the colour-graded clip lives in one, the caption
        styling in another — and each segment must be resolved against its own source.
        """
        donor = donor or self.donor
        seg = copy.deepcopy(proto)
        seg["id"] = uid()

        old_mid = seg.get("material_id")
        if old_mid and old_mid in donor.by_id:
            bucket, mat = donor.by_id[old_mid]
            mat = copy.deepcopy(mat)
            mat["id"] = uid()
            if mutate_material:
                mutate_material(mat)
            self._add(bucket, mat)
            seg["material_id"] = mat["id"]

        new_refs = []
        for ref in seg.get("extra_material_refs", []) or []:
            if ref in donor.by_id:
                bucket, mat = donor.by_id[ref]
                if bucket in drop_buckets:
                    continue          # e.g. B-roll must not inherit the host's grade
                mat = copy.deepcopy(mat)
                mat["id"] = uid()
                if mutate_extra and bucket in mutate_extra:
                    mutate_extra[bucket](mat)
                self._add(bucket, mat)
                new_refs.append(mat["id"])
        seg["extra_material_refs"] = new_refs

        seg["target_timerange"] = {"start": int(target_start), "duration": int(target_dur)}
        if seg.get("source_timerange") is not None and source_start is not None:
            seg["source_timerange"] = {"start": int(source_start), "duration": int(target_dur)}

        # never carry donor keyframe/group state into a fresh segment
        seg["common_keyframes"] = []
        seg["keyframe_refs"] = []
        seg["group_id"] = ""
        return seg

    def add_track(self, ttype: str, segments, *, flag=0, attribute=0, name=""):
        self.tracks.append({
            "type": ttype, "attribute": attribute, "flag": flag,
            "id": uid(), "name": name, "segments": segments,
            "is_default_name": True,
        })

    def finish(self, duration_us: int) -> dict:
        d = copy.deepcopy(self.donor.d)
        for bucket in d["materials"]:
            if isinstance(d["materials"][bucket], list):
                d["materials"][bucket] = []
        for bucket, items in self.materials.items():
            d["materials"][bucket] = items
        d["tracks"] = self.tracks
        d["id"] = uid()
        d["duration"] = int(duration_us)
        d["keyframes"] = {k: [] for k in d.get("keyframes", {})}
        d["keyframe_graph_list"] = []
        d["relationships"] = []
        d["platform"]["app_version"] = "9.2.0"
        d["last_modified_platform"]["app_version"] = "9.2.0"
        return d


# ---------------------------------------------------------------------- mutators


def set_media(mat: dict, path: str, dur_us: int) -> None:
    """Point a cloned video/audio material at our file."""
    name = os.path.basename(path)
    mat["path"] = path.replace("\\", "/")
    mat["duration"] = int(dur_us)
    for k, v in (("material_name", name), ("name", name)):
        if k in mat:
            mat[k] = v
    if "local_material_id" in mat:
        mat["local_material_id"] = ""


def set_card_text(mat: dict, text: str, dur_us: int, font: str = THAI_FONT,
                  size: float = 15.0) -> None:
    """Rewrite a donor caption material to our card, keeping the user's own styling.

    `size` is the number CapCut shows in the text panel. The user's own size-15 captions
    carry it in BOTH `font_size` and the style's `size`, with `text_size` left at 30 —
    change only one and the panel and the render disagree.
    """
    content = json.loads(mat["content"])
    content["text"] = text
    for st in content.get("styles", []):
        st["range"] = [0, len(text)]
        st.setdefault("font", {})["path"] = font
        st["size"] = size
    mat["font_size"] = float(size)
    mat["content"] = json.dumps(content, ensure_ascii=False)
    mat["base_content"] = mat["content"]
    mat["font_path"] = font
    mat["words"] = {"start_time": [0], "end_time": [int(dur_us / 1000)], "text": [text]}
    # this is OUR text, not a CapCut cloud recognition result
    for k in ("recognize_task_id", "recognize_text", "recognize_model", "punc_model"):
        if k in mat:
            mat[k] = ""


# ------------------------------------------------------------------------- cards


GROUP_DONOR = "1018"      # a project of the user's that actually contains a CapCut group


def lock_av(content: dict, vid_segs: list[dict], aud_segs: list[dict]) -> bool:
    """Link each picture segment to ITS OWN sound segment — one group per cut, not one
    group for the whole timeline.

    One big group would also keep audio with video, but it welds all 56 clips into a
    single lump: the user could no longer nudge one clip without dragging the entire
    edit. Pairing preserves clip-level editing while making the pairing unbreakable.

    The group entry is deep-copied from a project CapCut itself wrote — it carries a large
    `material_draft` blob that is not worth inventing. Subtitles are deliberately left out
    of every group so the user can still retype a card on its own.
    """
    src = os.path.join(CAPCUT_ROOT, GROUP_DONOR, "draft_content.json")
    try:
        groups = json.load(open(src, encoding="utf-8"))["group_container"]["groups"]
        proto = groups[0]
    except (OSError, KeyError, IndexError):
        print(f"    WARNING no group donor in {GROUP_DONOR}; A/V left unlinked")
        return False

    out = []
    for i, (v, a) in enumerate(zip(vid_segs, aud_segs)):
        gid = uid()
        v["group_id"] = a["group_id"] = gid
        g = copy.deepcopy(proto)
        g.update({"id": gid, "group_index": i, "group_main_id": "",
                  "group_members": [v["id"], a["id"]], "is_expand": True, "name": ""})
        if isinstance(g.get("material_draft"), dict):
            g["material_draft"]["id"] = uid()
        out.append(g)
    content["group_container"] = {"groups": out}
    return True


def uncaptioned_after_cut(mask, keeps, cards) -> list[tuple[float, float]]:
    """Kept audio that is voiced and carries no caption.

    The user's rule: every word that survives the cut gets a subtitle. Anything listed here
    breaks it — the viewer hears talking and reads nothing — so it is reported loudly rather
    than shipped quietly.
    """
    import fill_gaps
    inside = []
    for a, b in fill_gaps.uncaptioned_spans(mask, cards, min_gap=1.0):
        for ks, ke in keeps:
            lo, hi = max(a, ks), min(b, ke)
            if hi - lo >= 1.0:
                inside.append((lo, hi))
    return inside


SPLIT_TOP = 0.5          # normalised transform for the top half of the canvas
SPLIT_CROP = 0.25        # crop this much off each end -> the middle 50% of the frame


def set_crop(mat, top, bottom):
    """Keep only the vertical band [top, bottom] of the source, in 0..1 of frame height.

    Cropping is stored on the MATERIAL as four corner points, not as a rectangle, so all
    four have to move together or CapCut renders a trapezoid.
    """
    mat["crop"] = {"upper_left_x": 0.0, "upper_left_y": top,
                   "upper_right_x": 1.0, "upper_right_y": top,
                   "lower_left_x": 0.0, "lower_left_y": bottom,
                   "lower_right_x": 1.0, "lower_right_y": bottom}
    mat["crop_ratio"] = "free"
    mat["crop_scale"] = 1.0


def add_zoom(seg, dur_us, zoom_in, amount=0.06):
    """A slow push in or out across the whole segment.

    CapCut drives this from a KFTypeScaleX keyframe list on the segment; with uniform_scale
    on, Y follows X, so one property is a proportional zoom. Structure copied from a
    keyframed segment in the user's own 0727 project.
    """
    lo, hi = 1.0, 1.0 + amount
    first, last = (lo, hi) if zoom_in else (hi, lo)
    seg["uniform_scale"] = {"on": True, "value": 1.0}
    seg["common_keyframes"] = [{
        "id": uid(), "property_type": "KFTypeScaleX", "keyframe_list": [
            {"curveType": "Line", "graphID": "", "id": uid(),
             "left_control": {"x": 0.0, "y": 0.0}, "right_control": {"x": 0.0, "y": 0.0},
             "string_value": "", "time_offset": 0, "values": [first]},
            {"curveType": "Line", "graphID": "", "id": uid(),
             "left_control": {"x": 0.0, "y": 0.0}, "right_control": {"x": 0.0, "y": 0.0},
             "string_value": "", "time_offset": int(dur_us), "values": [last]},
        ]}]


def make_broll_mutator(path, dur_us, is_split):
    def mutate(m):
        set_media(m, path, dur_us)
        if is_split:
            set_crop(m, SPLIT_CROP, 1 - SPLIT_CROP)
    return mutate


def split_windows(plan):
    """Timeline ranges where picture and B-roll share the frame."""
    return sorted((i["at"], i["until"]) for i in plan
                  if i.get("layout") == "split" and "at" in i)


def slice_at(s, e, t0, wins):
    """Cut one kept span into pieces at every split boundary.

    The main clip must be its own segment wherever it is reframed to the bottom half, and
    the cut list knows nothing about the B-roll plan, so the boundaries are applied here.
    Yields (src_start, src_end, timeline_start, is_split).
    """
    marks = {s, e}
    for a, bw in wins:
        for m in (s + (a - t0), s + (bw - t0)):
            if s < m < e:
                marks.add(m)
    pts = sorted(marks)
    for i in range(len(pts) - 1):
        lo, hi = pts[i], pts[i + 1]
        mid_tl = t0 + ((lo + hi) / 2 - s)
        yield lo, hi, t0 + (lo - s), any(a <= mid_tl < bw for a, bw in wins)


def resolve_anchors(plan: list[dict], cards: list[dict], label: str) -> list[dict]:
    """Turn `anchor`/`until_anchor` phrases into timeline seconds.

    Absolute seconds in a plan are a trap: the cut changes whenever the cleaner improves,
    the whole narration slides, and every insert silently lands on the wrong line. Tightening
    the junk filter once moved this timeline 118.5s -> 109.3s and put all 19 inserts out of
    place. Anchoring to the spoken line means the plan survives a re-cut.
    """
    from rapidfuzz import fuzz

    def find(phrase):
        # Length guard. partial_ratio scores 100 whenever the card text is a substring of
        # the anchor, so the 10-character card 'เนื้อสัตว์' matched the 21-character anchor
        # 'ากขอลองกินเนื้อสัตว์ดู' perfectly and dragged an insert 19 s out of place.
        # A card can only be the anchor if it is of comparable length.
        floor = 0.6 * len(phrase)
        best, score = None, -1
        for c in cards:
            if len(c["text"]) < floor:
                continue
            s = fuzz.partial_ratio(phrase, c["text"])
            # on ties prefer the card closest in length — the least surprising reading
            key = (s, -abs(len(c["text"]) - len(phrase)))
            if best is None or key > (score, -abs(len(best["text"]) - len(phrase))):
                best, score = c, s
        return best, score

    out = []
    for i, item in enumerate(plan):
        if "anchor" not in item:
            out.append(item)
            continue
        a, sa = find(item["anchor"])
        if sa < 80:
            print(f"    [WARN] {label} {i}: anchor {item['anchor']!r} matched nothing "
                  f"(best {sa:.0f}) — skipped")
            continue
        end = a
        if item.get("until_anchor"):
            b, sb = find(item["until_anchor"])
            if sb >= 80 and b["end"] > a["start"]:
                end = b
        out.append({**item, "at": a["start"], "until": end["end"]})
    return out


def load_cards(path: str) -> list[dict]:
    cards = json.load(open(path, encoding="utf-8"))
    if not cards:
        raise SystemExit(f"{path} has no cards")
    return cards


def shift_cards(cards: list[dict], head_trim: float, span: float) -> list[dict]:
    """Move card times from audio-file time onto timeline time, dropping what falls off."""
    out = []
    for c in cards:
        st, en = c["start"] - head_trim, c["end"] - head_trim
        if en <= 0 or st >= span:
            continue
        out.append({"start": max(0.0, st), "end": min(span, en), "text": c["text"]})
    return [c for c in out if c["end"] - c["start"] > 0.05]


# -------------------------------------------------------------------- invariants


class DraftError(AssertionError):
    pass


def assert_draft_sane(d: dict) -> None:
    """States that must never reach CapCut. Invariants, not tests: they crash loudly."""
    for tr in d["tracks"]:
        segs = sorted(tr["segments"], key=lambda s: s["target_timerange"]["start"])
        if not segs:
            raise DraftError(f"{tr['type']}: empty track")
        for i, s in enumerate(segs):
            t = s["target_timerange"]
            if t["duration"] <= 0:
                raise DraftError(f"{tr['type']}: zero/negative duration segment")
            if t["start"] < 0:
                raise DraftError(f"{tr['type']}: negative start")
            src = s.get("source_timerange")
            if src and src["start"] < 0:
                raise DraftError(f"{tr['type']}: negative source start")
            if i:
                p = segs[i - 1]["target_timerange"]
                if t["start"] < p["start"] + p["duration"]:
                    raise DraftError(f"{tr['type']}: overlapping segments "
                                     "(CapCut forbids this on a text track)")
    ids = set()
    for items in d["materials"].values():
        if isinstance(items, list):
            ids |= {m["id"] for m in items if isinstance(m, dict) and "id" in m}
    for tr in d["tracks"]:
        for s in tr["segments"]:
            if s["material_id"] not in ids:
                raise DraftError(f"dangling material_id in {tr['type']}")
            for r in s.get("extra_material_refs", []):
                if r not in ids:
                    raise DraftError(f"dangling extra_material_ref in {tr['type']}")
    vids = [t for t in d["tracks"] if t["type"] == "video"]
    if not vids or vids[0]["segments"][0]["target_timerange"]["start"] != 0:
        raise DraftError("main video track must start at 0")
    for m in d["materials"].get("texts", []):
        if not json.loads(m["content"])["text"].strip():
            raise DraftError("empty subtitle card reached the draft")


def assert_av_locked(d: dict) -> None:
    """Picture and sound must occupy exactly the same stretches of timeline.

    This is the real meaning of "video and audio move together": if the two tracks ever
    disagree, the narration is playing over the wrong frames and every subtitle after that
    point is wrong too. An invariant catches the whole class; a test only catches the cut
    plans someone thought to write down.
    """
    def ranges(kind):
        tr = [t for t in d["tracks"] if t["type"] == kind]
        return [(s["target_timerange"]["start"], s["target_timerange"]["duration"])
                for t in tr for s in t["segments"]]

    v, a = sorted(ranges("video")), sorted(ranges("audio"))
    if not a:
        return          # sound lives inside the video file; they cannot come apart
    if v != a:
        raise DraftError(
            f"picture and sound are not the same cut: {len(v)} video vs {len(a)} audio "
            f"segments, first mismatch {next((x, y) for x, y in zip(v + [None], a + [None]) if x != y)}")
    # and each pair must read the same stretch of the two source files
    seen = {}
    for t in d["tracks"]:
        if t["type"] not in ("video", "audio"):
            continue
        for s in t["segments"]:
            key = s["target_timerange"]["start"]
            seen.setdefault(key, {})[t["type"]] = s["source_timerange"]["duration"]
    for key, pair in seen.items():
        if pair.get("video") != pair.get("audio"):
            raise DraftError(f"segment at {key / US:.3f}s reads {pair} — different lengths")


def assert_media_in_range(d: dict, limits: dict[str, int]) -> None:
    """A segment may never read past the end of its own source file."""
    by_id = {}
    for items in d["materials"].values():
        if isinstance(items, list):
            for m in items:
                if isinstance(m, dict) and "id" in m:
                    by_id[m["id"]] = m
    for tr in d["tracks"]:
        for s in tr["segments"]:
            src = s.get("source_timerange")
            mat = by_id[s["material_id"]]
            path = mat.get("path", "")
            if not src or path not in limits:
                continue
            if src["start"] + src["duration"] > limits[path] + 1000:
                raise DraftError(
                    f"{tr['type']}: reads {(src['start'] + src['duration']) / US:.3f}s of "
                    f"{os.path.basename(path)} but the file is only {limits[path] / US:.3f}s")


# ------------------------------------------------------------------------- write


def backup_root_meta() -> str:
    """root_meta_info.json is the gatekeeper for every draft on this machine."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    src = os.path.join(CAPCUT_ROOT, "root_meta_info.json")
    dst = os.path.join(BACKUP_DIR,
                       "root_meta_info.json.bak-" + time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(src, dst)
    return dst


def prune_old_drafts(keep: str) -> list[str]:
    """Keep only the newest pipeline draft — each one costs ~160 MB of the user's C: drive.

    Eligibility is the marker file, never the name: a draft this pipeline did not write
    has no marker and is therefore untouchable. The donor project is safe for the same
    reason, which matters because deleting it would break every future build.
    """
    removed = []
    for name in sorted(os.listdir(CAPCUT_ROOT)):
        d = os.path.join(CAPCUT_ROOT, name)
        if name == keep or not os.path.isdir(d):
            continue
        if not os.path.exists(os.path.join(d, MARKER)):
            continue
        shutil.rmtree(d)
        removed.append(name)
    if removed:
        rp = os.path.join(CAPCUT_ROOT, "root_meta_info.json")
        root = json.load(open(rp, encoding="utf-8"))
        store = root["all_draft_store"]
        store[:] = [e for e in store if e.get("draft_name") not in removed]
        with open(rp, "w", encoding="utf-8") as f:
            json.dump(root, f, ensure_ascii=False)
    return removed


def register(name: str, fold: str, draft_id: str, now_us: int, dur_us: int) -> None:
    """CapCut only lists drafts present in root_meta_info.json."""
    rp = os.path.join(CAPCUT_ROOT, "root_meta_info.json")
    root = json.load(open(rp, encoding="utf-8"))
    store = root["all_draft_store"]
    store[:] = [e for e in store if e.get("draft_name") != name]
    entry = copy.deepcopy(store[0])
    entry.update({
        "draft_fold_path": fold,
        "draft_id": draft_id,
        "draft_name": name,
        "draft_cover": fold + "/draft_cover.jpg",
        "draft_json_file": fold + "/draft_content.json",
        "draft_root_path": CAPCUT_ROOT,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_duration": int(dur_us),
    })
    store.insert(0, entry)
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(root, f, ensure_ascii=False)


def build(cards_path, video, audio, name, av_offset, donor_name, text_donor_name=None,
          enhance=True, audio_volume=1.0, video_volume=0.0, keep_all=False,
          cut=True, lock=True, drop_repeats=True, min_silence=0.35, font_size=15.0,
          start_at=0.0, broll=None, broll_plan=None, comments=None, zoom_share=0.6):
    donor_dir = os.path.join(CAPCUT_ROOT, donor_name)
    donor = Donor(os.path.join(donor_dir, "draft_content.json"))
    text_donor = donor if text_donor_name in (None, donor_name) else Donor(
        os.path.join(CAPCUT_ROOT, text_donor_name, "draft_content.json"))
    b = Builder(donor)

    # No separate recorder: the sound is the video's own track. There is nothing to sync,
    # and picture and sound cannot drift because they are one file.
    embedded = audio is None
    if embedded:
        audio = video
        av_offset = 0.0

    vid_dur = probe_duration_us(video)
    aud_dur = probe_duration_us(audio)

    # The camera started after the recorder (or the reverse), so no audio before this
    # point has a picture to go with it and nothing there can be kept.
    floor = max(0.0, -av_offset)
    if min(vid_dur - int(max(0.0, av_offset) * US), aud_dur - int(floor * US)) <= 0:
        raise SystemExit("av-offset leaves no overlap between the two files")

    cards = load_cards(cards_path)          # times are in AUDIO-file seconds

    # ---- the cut plan: ONE list of keep intervals that picture, sound and text all obey
    if cut:
        from cut_plan import plan, remap_cards
        from speech_mask import SpeechMask
        mask = SpeechMask(audio)
        dead = []
        dead_path = cards_path.replace(".json", ".dead.json")
        if os.path.exists(dead_path):
            dead = [tuple(x) for x in json.load(open(dead_path, encoding="utf-8"))]
        keeps, report = plan(mask, cards, min_silence=min_silence,
                             drop_repeats=drop_repeats, start_floor=floor,
                             start_at=start_at, dead_spans=dead)
        src_cards, cards = cards, remap_cards(cards, keeps)
        left = uncaptioned_after_cut(mask, keeps, src_cards)
        if left:
            print(f"    [WARN] {len(left)} kept spans still have speech with no caption:")
            for lo_s, hi_s in left[:8]:      # NOT a, b — `b` is the Builder in this scope
                print(f"           source {lo_s:7.2f}-{hi_s:7.2f}  ({hi_s-lo_s:.1f}s)")
    else:
        keeps = [(floor, min(aud_dur / US, (vid_dur / US) - av_offset))]
        report = None
        cards = shift_cards(cards, floor, keeps[0][1] - keeps[0][0])
    if not keeps:
        raise SystemExit("the cut plan kept nothing")
    if not cards:
        raise SystemExit("every card fell outside the kept material")

    # Resolve before any segment is built: a split insert forces the main clip to be cut
    # at its boundaries, so the plan has to be known first.
    if broll and broll_plan:
        broll_plan = resolve_anchors(broll_plan, cards, "B-roll")
    if comments:
        comments = resolve_anchors(comments, cards, "comment")
    wins = split_windows(broll_plan or [])

    reuse_alg = os.path.normcase(donor.media_path("video" if embedded else "audio")) == \
        os.path.normcase(audio.replace("\\", "/"))

    def fix_beautify(m):
        m["enable"] = bool(enhance)
        if not reuse_alg:
            # the cached artifact is keyed to the donor's audio; make CapCut recompute
            m["production_path"] = ""
        m["time_range"] = {"start": 0, "duration": int(aud_dur)}

    # ---- picture and sound: the SAME cut, segment for segment. This is the lock: they
    # are built from one list, so they cannot be out of step in the file.
    v_proto = donor.proto("video")
    a_proto = None if embedded else donor.proto("audio")
    vid_segs, aud_segs, t = [], [], 0.0
    rng = random.Random(20260818)      # deterministic: same build, same zooms
    for s, e in keeps:
        dur = int(round((e - s) * US))
        tgt = int(round(t * US))
        # When the sound is embedded, the video segment carries the Enhance-voice material
        # too, so the same mutator has to run on it.
        for lo, hi, tl, is_split in slice_at(s, e, t, wins):
            pdur = int(round((hi - lo) * US))
            if pdur <= 0:
                continue

            def mutate_main(m, sp=is_split):
                set_media(m, video, vid_dur)
                if sp:
                    set_crop(m, SPLIT_CROP, 1 - SPLIT_CROP)

            v = b.clone_segment(
                v_proto, target_start=int(round(tl * US)), target_dur=pdur,
                source_start=int(round((lo + av_offset) * US)),
                mutate_material=mutate_main,
                mutate_extra={"vocal_beautifys": fix_beautify} if embedded else None)
            v["volume"] = float(audio_volume if embedded else video_volume)
            v["last_nonzero_volume"] = float(audio_volume) or 1.0
            v["render_index"] = 0
            v["track_render_index"] = 0
            if is_split:
                v["clip"]["transform"] = {"x": 0.0, "y": -SPLIT_TOP}   # sits underneath
            vid_segs.append(v)

        if not embedded:
            a = b.clone_segment(a_proto, target_start=tgt, target_dur=dur,
                                source_start=int(round(s * US)),
                                mutate_material=lambda m: set_media(m, audio, aud_dur),
                                mutate_extra={"vocal_beautifys": fix_beautify})
            a["volume"] = float(audio_volume)
            a["last_nonzero_volume"] = float(audio_volume) or 1.0
            a["render_index"] = 0
            a["track_render_index"] = 1
            aud_segs.append(a)
        t += e - s
    span = int(round(t * US))

    # ---- slow push on a share of the full-frame clips.
    # Decided AFTER the segments exist, not per clip as they are made: the share is of all
    # full-frame clips, and deciding one at a time cannot hit a target it does not yet know
    # the denominator of (it landed at 34% when 60% was asked for). Longest clips win,
    # because a 0.3 s piece cannot show a move.
    full_idx = [i for i, v in enumerate(vid_segs)
                if v["clip"]["transform"]["y"] == 0.0]
    want = round(zoom_share * len(full_idx))
    eligible = sorted((i for i in full_idx
                       if vid_segs[i]["target_timerange"]["duration"] >= 1_000_000),
                      key=lambda i: -vid_segs[i]["target_timerange"]["duration"])
    zoomed = 0
    for i in eligible[:want]:
        add_zoom(vid_segs[i], vid_segs[i]["target_timerange"]["duration"],
                 rng.random() < 0.5)
        zoomed += 1

    # ---- text: one segment per card
    t_proto = text_donor.proto("text")
    text_segs = []
    for i, c in enumerate(cards):
        dur = int(round((c["end"] - c["start"]) * US))
        seg = b.clone_segment(
            t_proto, target_start=int(round(c["start"] * US)), target_dur=dur,
            mutate_material=lambda m, x=c["text"], d=dur: set_card_text(
                m, x, d, size=font_size),
            donor=text_donor)
        seg["render_index"] = 14000 + i
        seg["track_render_index"] = 2
        text_segs.append(seg)

    # ---- B-roll overlay: source footage cut in over the narration.
    # A separate track on purpose, so it can be nudged or deleted on its own without
    # touching the edit underneath. Muted — the narration is the only voice.
    broll_segs = []
    if broll and broll_plan:
        bdur = probe_duration_us(broll)
        for i, item in enumerate(sorted(broll_plan, key=lambda x: x["at"])):
            start, end, src = item["at"], item["until"], item["from"]
            dur = int(round((end - start) * US))
            src_us = int(round(src * US))
            if dur <= 0 or src_us + dur > bdur:
                print(f"    [WARN] B-roll {i} skipped: reads past the end of the source")
                continue
            seg = b.clone_segment(
                v_proto, target_start=int(round(start * US)), target_dur=dur,
                source_start=src_us,
                mutate_material=make_broll_mutator(broll, bdur,
                                                   item.get("layout") == "split"),
                # never inherit the host clip's colour grade, beauty or Enhance voice
                drop_buckets=("effects", "hsl", "vocal_beautifys", "material_colors"))
            vol = float(item.get("sound", 0.0))
            seg["volume"] = vol      # sound-on inserts let her own reaction be heard
            seg["last_nonzero_volume"] = vol or 1.0
            seg["render_index"] = 1
            seg["track_render_index"] = 1
            top = SPLIT_TOP if item.get("layout") == "split" else 0.0
            seg["clip"] = {"scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0,
                           "transform": {"x": 0.0, "y": top},
                           "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0}
            for k in ("enable_adjust", "enable_lut", "enable_hsl", "enable_color_curves"):
                if k in seg:
                    seg[k] = False
            broll_segs.append(seg)

    # ---- comment cards: stills cut in over the top, their own track again
    cmt_segs = []
    if comments:
        photo_proto = None
        photos = {m["id"] for m in text_donor.d["materials"]["videos"]
                  if m.get("type") == "photo"}
        for tr in text_donor.d["tracks"]:
            if tr["type"] != "video":
                continue
            for sg in tr["segments"]:
                if sg["material_id"] in photos:
                    photo_proto = copy.deepcopy(sg)
                    break
            if photo_proto:
                break
        if photo_proto is None:
            print("    [WARN] no photo segment in the donor; comment cards skipped")
        for i, item in enumerate(sorted(comments, key=lambda x: x["at"])):
            dur = int(round((item["until"] - item["at"]) * US))
            if dur <= 0 or not os.path.exists(item["file"]):
                print(f"    [WARN] comment {i} skipped ({item.get('file')})")
                continue
            sc = float(item.get("scale", 0.8))
            seg = b.clone_segment(
                photo_proto, target_start=int(round(item["at"] * US)), target_dur=dur,
                source_start=0, donor=text_donor,
                mutate_material=lambda m, f=item["file"]: set_media(m, f, 10800000000))
            seg["volume"] = 0.0
            seg["render_index"] = 2
            seg["track_render_index"] = 2
            seg["clip"] = {"alpha": 1.0, "rotation": 0.0,
                           "flip": {"horizontal": False, "vertical": False},
                           "scale": {"x": sc, "y": sc},
                           "transform": {"x": 0.0, "y": float(item.get("y", 0.3))}}
            cmt_segs.append(seg)

    b.add_track("video", vid_segs)
    if broll_segs:
        b.add_track("video", broll_segs)
    if cmt_segs:
        b.add_track("video", cmt_segs)
    if aud_segs:
        b.add_track("audio", aud_segs)
    b.add_track("text", text_segs, flag=1)

    content = b.finish(span)
    if lock and aud_segs:
        lock_av(content, vid_segs, aud_segs)
    assert_draft_sane(content)
    assert_av_locked(content)
    assert_media_in_range(content, {video.replace("\\", "/"): vid_dur,
                                    audio.replace("\\", "/"): aud_dur})

    # ---- write the draft folder
    out_dir = os.path.join(CAPCUT_ROOT, name)
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    for aux in ("draft_meta_info.json", "draft_cover.jpg"):
        src = os.path.join(donor_dir, aux)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(out_dir, aux))
    if enhance and reuse_alg:
        # Enhancing voice is a pre-rendered wav living in the draft's own Resources dir;
        # the donor already computed it for this exact file, so carry it across. Copy ONLY
        # the file the vocal_beautify actually points at — the donor's audioAlg folder also
        # holds vocal/background separation renders we never reference, and copying the
        # whole folder cost ~120 MB per draft.
        wanted = os.path.basename(
            b.materials["vocal_beautifys"][0].get("production_path", ""))
        src = os.path.join(donor_dir, "Resources", "audioAlg", wanted)
        if wanted and os.path.exists(src):
            dst_dir = os.path.join(out_dir, "Resources", "audioAlg")
            os.makedirs(dst_dir)
            shutil.copy2(src, os.path.join(dst_dir, wanted))
        else:
            print(f"    WARNING enhance artifact {wanted!r} not in donor; CapCut will recompute")

    with open(os.path.join(out_dir, "draft_content.json"), "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False)

    now_us = int(time.time() * US)
    fold = out_dir.replace("\\", "/")
    draft_id = uid()
    meta_path = os.path.join(out_dir, "draft_meta_info.json")
    meta = json.load(open(meta_path, encoding="utf-8"))
    meta.update({
        "draft_fold_path": fold,
        "draft_id": draft_id,
        "draft_name": name,
        "draft_cover": fold + "/draft_cover.jpg",
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_duration": int(span),
    })
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)

    open(os.path.join(out_dir, MARKER), "w").close()   # this draft is ours to delete later

    bak = backup_root_meta()
    register(name, fold, draft_id, now_us, span)
    dropped = [] if keep_all else prune_old_drafts(name)

    print(f"OK  {out_dir}")
    print(f"    tracks       {[(t['type'], len(t['segments'])) for t in content['tracks']]}")
    print(f"    timeline     {span / US:.3f}s")
    print(f"    av-offset    {av_offset:+.3f}s   floor {floor:.3f}s"
          f"{'   (sound embedded in the video)' if embedded else ''}")
    if report:
        for line in report.lines():
            print("    " + line)
    print(f"    cards        {len(cards)} (from {len(load_cards(cards_path))})")
    print(f"    font size    {font_size}")
    print(f"    layout       {len(wins)} split windows, {zoomed}/{len(full_idx)} full-frame clips zoomed")
    print(f"    comments     {len(cmt_segs)} cards")
    print(f"    B-roll       {len(broll_segs)} inserts"
          f"{' from ' + os.path.basename(broll) if broll else ''}")
    print(f"    A/V locked   "
          f"{'inherent (one file)' if embedded else (f'yes, {len(keeps)} pairs' if lock else 'no')}")
    print(f"    enhance      {'ON' if enhance else 'OFF'}"
          f"{'' if reuse_alg else ' (CapCut will recompute — different audio file)'}")
    print(f"    root backup  {bak}")
    print(f"    pruned       {', '.join(dropped) if dropped else 'nothing'}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cards", required=True, help="out.json from run_subs.py")
    p.add_argument("--video", required=True)
    p.add_argument("--audio", default=None,
                   help="separate mic recording; omit when the sound is inside --video")
    p.add_argument("--name", required=True, help="CapCut draft name")
    p.add_argument("--av-offset", type=float, default=0.0,
                   help="video_time - audio_time in seconds (negative = camera started later)")
    p.add_argument("--donor", default="0813",
                   help="draft to clone picture segments from (carries colour + enhance)")
    p.add_argument("--text-donor", default="0813",
                   help="draft to clone caption segments from")
    p.add_argument("--no-enhance", action="store_true", help="turn Enhancing voice OFF")
    p.add_argument("--audio-volume", type=float, default=1.0)
    p.add_argument("--video-volume", type=float, default=0.0)
    p.add_argument("--keep-all", action="store_true",
                   help="do not delete older pipeline drafts (default: keep only this one)")
    p.add_argument("--no-cut", action="store_true",
                   help="keep the take whole (default: cut dead air and repeated takes)")
    p.add_argument("--keep-repeats", action="store_true",
                   help="cut dead air but keep every take")
    p.add_argument("--min-silence", type=float, default=0.35,
                   help="pause longer than this counts as dead air")
    p.add_argument("--no-lock", action="store_true",
                   help="do not group picture and sound together in CapCut")
    p.add_argument("--font-size", type=float, default=15.0)
    p.add_argument("--broll", default=None, help="source footage to cut in as B-roll")
    p.add_argument("--zoom-share", type=float, default=0.6,
                   help="fraction of full-frame main clips that get a slow push (0..1)")
    p.add_argument("--comments", default=None,
                   help="json list of {at, until, file, scale, y} comment-card overlays")
    p.add_argument("--broll-plan", default=None,
                   help="json list of {at, until, from} in seconds (timeline, timeline, source)")
    p.add_argument("--start-at", type=float, default=0.0,
                   help="audio-file seconds where the real content begins; everything "
                        "before it is dropped (for a false start the text cannot see)")
    a = p.parse_args()
    build(a.cards, a.video, a.audio, a.name, a.av_offset, a.donor, a.text_donor,
          enhance=not a.no_enhance, audio_volume=a.audio_volume,
          video_volume=a.video_volume, keep_all=a.keep_all,
          cut=not a.no_cut, lock=not a.no_lock, drop_repeats=not a.keep_repeats,
          min_silence=a.min_silence, font_size=a.font_size, start_at=a.start_at,
          broll=a.broll,
          broll_plan=json.load(open(a.broll_plan, encoding="utf-8")) if a.broll_plan else None,
          comments=json.load(open(a.comments, encoding="utf-8")) if a.comments else None,
          zoom_share=a.zoom_share)


if __name__ == "__main__":
    main()
