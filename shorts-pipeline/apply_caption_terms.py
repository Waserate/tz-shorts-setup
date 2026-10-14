"""Rewrite caption wording: Thai-script English back into English, spelled-out numbers into
numerals.

The auto-caption writes loanwords and names phonetically in Thai (วีแกน, เครเตอร์,
มีเดียมแรนด์) and spells numbers out (สิบสี่ปี). On screen the user wants the English form
and real numerals.

Runs on the 111-card state, i.e. AFTER the 3-5 word split. That means a term can be
straddling a card boundary and no single-card replacement can see it — `_pairs` handles
those explicitly, rewriting two consecutive cards together. Everything else is a plain
longest-first replacement.

Changing the text changes its width, so `fit_caption_sizes` must be re-run afterwards or
the no-wrap guarantee no longer holds.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

_THAI = r"฀-๿"
# Thai runs words together, but a Latin word or a numeral jammed against Thai letters is
# unreadable — 'Veganสายแข็ง14ปี'. One space at each script boundary, never two.
_SPACE_RULES = (
    (re.compile(f"([{_THAI}])([A-Za-z0-9])"), r"\1 \2"),
    (re.compile(f"([A-Za-z0-9])([{_THAI}])"), r"\1 \2"),
    # Latin-to-Latin: re-splitting joins tokens with "" and welds two English words
    # together ('MediumRare', 'VeganTeacher'). A lowercase-then-uppercase boundary is the
    # signature. Only safe because no caption here uses genuine CamelCase as a name.
    (re.compile(r"([a-z])([A-Z])"), r"\1 \2"),
)


def space_scripts(text):
    for pat, rep in _SPACE_RULES:
        text = pat.sub(rep, text)
    return re.sub(r" {2,}", " ", text).strip()


def load_rules(path):
    raw = json.load(open(path, encoding="utf-8"))
    pairs = raw.get("_pairs", [])
    simple = {k: v for k, v in raw.items() if not k.startswith("_")}
    # longest first, so 'วีแก้นทีเชอร์' wins over 'วีแก้น'
    return sorted(simple.items(), key=lambda kv: -len(kv[0])), pairs


def apply_to_texts(texts, rules, pairs):
    out = list(texts)
    changes = []

    for a_from, a_to, b_from, b_to in pairs:
        for i in range(len(out) - 1):
            if out[i] == a_from and out[i + 1] == b_from:
                changes.append((i, out[i], a_to))
                changes.append((i + 1, out[i + 1], b_to))
                out[i], out[i + 1] = space_scripts(a_to), space_scripts(b_to)

    for i, t in enumerate(out):
        new = t
        for src, dst in rules:
            if src in new:
                new = new.replace(src, dst)
        new = space_scripts(new)
        if new != t:
            changes.append((i, t, new))
            out[i] = new
    return out, changes


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--draft-file", required=True, help="draft_content.json to read")
    p.add_argument("--rules", required=True)
    p.add_argument("--out", required=True, help="where to write the edited draft json")
    a = p.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    draft = json.load(open(a.draft_file, encoding="utf-8"))
    by = {m["id"]: m for m in draft["materials"]["texts"]}
    cands = [(len(t["segments"]), i) for i, t in enumerate(draft["tracks"])
             if t["type"] == "text" and t["segments"]]
    idx = max(cands)[1]
    segs = sorted(draft["tracks"][idx]["segments"],
                  key=lambda s: s["target_timerange"]["start"])
    texts = [json.loads(by[s["material_id"]]["content"])["text"] for s in segs]

    rules, pairs = load_rules(a.rules)
    new_texts, changes = apply_to_texts(texts, rules, pairs)

    for s, txt in zip(segs, new_texts):
        m = by[s["material_id"]]
        content = json.loads(m["content"])
        content["text"] = txt
        for st in content.get("styles", []):
            st["range"] = [0, len(txt)]
        m["content"] = json.dumps(content, ensure_ascii=False)
        m["base_content"] = m["content"]

    seen = {}
    for i, old, new in changes:
        seen[i] = (seen.get(i, (old, None))[0], new)
    print(f"{len(seen)} of {len(texts)} captions changed")
    for i in sorted(seen):
        old, new = seen[i]
        print(f"  {i:3d}  {old}")
        print(f"       -> {new}")

    json.dump(draft, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
