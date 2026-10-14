"""Golden regression tests for the Thai subtitle chunker.

Every case here was corrected BY THE USER (a native speaker) against my output.
Tuning the cost function keeps re-breaking earlier fixes, so these are locked down:
run this after ANY change to thai_subtitle.py.

    venv\\Scripts\\python.exe test_chunker.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from thai_subtitle import chunk_text, build_dict, assert_cards_sane, HARD_MAX, OPENERS

DICT = build_dict(["เทพศิรินทร์", "นนทบุรี", "กราดยิง", "แพะรับบาป", "ชาวเกมเมอร์",
                   "โหนกระแส", "หนุ่มกรรชัย", "อาวุธปืน", "สุขภาพจิต"])

# (source, expected cards) — expected values are the user's own corrections
GOLDEN = [
    (
        "เอาอีกแล้วสื่อใหญ่หลายเจ้าโยนบาปให้เกมหลังเกิดเหตุการณ์กราดยิงในโรงเรียน"
        "ทั้งที่หมอยืนยันว่ามันไม่ใช่สาเหตุหลักสักหน่อย",
        ["เอาอีกแล้วสื่อใหญ่", "หลายเจ้าโยนบาปให้เกม", "หลังเกิดเหตุการณ์",
         "กราดยิงในโรงเรียน", "ทั้งที่หมอยืนยันว่า", "มันไม่ใช่สาเหตุหลักสักหน่อย"],
    ),
    (
        "แต่ว่าสิ่งที่ทำให้ชาวเกมเมอร์อย่างพวกเราเนี่ยอึ้งไปตามๆกัน",
        ["แต่ว่าสิ่งที่ทำให้", "ชาวเกมเมอร์อย่างพวกเราเนี่ย", "อึ้งไปตามๆกัน"],
    ),
]

# things that must never happen, whatever the tuning
MUST_NOT_SPLIT = [
    "โยนบาป", "สื่อใหญ่", "ให้เกม", "ชาวเกมเมอร์", "ทางครอบครัว", "บ้านเรา",
    "หลายคน", "แพะรับบาป", "เทพศิรินทร์",
    # found by reviewing all 32 narration lines
    "ไม่มีใคร", "อาวุธปืน", "จริงจริง", "ไม่ว่าจะ", "ล้านคน", "โหนกระแส",
]

SENTENCES = [
    "ทำไมผู้ใหญ่ในบ้านเราถึงชอบโยนความผิดให้เกมเป็นแพะรับบาปตลอดเวลา",
    "แน่นอนว่าหลายคนเนี่ยน่าจะเห็นเหตุการณ์สะเทือนขวัญเมื่อไม่นานมานี้",
    "และพวกเราทุกคนเนี่ยก็เสียใจกับทางครอบครัวของผู้สูญเสียทั้งหมด",
    "จากข่าวเหตุการณ์กราดยิงในโรงเรียนเทพศิรินทร์นนทบุรีล่าสุด",
    "แน่นอนว่ามันเป็นความสูญเสียที่ไม่มีใครอยากให้เกิดขึ้น",
    "สังคมไทยเนี่ยก็ไม่เคยเดินหน้าไปไหนเลย",
    "แล้วก็กลายเข้าถึงอาวุธปืนไปซะอย่างนั้น",
    "เกมน่ะไม่ใช่ปัจจัยหลักของพฤติกรรมความรุนแรงแต่ว่าสาเหตุที่แท้จริงน่ะ"
    "มันมาจากปัญหาที่สะสมไม่ว่าจะเป็นสภาพจิตใจ",
    "ทั้งที่ในรายการโหนกระแสพี่หนุ่มกรรชัยและจิตแพทย์ผู้เชี่ยวชาญก็ออกมาบอก",
]

fails = []

for src, want in GOLDEN:
    cards = chunk_text(src, custom_dict=DICT)
    assert_cards_sane(cards, src)
    got = [c.text for c in cards]
    if got != want:
        fails.append(f"GOLDEN mismatch\n  src : {src}\n  want: {' | '.join(want)}\n"
                     f"  got : {' | '.join(got)}")

for src in [s for s, _ in GOLDEN] + SENTENCES:
    cards = chunk_text(src, custom_dict=DICT)
    assert_cards_sane(cards, src)
    joined = " | ".join(c.text for c in cards)
    for phrase in MUST_NOT_SPLIT:
        if phrase in src.replace(" ", "") and phrase not in joined.replace(" ", ""):
            fails.append(f"SPLIT a phrase that must stay whole: {phrase!r}\n"
                         f"  src: {src}\n  got: {joined}")
    for c in cards[:-1]:
        # regression guard: when break-cost replaced the edge-word checks, the
        # "don't END on a phrase opener" half of the rule went missing and produced
        # cards like "สังคมไทยเนี่ยก็ |" and "ผู้หลักผู้ใหญ่หรือ |".
        if c.words[-1] in OPENERS:
            fails.append(f"card ends on a phrase opener {c.words[-1]!r}: {c.text!r}\n"
                         f"  src: {src}")
    for c in cards:
        if len(c.words) > HARD_MAX:
            fails.append(f"card over HARD_MAX: {c!r}")

if fails:
    print(f"FAILED ({len(fails)})\n")
    for f in fails:
        print(f + "\n")
    sys.exit(1)
print(f"PASS  {len(GOLDEN)} golden cases + "
      f"{len(MUST_NOT_SPLIT)} unbreakable phrases across {len(GOLDEN)+len(SENTENCES)} sentences")
