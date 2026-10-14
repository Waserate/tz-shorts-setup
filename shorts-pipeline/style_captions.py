"""Give every caption a readable outline, and a size that fits without wrapping.

Two complaints, one pass:

* White text on white plates and bright kitchens disappeared. CapCut's own captions in the
  user's other projects solve this with a black stroke — the shape is cloned from one of
  those drafts rather than invented, and applied identically to every card so the look is
  the same for the whole clip.
* Some cards still wrapped. The width model already exists in `fit_caption_sizes`, but the
  fitter RE-SPLITS as well as resizes, and re-running it kept shaving the cards into one and
  two word fragments. This only ever changes the size, never the text, so the wording the
  user approved survives.

The Latin runs keep the smaller size the height matcher gave them: the whole caption is
scaled by one factor, so Thai and Latin stay the same height.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time


from config import CAPCUT_ROOT, BACKUP_DIR

# The captions render in CapCut's en.ttf — that is what the user's own Auto Caption stamped
# on every run, INCLUDING the Thai ones. `fit_caption_sizes.width_per_px` measures with
# NotoSansThai instead, and en.ttf sets Thai 39% wider, so the fitter kept certifying cards
# that then wrapped on screen ("Viral สนั่น Social" broke over two lines).
#
# PX_PER_UNIT is re-derived from that screenshot rather than guessed: the first line fitted
# at roughly 61% of the frame while the whole card did not, which brackets the constant to
# 5.08-7.45 and puts it at 5.6.
from config import FONT_DIR
CAPTION_FONT = os.path.join(FONT_DIR, "en.ttf")
PX_PER_UNIT = 5.6
FIT_MARGIN = 0.97
REF = 200
_FONT = None


def width_per_px(text: str) -> float:
    """Width of the text when the font it actually renders in is 1 px tall."""
    global _FONT
    if _FONT is None:
        from PIL import ImageFont
        _FONT = ImageFont.truetype(CAPTION_FONT, REF)
    return _FONT.getlength(text) / REF


def room_units(canvas_w: int, line_max_width: float) -> float:
    """How much `width_per_px * font_size` fits on one line."""
    return canvas_w * line_max_width / PX_PER_UNIT * FIT_MARGIN


def stroke_from(donor_name: str):
    """Borrow a real caption outline instead of guessing the schema."""
    d = json.load(open(os.path.join(CAPCUT_ROOT, donor_name, "draft_content.json"),
                       encoding="utf-8"))
    for m in d["materials"].get("texts", []) or []:
        try:
            c = json.loads(m["content"])
        except Exception:
            continue
        for st in c.get("styles", []) or []:
            if st.get("strokes"):
                return (json.loads(json.dumps(st["strokes"])), m.get("border_color", ""),
                        m.get("border_width"))
    raise SystemExit(f"no outlined caption in donor {donor_name}")


def line_widths(text: str, styles: list, size_of) -> float:
    """Widest line, honouring the per-run sizes (Latin runs are set smaller)."""
    widest = 0.0
    for line in text.split("\n"):
        pass
    # ranges are indices into the whole text; measure line by line using them
    start = 0
    for line in text.split("\n"):
        end = start + len(line)
        w = 0.0
        for st in styles:
            a, b = st["range"]
            lo, hi = max(a, start), min(b, end)
            if hi > lo:
                w += width_per_px(text[lo:hi]) * size_of(st)
        widest = max(widest, w)
        start = end + 1
    return widest


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft", required=True)
    p.add_argument("--stroke-donor", default="0208")
    p.add_argument("--box", type=float, default=0.86)
    p.add_argument("--equal-runs", action="store_true",
                   help="give Latin the same size as the Thai instead of matching heights")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    path = os.path.join(CAPCUT_ROOT, a.draft, "draft_content.json")
    draft = json.load(open(path, encoding="utf-8"))
    strokes, border_color, border_width = stroke_from(a.stroke_donor)
    print(f"outline from draft {a.stroke_donor}: width {border_width}, {border_color}")

    # the caption track is the busy one; the title card is its own track and keeps the size
    # the user asked for, so it stays bigger than the captions
    cap_track = max((len(t["segments"]), i) for i, t in enumerate(draft["tracks"])
                    if t["type"] == "text" and t["segments"])[1]
    room = room_units(draft["canvas_config"]["width"], a.box)
    by = {m["id"]: m for m in draft["materials"]["texts"]}
    shrunk, outlined, worst = 0, 0, 0.0

    for ti, tr in enumerate(draft["tracks"]):
        if tr["type"] != "text":
            continue
        for seg in tr["segments"]:
            mat = by[seg["material_id"]]
            content = json.loads(mat["content"])
            text, styles = content["text"], content.get("styles", [])
            if not styles:
                continue

            if ti == cap_track:
                if a.equal_runs:
                    # The height matcher shrank Latin so cap height equalled Thai body
                    # height. The user wants one size for the whole line instead, anchored
                    # to the Thai, so every run goes back to the card's Thai size.
                    one = max(st["size"] for st in styles)
                    for st in styles:
                        st["size"] = one
                    mat["font_size"] = float(one)
                width = line_widths(text, styles, lambda st: st["size"])
                if width > room:
                    k = room / width
                    for st in styles:
                        st["size"] = round(st["size"] * k, 3)
                    mat["font_size"] = float(max(st["size"] for st in styles))
                    shrunk += 1
                    width = room
                worst = max(worst, width / room)
                mat["line_max_width"] = a.box

            for st in styles:
                st["strokes"] = json.loads(json.dumps(strokes))
            mat["border_color"] = border_color
            if border_width is not None:
                mat["border_width"] = border_width
            mat["content"] = json.dumps(content, ensure_ascii=False)
            mat["base_content"] = mat["content"]
            outlined += 1

    print(f"outlined {outlined} cards; shrank {shrunk} that would have wrapped")
    print(f"  widest line now fills {worst * 100:.0f}% of the {a.box} box")
    assert worst <= 1.0 + 1e-9, "a caption still overflows the box"

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
