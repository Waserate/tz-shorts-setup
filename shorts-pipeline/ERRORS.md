---
title: "Shorts Pipeline — Failure log"
stage: project
topic: shorts-pipeline
created: 2026-08-13
updated: 2026-08-13
tags: [stage/project, topic/video-automation]
---

# ERRORS.md — what didn't work, what did, why

Logged per the workflow rule: anything that took >2 attempts.

---

## E1 — `pythainlp[compact]` will not install on Windows
**Didn't work:** `pip install "pythainlp[compact]"` → `RuntimeError: Please install pkg-config
… or set the ICU_VERSION` while building **pyicu**.
**Worked:** `pip install pythainlp nlpo3` separately.
**Why:** the `compact` extra pulls `pyicu`, which compiles against a system ICU that Windows
does not ship. `nlpo3` (the part actually wanted — the fast Rust tokenizer) has prebuilt
Windows wheels and does not need ICU.
**Next time:** never take the `[compact]` extra on Windows; name the sub-packages.

---

## E2 — CUDA invisible to CTranslate2 despite a working driver
**Didn't work:** `WhisperModel(..., device="cuda")` → `RuntimeError: Library cublas64_12.dll
is not found or cannot be loaded`, even though `nvidia-smi` was fine and
`ctranslate2.get_cuda_device_count()` returned 1.
**Worked:** `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`, then a `cuda_setup.py` that calls
`os.add_dll_directory()` on every `site-packages/nvidia/*/bin`, imported **before** ctranslate2.
**Why:** the pip nvidia wheels drop DLLs inside site-packages, which is not on the Windows DLL
search path. Python 3.8+ also ignores `PATH` for extension-module DLL resolution.
**Next time:** on Windows, pip-installed CUDA libs always need `add_dll_directory`.

---

## E3 — Mouse clicks silently missed the CapCut window
**Didn't work:** `SetCursorPos(2223, 800)` then `mouse_event` — nothing happened, twice.
Suspected the app was blocking synthetic input.
**Worked:** reading the cursor back showed it landed at **1919,800** — clamped. The virtual
desktop starts at **X = −1920** (left monitor), so screenshot pixel X must have −1920 added
before it is a real screen coord. `click.ps1` now converts and warns if the cursor lands
somewhere else.
**Why:** two monitors with the primary on the right → negative virtual-screen origin.
Nothing to do with DPI (verified 96 dpi) or with the app (it is a Qt app, accepts synthetic input).
**Next time:** always verify with `GetCursorPos` after `SetCursorPos`; never assume image
coords equal screen coords on a multi-monitor box.

---

## E4 — Thonburian hallucinated a slot-machine advert
**Didn't work:** default decode → the transcript degenerated into
`โรม่าทุกวันอังคาร 19.05 น` repeated 10×, and `สล็อตโรม่า` appeared out of nowhere. Only 2
segments came back for 60 s of audio.
**Worked:** `condition_on_previous_text=False` + `repetition_penalty=1.15` +
`no_repeat_ngram_size=4` + temperature fallback list + `compression_ratio_threshold=2.2`.
Loop score 0.24 → **0.00**. Batching to 16 also removed it entirely and was 21× faster.
**Why:** Whisper conditions each window on its own previous output; once it emits a
degenerate span it feeds itself. The source audio contains repeated mic-test counting
("หนึ่ง สอง สาม") and retakes, which is exactly the input that triggers it.
**Next time:** on any long-form Thai transcription, turn conditioning off by default and
measure a repetition score, don't eyeball it.

---

## E5 — Chunker metrics looked great while the output was broken
**Didn't work:** "98 % of cards are 3-5 words" — but the cards read
`แน่นอนว่าหลาย | คนเนี่ย…` and `ในโรงเรียนเทพสิริ | นทร์โนภพ` (a school name cut in half).
**Worked:** bind adjacent tokens into unbreakable *units* first (quantifier+classifier,
negator, prefix, reduplication, out-of-dictionary runs = fragmented proper nouns), then run the
DP over units. Plus a per-video custom dictionary.
**Why:** the cost function only scored card size and a hand-written connector list. It had no
concept of which adjacent words belong together, so it split anything to hit a size target.
**Next time:** a size metric proves nothing about readability. Read the actual output.

---

## E6 — Hand-written word lists can never cover Thai
**Didn't work:** growing `NO_END` / `NO_START` word lists. Fixing `ให้` broke `สื่อใหญ่`;
fixing that broke `โยนบาป`.
**Worked:** switch from "this word may not sit at a card edge" to **"what does it cost to cut
between these two words"**, scored from the **POS tags on both sides** (`pos_tag(engine=
"perceptron", corpus="orchid_ud")`). ADJ binds backward, ADP/DET bind forward, VERB+NOUN is an
object, CCONJ/SCONJ are good break points.
**Why:** an edge rule only sees one side of the cut, so a word banned from a card end just
jumps to the head of the next card and breaks something there instead.
**Next time:** model the boundary, not the token.

---

## E7 — 🟥 Half a rule went missing during the refactor
**Didn't work:** after moving to break-cost, cards appeared ending on `ก็` and `หรือ`
(`สังคมไทยเนี่ยก็ |`). The old `NO_END` check had been deleted and only the
"breaking *before* an opener is good" half was reimplemented.
**Worked:** add the symmetric `if lw in OPENERS: return 12.0`, and a regression test asserting
no card ends on a phrase opener.
**Why:** the refactor moved two rules into one function and silently dropped one direction.
**Next time:** when replacing a rule set, enumerate the old rules and tick each one off.

---

## E8 — Fixing one Thai phrase kept breaking a previously-fixed one
**Didn't work:** raising `MAX_WORDS` 5→6 to satisfy a user correction re-broke
`ทางครอบครัว`, which had been correct one iteration earlier. This happened three times.
**Worked:** `test_chunker.py` — the user's own corrections as golden cases plus a list of
phrases that must never split. Run after every change.
**Why:** the DP is global, so any weight change reshuffles every boundary in the sentence.
There is no such thing as a local tweak here.
**Next time:** the moment a native speaker corrects an output, it becomes a test, immediately.

---

## E9 — Bind rules chained into one unbreakable blob
**Didn't work:** after adding reduplication + quantifier + prefix binds, a card came out
**8 words** (`มีเป็นล้านล้านคนหลายคนเนี่ย`) — each rule fired in turn and fused a whole clause.
**Worked:** `MAX_UNIT_WORDS = 4` cap in `merge_units`.
**Why:** the rules are pairwise and applied greedily left-to-right, so they compose transitively.
**Next time:** any greedy pairwise merge needs a size cap.

---

## E10 — Subtitle card sat on screen for 11 seconds (three layers)
**Didn't work:** cards spanning a pause. Fixed in three rounds:
1. **11 s** — chunking was purely textual and never looked at time.
   → split the word stream wherever the gap between words exceeds 0.55 s.
2. **5.2 s** — still wrong: Whisper swallows silence *into a piece*
   (`('้', 5.44, 11.28)` — a single tone mark holding 5.84 s), so no between-word gap exists.
   → clamp each piece to `0.5 s × len(text)`, which makes the silence reappear as a gap.
3. **3.9 s** — still wrong: the pause was *inside one word* (`ให้` = pieces `ให` + `้`
   with 2 s between them), invisible to a word-to-word check.
   → clamp each word to `0.25 s × len(word) + 0.30 s`.
**Result:** 17 cards, 0.52–3.23 s, none spanning a pause.
**Why:** Whisper's Thai "word" timestamps are per-character, and its DTW parks silence
wherever it likes. Never trust a reported span; bound it by what speech physically takes.
**Next time:** validate durations against physical plausibility, and assert it
(`MAX_CARD_DUR`) so it crashes rather than shipping an 11-second subtitle.

---

## E11 — Batched ASR benchmarked clean, then OOM'd on the first real file
**Didn't work:** `batch_size=16` (the benchmark winner) and then `8` on the full 232 s
`kids Gun.wav` → `RuntimeError: CUDA failed with error out of memory`, at the very first
`model.encode`, with 3.8 GB free on the card.
**Worked:** `--batch 4`. 1420 pieces, 185.7 s, RTF 0.80x, peak ~3.9 GB of the 4 GB card.
**Why:** `BatchedInferencePipeline` batches VAD chunks, and the 60 s benchmark clip only
produced ~2 chunks — so `batch_size=16` was never actually reached and the benchmark
measured a batch of 2. A 232 s file produces enough chunks to fill the batch for real, and
large-v3's encoder attention is float32 even under `compute_type="int8"`: ~180 MB per
sample per layer. The "21× faster" figure in the benchmark is therefore not a batch-16
number and does not transfer to full-length files.
**Next time:** never tune a batch size on a clip too short to fill the batch. Benchmark on
input at least as long as production input, and record peak VRAM, not just RTF.

---

## E12 — Thai diacritics bought a word extra time budget (E10, fourth layer)
**Didn't work:** the E10 word clamp `0.25 * len(w) + 0.30` let `ทั้งที่` claim **2.05 s**
because Python counts it as 7 code points. A card went to **4.31 s** across a 2.8 s pause
and `assert_timing_sane` crashed the first full run — the invariant did its job.
**Worked:** `spoken_len()` — count only characters that cost time to say, excluding
`ั`, U+0E34–U+0E3A and U+0E47–U+0E4E. `ทั้งที่` is 3 spoken characters → 1.05 s, card 3.31 s.
Applied to both the per-piece budget in `CharClock` and the per-word clamp.
**Why:** tone marks and above/below vowels are written on top of the preceding consonant,
so a code-point count overstates a word's spoken length by up to 2×, and the clamp that was
supposed to expose the silence let the silence back in.
**Next time:** any "characters × seconds" heuristic on Thai must count **spoken**
characters. `len()` is the wrong unit for a Thai duration.

---

## E13 — 🟥 The fix for E10 was quietly deleting 18.4 s of subtitles
**Symptom the user reported:** "ตรงบ้างไม่ตรงบ้าง แล้วอันที่หายไป" — subtitles vanishing while
they could still hear talking.

**Wrong hypothesis, tested and killed first (~15 min of GPU):** that the ASR was dropping
speech, because E4's anti-loop settings suppress repetition and this take is full of
retakes. Four full-file variants:

| variant | pieces | speech covered | loop score |
|---|---|---|---|
| A current | 1420 | 122.7 s (92 %) | 0.109 |
| B `compression_ratio_threshold=None` | 1420 | 122.7 s (92 %) | 0.109 |
| C `no_repeat_ngram=0`, `repetition_penalty=1.0` | 1486 | 118.1 s (88 %) | 0.173 |
| D both off | 1486 | 118.1 s (88 %) | 0.173 |

`compression_ratio_threshold` changes **nothing** here, and turning the anti-loop off makes
coverage *worse* while the loop score gets worse too. **The current decode settings are
already the best of the four — do not re-litigate this.** Also learned: you cannot test
`vad_filter=False` on the batched path at all — `BatchedInferencePipeline` raises
`RuntimeError: No clip timestamps found. Set 'vad_filter' to True…`.

**What was actually wrong:** measure coverage at every link and the culprit is obvious.

| link | speech covered |
|---|---|
| raw Whisper pieces | 122.7 s (92 %) |
| after our clamps | 104.3 s (78 %) ← **18.4 s lost here** |
| final cards | 106.6 s (80 %) |

E10's clamp (`0.5 s per spoken character`) assumes a long piece means "Whisper swallowed
silence". That is only sometimes true. This file has 19 pieces longer than 1 s, totalling
40.8 s, and each is **55–71 % real speech** — e.g. `('ช', 139.82, 145.54)`, 5.72 s at 71 %
speech, truncated to 0.5 s. A character count cannot distinguish "long because silent"
from "long because they kept talking".

**Worked:** `speech_mask.py` — an RMS speech mask off the waveform (20 ms frames,
threshold relative to the file's own floor/loud percentiles, short holes closed so a stop
consonant is not a pause, edges padded because onsets ramp). `CharClock` now advances
characters through **voiced time only**, and a word ends at the first real pause inside its
span. The character-count clamp survives only as the no-audio fallback.

| metric | before | after |
|---|---|---|
| speech covered by cards | 106.6 s (80 %) | **114.7 s (86 %)** |
| speech lost in gaps | 17.5 s | **8.7 s** |
| cards firing before the words | 16 (max 0.97 s) | **11 (max 0.46 s)** |
| cards >0.30 s early | 9 | **1** |
| cards still up >0.5 s after speech | 5 | **0** |

**Why the mistake happened:** E10 was validated on "no card is longer than 4 s", which the
clamp satisfies perfectly — by throwing away content. A one-sided metric certified a fix
that broke the other side.

**Next time:** when a fix bounds something, measure the quantity it can destroy in
exchange. Coverage and duration had to be measured together; either alone passes a bad fix.
And when output goes missing, **measure every link in the chain before blaming the model** —
the two cheap coverage numbers would have pointed at our own code in one minute.

---

## E14 — 🟥 Trusting the START of a Whisper piece (subtitles arriving a second early)
**Symptom the user reported:** a card appearing at `0:38.08` that should appear at `0:39.07`.

**The mechanism, from the raw pieces:**
```
70.69-71.11  '1',' 2',' 3'      <- mic-test counting
71.19-73.17  ' จ'   (1.98 s!)   <- ONE consonant holding two seconds
73.17-73.29  'าก'  (0.12 s)     <- the word actually starts here
```
Whisper dumped the audio *before* the character into the character's span. The energy mask
said (correctly) that 71.6-72.98 is voiced — it is, it is the tail of the counting — so the
waveform-driven clock happily placed `จ` at the front of that speech, ~0.9 s early. Silero
VAD agreed there was speech there, so this was never a breath-vs-word problem: it is a
**whose** speech problem.

**Worked:** a piece longer than `0.5 s × spoken characters` has an untrustworthy START but a
trustworthy END — the next piece pins it. So the characters are anchored to the voiced run
that the piece's END falls in (`SpeechMask.run_start_at`). `จ` moves to 73.14. Three
supporting changes fell out of it:
- `GAP_SPLIT` 0.55 → **0.35 s**, matched to the dead-air threshold: a card must never be
  built across a pause that the cut is going to remove anyway.
- a card may not still be up once the talking stopped — bounded by
  `last_voiced_before(end)`, asserted by `assert_no_overrun`. Bounding by the end of a
  single voiced *run* was tried first and was too strict: a sentence contains 0.2 s pauses
  and cards legitimately ride over them, so that version produced 11 unreadable 0.15 s
  flashes.
- a card containing **no** speech at all is dropped. This is where Whisper's stray tokens
  land — a lone `1` parked in a 3 s silence, a bare `ก็` in a pause — and no anchoring rule
  can place text nobody said.

| metric | before | after |
|---|---|---|
| cards firing before the words, >0.30 s | 9 | **1** |
| worst early | 2.97 s | **0.40 s** |
| overhang after the speaking stops | up to 0.15 s | **0.00 s** |
| cards under 0.45 s | 3 | **1** |
| median card | 0.96 s | **1.32 s** |

Verified in CapCut: `00:00:38:21` blank, `00:00:39:24` shows `จากข่าวเหตุการณ์` — the user
asked for 0:39.07 and the card starts at 0:39.05, two frames out.

**Next time:** a timestamp from a model has two ends and they are not equally reliable.
Ask which end is pinned by independent evidence before building on it. And when the user
says a subtitle is early, do not measure "is there sound here" — measure "is this the sound
those words came from".

---

## E15 — Repeat detection compared the wrong unit, and audio could not rescue it
**Didn't work (v1):** compare whole **utterances** with `partial_ratio`. Found 4 repeats;
the user watched the result and said repeats were still obviously there. They were right.
Two structural reasons, both fatal:
- a retake does not respect utterance boundaries — the flub is the *tail* of one breath
  group and the retake is the *head* of the next, so the matching part is a small fraction
  of each string and the score collapses;
- three attempts can land **inside one utterance** (`คือเหตุการณ์จริงๆนี้เนี่ย` +
  `คือเหตุกาลในนี้เนี๊ย` + `คือการนี้เเนี่ว`), where nothing can ever compare them.

**Didn't work (v2):** audio self-similarity, on the theory that the same person saying the
same line in the same room must look alike even when the ASR spells it three ways.
Log-mel slices, per-frame normalised, cosine under a ±120 ms shift search:
positives **0.360-0.750**, negatives **0.491-0.675** — almost total overlap. The measure is
dominated by speaker and room, which are identical everywhere in the file. Would need DTW
over phoneme-level embeddings; not worth it for this.

**Worked:** compare a fixed **18-character window** from each card's start, over all card
pairs within 45 s. Calibrated against an answer key made by reading all 97 cards by hand,
then swept over every pair in the file: at threshold **60 there are zero false positives**,
and it catches `เกมไม่ใช่ปัจจัยหลัก…` (83) and `คือเหตุกาล…` (61) that the utterance
version missed. Repeats cut went **4 → 12**, total cut **30 % → 40 %**.

Also added: mic-test junk removal by pattern (`หนึ่ง สอง สาม` comes back as `นี่สองซ่าม` /
`นี่สิงห์สองซั่ม` / `นี่สองทราม` / `123`), and a `MIN_CARD_AFTER_CUT` floor because a card
whose audio is mostly cut away leaves an unreadable one-frame sliver.

🟥 **Known ceiling, do not pretend otherwise.** Text cannot see a repeat when the ASR heard
different words: `เอาอีกแล้วสังคมโยนบาป` vs its retake `เสือใหญ่หลายจ้าง…` (really
`สื่อใหญ่หลายเจ้า`) scores **38.9**, below several genuine non-repeats. Anything in the
48-59 band is **reported, never cut** — deleting real content is worse than leaving a
repeat — and `--start-at` exists so the user can kill a false start the text cannot see.

**Next time:** pick the comparison unit from how the phenomenon actually behaves, not from
whatever unit the data is already grouped into. And before adding a heavier signal
(audio, ML), test it against a labelled key first — this one looked obviously right and
measured useless.

---

## E16 — 🟥 The anti-repeat settings created 27 s of silent-but-talking video
**Symptom the user reported:** timeline 1:49-2:12 of the Vegan clip has picture and a
waveform and no subtitle at all. Then: "มันควรจะ Gen มาให้หมดเลยไหมทุกคำ".

**Mechanism:** `no_repeat_ngram_size=4` + `repetition_penalty` (E4's fix for the
hallucination loop) forbid the model from emitting an n-gram it has already produced. Where
the speaker RETAKES a line, that is exactly what they are doing, so the model emitted
**nothing** — 52 pieces of `นี่สองซ่ำ ๆ แหม` for 33 s of clearly voiced audio. Adding
`hotwords` made it worse: locking the vocabulary made the repeated wording even easier to
suppress. The failure then cascaded: no text → the repeat cleaner cannot see a repeat →
the audio is not cut either. Kept, uncaptioned, and unremovable.

**Worked:** `fill_gaps.py` — a second pass over exactly the spans that are voiced and
carry no card, decoded one span at a time with `no_repeat_ngram_size=0`,
`repetition_penalty=1.0` and no compression-ratio cutoff. Those settings are unsafe over a
whole file and safe over a 2 s span: a loop cannot run away, and any span whose own output
is still degenerate is rejected by a 6-gram repetition score and **marked dead for the cut
planner** instead. That is what closes the hole — audio is either captioned or cut, and the
third state stops existing. `build_draft` prints any span that still breaks the rule.

| | before | after |
|---|---|---|
| uncaptioned speech in the finished edit | **27.0 s** | **3.3 s** |
| repeat takes cut | 3 | **9** |
| total cut | 27 % | **36 %** |

**Two bugs found while building it, both caught by existing guards:**
- `for a, b in left[:8]` inside `build()` rebound `b`, which was the `Builder` —
  `AttributeError: 'float' object has no attribute 'clone_segment'`. Single-letter loop
  variables in a long function are how this happens; the loop vars are named `lo_s, hi_s`
  now.
- Running fill twice re-decoded spans an earlier run had already filled and **stacked** the
  new pieces on the old, producing overlapping cards — `assert_timing_sane` crashed rather
  than shipping it. `fill` now drops existing pieces inside any span it re-decodes, so it
  is idempotent. The pieces cache had already been written by then; it was rebuilt from the
  pass-1 copy, which is why that copy is worth keeping.

**Next time:** when a guard suppresses output, ask what it does on input that legitimately
looks like the thing being suppressed. And any "top up the gaps" pass must be idempotent
before it is ever run twice.

## E17 — `resplit_captions.py` เถียงว่าซับทับกัน ทั้งที่ชิ้นที่คำนวณไม่ทับ

**อาการ:** `AssertionError: overlapping captions at 11.39s` ทุกครั้ง แก้ `split_caption()` ไป 3 รอบก็ยังขึ้นเลขเดิมเป๊ะ

**สิ่งที่ไม่ได้ผล**
1. เดาว่ากติกา "การ์ดขั้นต่ำ 0.35 วิ" ดันปลายการ์ดล้ำการ์ดถัดไป → ใส่เพดานยืมเวลา
2. เดาว่าย่อหน้าที่ยาวถูกซอยหลายสิบชิ้นจนบังคับขั้นต่ำไม่พอที่ → ปิดการบังคับเมื่อที่ไม่พอ

ทั้งสองข้อเป็นบั๊กจริงและควรแก้ แต่ไม่ใช่สาเหตุของ assertion

**สิ่งที่ได้ผล:** พิมพ์ชิ้นที่คำนวณได้ออกมาดูจริง แล้วพบว่า **ไม่มีชิ้นไหนทับกันเลย** — ปัญหาจึงไม่ได้อยู่ที่การซอย แต่อยู่ที่ตอนแปลงเป็นไมโครวินาที

**กลไก:** `rebuild_track` ปัด start กับ duration แยกกัน
`int(round(cs*US))` + `int(round((ce-cs)*US))` มีสิทธิ์มากกว่า `int(round(ce*US))` อยู่ 1 µs
ใบถัดไปเริ่มที่ `round(ce*US)` จึง "เริ่มก่อนใบก่อนหน้าจบ" 1 µs → assert ยิง
แก้โดยปัดเป็นจำนวนเต็มก่อนแล้วค่อยลบ: `cs_us, ce_us = round(...)` → `duration = ce_us - cs_us`

**บทเรียนคราวหน้า:** assert ที่ให้เลขเดิมเป๊ะทุกครั้งหลังแก้ = ยังไม่ได้แตะสาเหตุจริง
หยุดเดาแล้ว **พิมพ์ค่ากลางออกมาดู** ก่อนแก้รอบที่สาม
และถ้าตรวจด้วยทศนิยมแต่เก็บเป็นจำนวนเต็ม ให้ตรวจในหน่วยจำนวนเต็มเสมอ

## E18 — ครึ่งบนจอเป็นสีดำ เพราะค่าแบ่งจอค้างจากดราฟรุ่นก่อน

**อาการ:** ผู้ใช้สร้างคัตใหม่โดยต่อยอดจากดราฟเก่าที่เคยจัดแบ่งบนล่างไว้
main 13 จาก 25 ชิ้นจึงยังถูก crop เหลือกลางภาพ 50% และดันลงครึ่งล่าง (`transform.y = -0.5`)
แต่ B-roll รอบใหม่เป็นเต็มจอทั้งหมด → ครึ่งบนไม่มีอะไรวาง เลยเป็นสีดำ

**กลไก:** เลย์เอาต์แบ่งจอเป็นของ **คู่** เสมอ (main ครึ่งล่าง + B-roll ครึ่งบน)
แต่เก็บอยู่คนละแทร็ก แก้ฝั่งเดียวเมื่อไหร่ก็พัง และไม่มีอะไรเตือน

**วิธีแก้:** `fix_layout.py` ล้าง main กลับเป็นเต็มจอก่อนเสมอ แล้วค่อยจับคู่ใหม่จากแผน B-roll
พร้อม invariant ที่ assert ว่า main ชิ้นไหนอยู่ครึ่งล่างต้องมี B-roll ครึ่งบนคลุมช่วงนั้น
(หนึ่งหน้าต่างคลุม main ได้หลายชิ้น จึงต้องเช็ค "คลุม" ไม่ใช่ "จำนวนเท่ากัน" —
ตอนแรกผมเช็คด้วยจำนวนแล้วได้ธงเตือนปลอม)

**บทเรียนคราวหน้า:** ค่าที่ต้องตรงกันข้ามแทร็ก ให้ assert ความสัมพันธ์ ไม่ใช่จำนวน
และก่อนวาง B-roll รอบใหม่ ต้องล้าง framing เดิมทุกครั้ง

## E19 — ปัดเศษไมโครวินาทีในตัวซอยภาพ (ญาติของ E17)

`reframe_main_for_splits` ปัด `start` กับ `duration` แยกกัน ชิ้นที่ต่อกันเลยเหลื่อม 1 µs
ทำให้เทียบ "เสียงเหมือนเดิมไหม" ไม่ผ่านทั้งที่ไม่มีอะไรเปลี่ยนจริง
แก้สองชั้น: ปัดปลายก่อนแล้วค่อยลบ + `snap_ends()` บังคับให้ชิ้นแรก/ชิ้นสุดท้าย
เริ่มและจบตรงกับ segment เดิมเป๊ะ ไม่ให้ค่าคลาดสะสมทุกรอบที่ซอยซ้ำ

## E20 — ลบเสียงพูดของผู้ใช้หายไป 1.8 วินาที เพราะเช็ค "ซ้ำ" ผิดวิธี

**อาการ:** ทุกอย่างหลังนาที 13.37 เลื่อนเร็วขึ้น 1.8 วิ ซับหลุดจากคำพูดทั้งครึ่งหลัง
คลิปจบที่ 80.33 แทนที่จะเป็น 82.33 และท้ายคลิปเป็นจอดำ

**ลำดับเหตุการณ์**
1. ตัวซอยภาพ (`reframe_main_for_splits`) ปัดเศษพลาด → สร้าง segment ที่เวลาซ้อนกันบนแทร็กหลัก
2. CapCut เปิดไฟล์แล้วเจอ segment ซ้อน → **ย้ายตัวหนึ่งไปแทร็กใหม่เอง** (พฤติกรรมของ CapCut)
3. สคริปต์เลือกแทร็กด้วย **ลำดับ** (`video tracks[1]` = B-roll) → ไปหยิบแทร็กที่ CapCut เพิ่งสร้าง
   → เลย์เอาต์แบ่งจอพังทั้งคลิป
4. ผมเขียน `normalise_tracks.py` ให้ทิ้งแทร็ก Video Main ที่ "ถูกแทร็กหลักคลุมอยู่แล้ว"
   โดยเช็คแค่ **ช่วงเวลาบนไทม์ไลน์** → แต่ชิ้นนั้นเล่น **ต้นทางคนละช่วง** (28.53-30.37)
   ที่แทร็กหลักไม่ได้เล่น → ลบทิ้ง = เสียงพูดหายจริง 1.8 วินาที

**กลไกที่พลาด:** "ช่วงเวลาทับกัน" ไม่ได้แปลว่า "เนื้อหาเดียวกัน"
segment สองชิ้นครองเวลาเดียวกันได้โดยเล่นคนละส่วนของไฟล์ต้นทาง
เกณฑ์ที่ถูกต้องต้องเทียบ **คู่ (timeline, source)** ไม่ใช่ timeline อย่างเดียว

**วิธีแก้:** `restore_main.py` ดึงแทร็กภาพหลักกลับมาทั้งแทร็กจากไฟล์อ้างอิงคัตต้นฉบับ
แล้วค่อยไล่ใส่ framing ใหม่ ไม่ปะทีละจุด
และแก้ตัวซอยให้ทำงานเป็น **จำนวนเต็มไมโครวินาที** ตั้งแต่ต้น: ตัดเป็นรายการ offset แล้วหยิบคู่ติดกัน
ชิ้นจึงต่อกันสนิทโดยโครงสร้าง ไม่ต้องมี `snap_ends` และไม่ต้องผ่อนเกณฑ์
🟥 ต้นทางกับไทม์ไลน์ของ CapCut **ความยาวไม่เท่ากันเป๊ะแม้ speed=1** ต้องแมป offset ตามสัดส่วน
`src0 + round(off * src_span / span)` ห้ามสมมติว่าเท่ากัน

**บทเรียนคราวหน้า**
- ห้ามอ้างอิงแทร็กด้วยลำดับ ให้ดูจาก **สื่อที่อยู่บนแทร็ก** (CapCut สลับ/สร้างแทร็กเองได้)
- ก่อนลบอะไรที่ "ซ้ำ" ต้องพิสูจน์ว่า **เสียงที่ได้ยินเหมือนเดิม** ไม่ใช่แค่ช่วงเวลาทับกัน
- invariant เสียง (`av_signature`) จับได้จริง — ครั้งนี้มันเตือน 3 รอบก่อนผมจะเข้าใจ อย่าผ่อนเกณฑ์เพื่อให้ผ่าน
