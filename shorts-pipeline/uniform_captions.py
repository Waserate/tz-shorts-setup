"""Give every caption ONE size, and make Latin stand the same height as Thai.

Two things were wrong on screen:

* The captions ranged 14.6 to 26. Each one had been shrunk just enough to fit its own text,
  so a long card was visibly smaller than the card before it.
* Thai and Latin carried the same NUMBER but did not look the same size. A Latin capital is
  taller than a Thai body at equal font size — measured at 143px vs 112px — so "Vegan" stood
  over the Thai around it. Anchoring to Thai means the Latin runs take that ratio.

One size for the whole clip means the size is set by the widest card, so the cards that are
too long to fit are SPLIT rather than shrunk. Splitting costs a few more cards; shrinking
costs the size of every other caption on screen.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import time
import uuid

from fit_caption_sizes import _balanced
from style_captions import room_units, width_per_px
from match_script_heights import is_latin, runs
from thai_subtitle import build_dict, tokenize
from thai_timing import spoken_len

from config import CAPCUT_ROOT, BACKUP_DIR
US = 1_000_000
LATIN_RATIO = 0.783          # measured: Thai base 112px vs Latin cap 143px at equal size


def units(text: str) -> float:
    """Width of the text at Thai size 1, with the Latin runs already scaled down."""
    return sum(width_per_px(text[a:b]) * (LATIN_RATIO if lat else 1.0)
               for a, b, lat in runs(text))


def restyle(content: dict, text: str, size: float) -> None:
    """One size for the card, with Latin shrunk to match the Thai height."""
    proto = copy.deepcopy(content["styles"][0])
    styles = []
    for a, b, lat in runs(text):
        st = copy.deepcopy(proto)
        st["range"] = [a, b]
        st["size"] = round(size * LATIN_RATIO, 3) if lat else float(size)
        styles.append(st)
    content["text"] = text
    content["styles"] = styles


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--size", type=float, default=20.0)
    p.add_argument("--box", type=float, default=0.86)
    p.add_argument("--terms-file", default="terms_vegan.txt")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    path = os.path.join(CAPCUT_ROOT, a.draft, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))
    room = room_units(draft["canvas_config"]["width"], a.box) / a.size
    by = {m["id"]: m for m in draft["materials"]["texts"]}
    terms = []
    if a.terms_file and os.path.exists(a.terms_file):
        terms = [ln.strip() for ln in open(a.terms_file, encoding="utf-8")
                 if ln.strip() and not ln.startswith("#")]
    cd = build_dict(terms)

    ti = max((len(t["segments"]), i) for i, t in enumerate(draft["tracks"])
             if t["type"] == "text" and t["segments"])[1]
    track = draft["tracks"][ti]
    segs = sorted(track["segments"], key=lambda s: s["target_timerange"]["start"])

    out, texts, split = [], [], 0
    for seg in segs:
        mat = by[seg["material_id"]]
        content = json.loads(mat["content"])
        text = content["text"]
        need = units(text)
        parts = [text]
        if need > room:
            toks = [t for t in tokenize(text, custom_dict=cd) if t]
            k = 2
            while k <= len(toks):
                cand = _balanced(toks, k)
                if max(units(c) for c in cand) <= room:
                    break
                k += 1
            parts = cand if k <= len(toks) else [text]
            split += 1

        tr = seg["target_timerange"]
        weights = [spoken_len(q) or 1.0 for q in parts]
        total = sum(weights)
        at = tr["start"]
        for i, (q, w) in enumerate(zip(parts, weights)):
            dur = (tr["start"] + tr["duration"] - at if i == len(parts) - 1
                   else int(tr["duration"] * w / total))
            s2 = copy.deepcopy(seg)
            s2["id"] = str(uuid.uuid4()).upper()
            m2 = copy.deepcopy(mat)
            m2["id"] = str(uuid.uuid4()).upper()
            c2 = json.loads(m2["content"])
            restyle(c2, q, a.size)
            m2["content"] = json.dumps(c2, ensure_ascii=False)
            m2["base_content"] = m2["content"]
            m2["font_size"] = float(a.size)
            m2["line_max_width"] = a.box
            m2["words"] = {"start_time": [0], "end_time": [int(dur / 1000)], "text": [q]}
            s2["material_id"] = m2["id"]
            s2["target_timerange"] = {"start": at, "duration": dur}
            texts.append(m2)
            out.append(s2)
            at += dur

    old = {s["material_id"] for s in segs}
    draft["materials"]["texts"] = [m for m in draft["materials"]["texts"]
                                   if m["id"] not in old] + texts
    for i, s in enumerate(out):
        s["render_index"] = 14000 + i
    track["segments"] = out

    print(f"ซับ {len(segs)} -> {len(out)} ใบ (ซอยเพิ่ม {split} ใบ) ขนาดเดียว {a.size}")
    print(f"  ละตินย่อเหลือ {round(a.size * LATIN_RATIO, 3)} เพื่อให้สูงเท่าไทย")

    worst, prev = 0.0, -1
    sizes = set()
    for s in out:
        c = json.loads({m["id"]: m for m in texts}[s["material_id"]]["content"])
        worst = max(worst, units(c["text"]) / room)
        sizes.update(round(st["size"], 3) for st in c["styles"])
        t = s["target_timerange"]
        assert t["duration"] > 0, "a caption lost all its time"
        assert t["start"] >= prev, "captions overlap"
        prev = t["start"] + t["duration"]
    print(f"  ใบที่แน่นสุดกิน {worst * 100:.0f}% ของกรอบ, ขนาดที่ใช้ทั้งหมด {sorted(sizes)}")
    assert worst <= 1.0 + 1e-9, "a caption still overflows"
    assert len(sizes) <= 2, "more than one Thai size is in use"

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
