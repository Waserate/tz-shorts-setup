"""Make captions as large as they can be WITHOUT wrapping, splitting where needed.

Font size alone cannot solve this. A caption wraps when its width exceeds the text box, so
there are three levers and they trade against each other:

  * the box      — `line_max_width`, a fraction of canvas width (CapCut's default 0.82)
  * the size     — `font_size`, in CapCut units
  * the wording  — a card too wide for any acceptable size has to become two cards

🟥 `PX_PER_UNIT = 4.652` px per font_size unit. MEASURED, not guessed: two captions caught
mid-wrap bracket the box to 190.35 units, and 0.82 x 1080 / 190.35 = 4.652 — the stored
`line_max_width` and the observed wrap point agree, which is what makes it trustworthy. An
earlier guess of 3.3 was 40 % out and put 53 of 111 captions into a wrap. Re-derive this if
the canvas size or the font ever changes; never estimate it.

Over-wide captions are re-split by a DP that minimises the widest piece. A greedy
left-to-right split was tried first and it strands orphans ('คลิป' alone on a line, 17 times).

Timing: each caption's span is shared among its pieces by **spoken** length, and its own
start and end never move, so nothing drifts against the picture.
"""
from __future__ import annotations

import argparse
import collections
import copy
import json
import os
import shutil
import time
import uuid

from apply_caption_terms import space_scripts
from thai_subtitle import build_dict, tokenize
from thai_timing import spoken_len

from config import CAPCUT_ROOT, BACKUP_DIR, FONT_DIR
THAI_FONT = os.path.join(FONT_DIR, "NotoSansThai-Regular.ttf")
PX_PER_UNIT = 4.652
FIT_MARGIN = 0.98            # hinting makes the rendered advance differ from the estimate
US = 1_000_000
REF = 200
_FONT = None


def width_per_px(text: str) -> float:
    """Width of the text when the font is rendered at 1 px."""
    global _FONT
    if _FONT is None:
        from PIL import ImageFont
        _FONT = ImageFont.truetype(THAI_FONT, REF)
    return _FONT.getlength(text) / REF


def box_units(canvas_w: int, line_max_width: float) -> float:
    """How much `width_per_px * font_size` fits on one line."""
    return canvas_w * line_max_width / PX_PER_UNIT * FIT_MARGIN


def _balanced(tokens: list[str], k: int) -> list[str]:
    """Split into k consecutive pieces, minimising the widest piece."""
    n = len(tokens)
    pre = [0.0] * (n + 1)
    for i, t in enumerate(tokens):
        pre[i + 1] = pre[i] + width_per_px(t)
    INF = float("inf")
    best = [[INF] * (k + 1) for _ in range(n + 1)]
    cut = [[0] * (k + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, k + 1):
            for p in range(j - 1, i):
                v = max(best[p][j - 1], pre[i] - pre[p])
                if v < best[i][j]:
                    best[i][j], cut[i][j] = v, p
    out, i = [], n
    for j in range(k, 0, -1):
        p = cut[i][j]
        # Re-space each piece HERE, not before splitting: joining tokens with "" drops the
        # spaces that separate Latin from Thai, and doing it afterwards would leave the
        # width check measuring a string that is not what ends up on screen.
        out.append(space_scripts("".join(tokens[p:i])))
        i = p
    return out[::-1]


def fit_split(text: str, cap: float, custom_dict=None) -> list[str]:
    text = space_scripts(text)
    if width_per_px(text) <= cap:
        return [text]
    toks = tokenize(text, custom_dict=custom_dict)
    for k in range(2, len(toks) + 1):
        pieces = _balanced(toks, k)
        if max(width_per_px(p) for p in pieces) <= cap:
            return pieces
    return [text]


def share_time(pieces, start, end):
    weights = [sum(spoken_len(c) for c in p) or 1 for p in pieces]
    total = sum(weights)
    out, t = [], start
    for i, (p, wt) in enumerate(zip(pieces, weights)):
        hi = end if i == len(pieces) - 1 else min(end, t + (end - start) * wt / total)
        out.append((p, t, max(hi, t + 0.05)))
        t = out[-1][2]
    return out


def rebuild(draft, idx, size, line_max_width, custom_dict=None):
    canvas_w = draft["canvas_config"]["width"]
    cap = box_units(canvas_w, line_max_width) / size
    by = {m["id"]: m for m in draft["materials"]["texts"]}
    extras = {}
    for bucket, items in draft["materials"].items():
        if isinstance(items, list):
            for m in items:
                if isinstance(m, dict) and "id" in m:
                    extras[m["id"]] = (bucket, m)

    track = draft["tracks"][idx]
    old = sorted(track["segments"], key=lambda s: s["target_timerange"]["start"])
    new_segs, new_texts = [], []
    for seg in old:
        tr = seg["target_timerange"]
        a, b = tr["start"] / US, (tr["start"] + tr["duration"]) / US
        mat = by[seg["material_id"]]
        text = json.loads(mat["content"])["text"]
        for card, cs, ce in share_time(fit_split(text, cap, custom_dict), a, b):
            s2 = copy.deepcopy(seg)
            s2["id"] = str(uuid.uuid4()).upper()
            m2 = copy.deepcopy(mat)
            m2["id"] = str(uuid.uuid4()).upper()
            content = json.loads(m2["content"])
            content["text"] = card
            for st in content.get("styles", []):
                st["range"] = [0, len(card)]
                st["size"] = size
            m2["content"] = json.dumps(content, ensure_ascii=False)
            m2["base_content"] = m2["content"]
            m2["font_size"] = float(size)
            m2["line_max_width"] = float(line_max_width)
            m2["words"] = {"start_time": [0], "end_time": [int((ce - cs) * 1000)],
                           "text": [card]}
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
                    em2["id"] = str(uuid.uuid4()).upper()
                    draft["materials"].setdefault(bucket, []).append(em2)
                    refs.append(em2["id"])
            s2["extra_material_refs"] = refs
            s2["target_timerange"] = {"start": int(round(cs * US)),
                                      "duration": int(round((ce - cs) * US))}
            s2["common_keyframes"] = []
            s2["keyframe_refs"] = []
            s2["group_id"] = ""
            new_segs.append(s2)

    for i, s in enumerate(new_segs):
        s["render_index"] = 14000 + i
    dead = {s["material_id"] for s in old}
    draft["materials"]["texts"] = [m for m in draft["materials"]["texts"]
                                   if m["id"] not in dead] + new_texts
    track["segments"] = new_segs
    return len(old), len(new_segs), cap


def assert_fits(draft, idx, cap):
    """No caption may be wider than the box, and none may overlap."""
    by = {m["id"]: m for m in draft["materials"]["texts"]}
    segs = sorted(draft["tracks"][idx]["segments"],
                  key=lambda s: s["target_timerange"]["start"])
    prev, over = -1, []
    for s in segs:
        t = s["target_timerange"]
        if t["duration"] <= 0:
            raise AssertionError("non-positive caption duration")
        if t["start"] < prev:
            raise AssertionError(f"overlapping captions at {t['start']/US:.2f}s")
        prev = t["start"] + t["duration"]
        txt = json.loads(by[s["material_id"]]["content"])["text"]
        if not txt.strip():
            raise AssertionError("empty caption")
        if width_per_px(txt) > cap:
            over.append(txt)
    if over:
        raise AssertionError(f"{len(over)} captions still wider than the box, "
                             f"e.g. {over[0]!r}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--size", type=float, default=26.0)
    p.add_argument("--box", type=float, default=0.92, help="line_max_width, 0..1")
    p.add_argument("--terms-file", default="")
    p.add_argument("--from-backup", default="",
                   help="rebuild from this backup instead of the live draft")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    folder = os.path.join(CAPCUT_ROOT, a.draft)
    path = os.path.join(folder, "draft_content.json")
    draft = json.load(open(a.from_backup or path, encoding="utf-8"))

    cands = [(len(t["segments"]), i) for i, t in enumerate(draft["tracks"])
             if t["type"] == "text" and t["segments"]]
    if not cands:
        raise SystemExit("no text track")
    idx = max(cands)[1]

    terms = []
    if a.terms_file:
        terms = [ln.strip() for ln in open(a.terms_file, encoding="utf-8")
                 if ln.strip() and not ln.startswith("#")]
    cd = build_dict(terms)

    before = draft["materials"]["texts"][0]["font_size"]
    n0, n1, cap = rebuild(draft, idx, a.size, a.box, cd)
    assert_fits(draft, idx, cap)

    by = {m["id"]: m for m in draft["materials"]["texts"]}
    segs = sorted(draft["tracks"][idx]["segments"],
                  key=lambda s: s["target_timerange"]["start"])
    texts = [json.loads(by[s["material_id"]]["content"])["text"] for s in segs]
    nw = collections.Counter(len(tokenize(t, custom_dict=cd)) for t in texts)
    fill = [width_per_px(t) / cap * 100 for t in texts]
    print(f"captions {n0} -> {n1} | size {before:.2f} -> {a.size:g} "
          f"({a.size/before*100-100:+.0f}%) | box {a.box:g}")
    print(f"  words per card: {dict(sorted(nw.items()))} "
          f"({sum(v for k, v in nw.items() if 3 <= k <= 5)} in the 3-5 range)")
    print(f"  widest line fills {max(fill):.0f}% of the box — 0 wrap (asserted)")

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
