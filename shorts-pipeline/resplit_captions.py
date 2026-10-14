"""Re-split CapCut's Auto Caption track into short, well-broken Thai cards.

CapCut's auto-caption gets the WORDS right but not the BREAKS: it hands back whole
paragraphs (197 characters over 17 seconds in one case). This keeps its text and its
timings and only changes where the lines break, using the same chunker the rest of the
pipeline uses — DP over bind-units with POS-based break costs, so a card never ends mid
phrase.

Timing inside a caption: CapCut gives one span per caption, not per word, so each new card
gets a slice of that span proportional to its **spoken** length (tone marks and the
above/below vowels take no time to say). The caption's own start and end are never moved,
so nothing drifts against the picture.

Writes back into the draft in place, after backing it up. CapCut must be closed, or it
overwrites the file from memory when it exits.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import time
import uuid

from thai_subtitle import build_dict, chunk_words, tokenize
from thai_timing import spoken_len

from config import CAPCUT_ROOT, BACKUP_DIR
US = 1_000_000
MIN_CARD = 0.35          # never emit a card shorter than this


def uid() -> str:
    return str(uuid.uuid4()).upper()


def split_caption(text: str, start: float, end: float, custom_dict=None
                  ) -> list[tuple[str, float, float]]:
    """One caption -> several cards, sharing its span by spoken length."""
    words = tokenize(text, custom_dict=custom_dict)
    groups = [g for g in chunk_words(words) if g]
    if len(groups) <= 1:
        return [(text, start, end)]

    weights = [sum(spoken_len(w) for w in g) or 0.5 for g in groups]
    total = sum(weights) or len(groups)
    out, t = [], start
    for i, (g, w) in enumerate(zip(groups, weights)):
        share = (end - start) * (w / total)
        hi = end if i == len(groups) - 1 else min(end, t + share)
        out.append(("".join(g), t, hi))
        t = hi

    # A card too short to read is worse than a slightly long one, so a short card borrows
    # from its neighbour — but only when the caption is long enough to give every piece its
    # minimum. A 8.4 s paragraph that splits into 30 pieces cannot: forcing 0.35 s each
    # needs 10.5 s, the surplus ran off the end of the caption and overlapped the next one.
    # When there is not enough room, proportional division is the honest answer.
    if len(out) * MIN_CARD <= (end - start):
        _borrow(out)

    # last line of defence: strictly increasing, inside the caption, nothing empty
    fixed, t = [], start
    for txt, a, bnd in out:
        a = max(a, t)
        bnd = max(a, min(bnd, end))
        fixed.append((txt, a, bnd))
        t = bnd
    return fixed


def _borrow(out):
    for i in range(len(out) - 1):
        txt, a, bnd = out[i]
        nxt_txt, _, nxt_end = out[i + 1]
        room = nxt_end - MIN_CARD          # the next card must keep this much for itself
        if bnd - a < MIN_CARD and room > bnd:
            bnd = min(a + MIN_CARD, room)
        bnd = max(a + 0.05, min(bnd, nxt_end - 0.05))
        out[i] = (txt, a, bnd)
        out[i + 1] = (nxt_txt, bnd, nxt_end)


def rebuild_track(draft: dict, track_index: int, custom_dict=None) -> tuple[int, int]:
    by = {m["id"]: m for m in draft["materials"]["texts"]}
    extras = {}
    for bucket, items in draft["materials"].items():
        if isinstance(items, list):
            for m in items:
                if isinstance(m, dict) and "id" in m:
                    extras[m["id"]] = (bucket, m)

    track = draft["tracks"][track_index]
    old = sorted(track["segments"], key=lambda s: s["target_timerange"]["start"])
    new_segs, new_texts = [], []
    keep_ids = set()

    for seg in old:
        tr = seg["target_timerange"]
        a, b = tr["start"] / US, (tr["start"] + tr["duration"]) / US
        mat = by[seg["material_id"]]
        text = json.loads(mat["content"])["text"]
        for card_text, cs, ce in split_caption(text, a, b, custom_dict):
            s2 = copy.deepcopy(seg)
            s2["id"] = uid()
            m2 = copy.deepcopy(mat)
            m2["id"] = uid()
            content = json.loads(m2["content"])
            content["text"] = card_text
            for st in content.get("styles", []):
                st["range"] = [0, len(card_text)]
            m2["content"] = json.dumps(content, ensure_ascii=False)
            m2["base_content"] = m2["content"]
            m2["words"] = {"start_time": [0], "end_time": [int((ce - cs) * 1000)],
                           "text": [card_text]}
            for k in ("recognize_task_id", "recognize_text"):
                if k in m2:
                    m2[k] = ""
            new_texts.append(m2)
            s2["material_id"] = m2["id"]

            refs = []
            for r in seg.get("extra_material_refs", []) or []:
                if r in extras:
                    bucket, em = extras[r]
                    em2 = copy.deepcopy(em)
                    em2["id"] = uid()
                    draft["materials"].setdefault(bucket, []).append(em2)
                    refs.append(em2["id"])
            s2["extra_material_refs"] = refs
            # Round to microseconds FIRST, then subtract. Rounding start and duration
            # separately lets round(cs)+round(ce-cs) land 1 us past round(ce), so the next
            # card started 1 us before this one ended and `assert_sane` fired at 11.39s.
            cs_us, ce_us = int(round(cs * US)), int(round(ce * US))
            s2["target_timerange"] = {"start": cs_us, "duration": ce_us - cs_us}
            s2["common_keyframes"] = []
            s2["keyframe_refs"] = []
            s2["group_id"] = ""
            new_segs.append(s2)

    for i, s in enumerate(new_segs):
        s["render_index"] = 14000 + i
    old_ids = {s["material_id"] for s in old}
    draft["materials"]["texts"] = [m for m in draft["materials"]["texts"]
                                   if m["id"] not in old_ids] + new_texts
    track["segments"] = new_segs
    return len(old), len(new_segs)


def assert_sane(track: dict, texts: dict) -> None:
    segs = sorted(track["segments"], key=lambda s: s["target_timerange"]["start"])
    prev = -1
    for s in segs:
        t = s["target_timerange"]
        if t["duration"] <= 0:
            raise AssertionError(f"non-positive duration at {t['start']/US:.2f}s")
        if t["start"] < prev:
            raise AssertionError(f"overlapping captions at {t['start']/US:.2f}s")
        prev = t["start"] + t["duration"]
        if not json.loads(texts[s["material_id"]]["content"])["text"].strip():
            raise AssertionError("empty caption produced")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True, help="draft folder name, e.g. 'Vegan V6'")
    p.add_argument("--track", type=int, default=None,
                   help="index of the text track (default: the one with most segments)")
    p.add_argument("--terms-file", default="")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    folder = os.path.join(CAPCUT_ROOT, a.draft)
    path = os.path.join(folder, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))

    idx = a.track
    if idx is None:
        cands = [(len(t["segments"]), i) for i, t in enumerate(draft["tracks"])
                 if t["type"] == "text" and t["segments"]]
        if not cands:
            raise SystemExit("no text track in that draft")
        idx = max(cands)[1]

    terms = []
    if a.terms_file:
        terms = [ln.strip() for ln in open(a.terms_file, encoding="utf-8")
                 if ln.strip() and not ln.startswith("#")]
    cd = build_dict(terms)

    before, after = rebuild_track(draft, idx, cd)
    texts = {m["id"]: m for m in draft["materials"]["texts"]}
    assert_sane(draft["tracks"][idx], texts)

    segs = sorted(draft["tracks"][idx]["segments"],
                  key=lambda s: s["target_timerange"]["start"])
    lens = [len(tokenize(json.loads(texts[s["material_id"]]["content"])["text"], custom_dict=cd))
            for s in segs]
    durs = [s["target_timerange"]["duration"] / US for s in segs]
    import collections
    print(f"captions {before} -> {after}")
    print(f"  words per card: {dict(sorted(collections.Counter(lens).items()))}")
    print(f"  duration min/median/max "
          f"{min(durs):.2f}/{sorted(durs)[len(durs)//2]:.2f}/{max(durs):.2f}s")

    if a.dry_run:
        for s in segs[:25]:
            t = s["target_timerange"]
            print(f"   {t['start']/US:7.2f}-{(t['start']+t['duration'])/US:7.2f}  "
                  f"{json.loads(texts[s['material_id']]['content'])['text']}")
        print("\ndry run — nothing written")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR,
                       f"{a.draft}.draft_content.json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, bak)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False)
    print(f"  backup  {bak}")
    print(f"  wrote   {path}")


if __name__ == "__main__":
    main()
