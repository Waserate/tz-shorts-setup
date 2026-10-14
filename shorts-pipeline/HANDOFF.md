---
title: "Shorts Pipeline — Handoff"
stage: project
topic: shorts-pipeline
created: 2026-08-13
updated: 2026-08-13
tags: [stage/project, topic/video-automation, topic/thai-nlp]
---

# Shorts Pipeline — HANDOFF

Auto-edit short-form clips for **Take A Zeat** and **Bangkok Esports**: sync separate
video+audio → cut dead air and repeated takes → Thai subtitles 3-6 words per card →
matched B-roll → **emit an editable CapCut project with every element on its own track**.

**Root:** `N:\shorts-pipeline\`  ·  **Python:** `N:\shorts-pipeline\venv` (3.11.7)

---

## 🟡 OPTION ก — BUILT, WAITING ON THE USER'S VERDICT

**Draft `TAZ_KidsGun_subcheck` is written and opens in CapCut.** 100 real cards on their
own text track, camera on its own video track, mic on its own audio track with Enhancing
voice ON. The user scrubs it and says whether the subtitles land on the spoken words.

Reproduce:
```
venv\Scripts\python run_subs.py "N:\Take A Zeat\Kids Gun\kids Gun.wav" ^
    -o N:\shorts-pipeline\kidsgun.srt --terms-file N:\shorts-pipeline\terms_kidsgun.txt ^
    --pieces N:\shorts-pipeline\kidsgun_pieces.json --batch 4
venv\Scripts\python build_draft.py --cards N:\shorts-pipeline\kidsgun.json ^
    --video "E:\DCIM\235D5500\DSC_0198.MOV" --audio "N:\Take A Zeat\Kids Gun\kids Gun.wav" ^
    --name TAZ_KidsGun_subcheck --av-offset -3.935
```
Add `--from-pieces` to re-chunk from the cache without paying for ASR again.

Verified by spot check (playhead timecode vs the generated card):
- timeline `00:01:25:20` → audio 89.60 s → card 35 `จะทำให้ชาวเกมเมอร์` (89.58–90.58) ✅
- timeline `00:03:01:04` → audio 185.07 s → card 77 `คว้ารางวัลอันดับโลก` (185.06–185.80) ✅

### Round 2 — user reported missing subtitles, root cause found and fixed

Their verdict on v1: mostly good, but some cards off and **some missing**. Measured against
the waveform, they were right: **`speech_mask.py` now drives the timing** and the numbers
moved as follows (full story in ERRORS **E13**).

| metric | v1 | v2 |
|---|---|---|
| speech covered by cards | 106.6 s (80 %) | **114.7 s (86 %)** |
| speech lost in gaps | 17.5 s | **8.7 s** |
| cards firing before the words | 16 (max 0.97 s) | **11 (max 0.46 s)** |
| cards >0.30 s early | 9 | **1** |
| cards still up >0.5 s after speech stops | 5 | **0** |
| cards | 100 | 97 |

Draft `TAZ_KidsGun_subcheck2` holds v2. Proof of the fix, same moment, both drafts open:
v1 at `00:02:08:26` shows **nothing**, v2 at `00:02:09:05` shows `ทั้งที่ในรายการโหนกระแส`.

🟥 **Only the newest generated draft is kept** — the user's C: has ~35 GB free and each
draft cost ~160 MB. `build_draft.py` writes a `.shorts-pipeline` marker into every draft it
creates and `prune_old_drafts()` deletes **only folders carrying that marker**, so the
user's own projects and the donor can never be reached. `--keep-all` opts out.
Draft size is also down 159 MB → **40 MB** by copying only the one `audioAlg` render the
`vocal_beautify` actually references instead of the whole folder.

🟥 **The ASR decode settings are NOT the problem — that was tested and killed (E13 table).
Do not re-open `compression_ratio_threshold` / `no_repeat_ngram` / `repetition_penalty`.**

Remaining 8.7 s of holes are concentrated in 118–146 s, the retake cluster where Whisper
itself emits very few characters over long voiced stretches. That is an ASR limit, not a
timing bug; a targeted re-transcribe of that window is the next lever if the user cares.

Still open, deliberately not done: word boundaries broken across a few card pairs
(`ยังคงติดโห | ลมอยู่กับ`, `ที่ต้น | ตอนจริงๆ`); ASR spelling errors (`โต๊ะ` for `ตัวเลข`,
`กัญชัย` for `กรรชัย`) — **user chose to fix these by hand in CapCut, do not build a
replace list**; card font/position inherited from 0808 (small, sits low).

### Round 3 — pipeline reordered, cut + lock + size 15 built

Draft **`TAZ_KidsGun_v3`**: 231.8 s → **162.5 s (cut 30 %)**, 28 video + 28 audio + 86 text
segments. Verified open in CapCut.

- **Cut** (`cut_plan.py`): dead air 51.6 s (pause > 0.35 s, 0.12 s pad kept) + 4 repeated
  takes 17.7 s. Repeat rule is `partial_ratio >= 70` with a 15-character floor, calibrated
  on this take: true repeats scored 73.8–92.9, the best false pair 62.5, and the floor is
  what stops `123` (mic-test counting) matching a long sentence at 80. **Keep the LAST
  take** — you retake because the previous one was wrong.
- **Lock**: one CapCut group **per cut**, video segment + its own audio segment. One group
  for the whole timeline also keeps them together but welds all 56 clips into a lump so a
  single clip can no longer be nudged; pairing was checked in the UI — clicking one clip
  selects exactly its partner. Subtitles are left out of every group on purpose so cards
  stay individually editable.
- The keep list is the single source of truth: picture, sound and card times are all
  derived from it, and `assert_av_locked` crashes the build if the two tracks ever differ.
- **Font size 15** on every card (`font_size` + the style's `size`; `text_size` stays 30 —
  matching how the user's own size-15 text is stored).

Escape hatches: `--no-cut`, `--keep-repeats`, `--min-silence`, `--no-lock`, `--font-size`.

### Round 4 — subtitle timing rules, from the user 2026-08-13

🟥 **A card may never outlast the sentence being spoken. If the text needs more room it
becomes a NEW card.** Enforced three ways, all in `thai_timing.py`:

1. an over-long Whisper piece is anchored by its **END**, not its start (ERRORS **E14** —
   this was the "sub starts a second early" bug);
2. a card's end is bounded by `last_voiced_before()` and `assert_no_overrun` crashes the
   build if it is not;
3. `GAP_SPLIT = 0.35 s`, equal to the dead-air threshold, so no card is ever built across a
   pause that the cut removes.

Current draft **`TAZ_KidsGun_v4`** — 163.2 s, 28 A/V pairs, 86 cards, size 15.
Card timing on the finished timeline: worst early **0.40 s** (1 card over 0.30 s),
overhang **0.00 s**, shortest card 0.44 s, median 1.32 s.
Spot-checked in CapCut: `00:00:38:21` blank → `00:00:39:24` `จากข่าวเหตุการณ์`.

### Round 5 — repeat detection rebuilt (user: "ยังมีประโยคซ้ำอยู่ ต้องทำใหม่")

They were right. Comparing whole utterances could not see repeats that straddle utterance
boundaries or sit three-deep inside one. Rebuilt to compare an **18-character window from
each card's start**, calibrated against a hand-read answer key over all 97 cards — full
story in ERRORS **E15**, including the audio-similarity experiment that measured useless.

| | before | after |
|---|---|---|
| repeat takes cut | 4 | **12** |
| mic-test junk | 0 | **5 cards, 4.9 s** |
| total cut | 30 % | **40 %** (231.8 → 138.4 s) |
| false positives across every pair in the file | — | **0** |

Current draft **`TAZ_KidsGun_v5`** — 138.4 s, 26 A/V pairs, 73 cards, size 15.

🟥 **The ceiling is real and is not a bug to keep grinding on.** Text cannot match a repeat
the ASR heard as different words (`เอาอีกแล้วสังคมโยนบาป` vs `เสือใหญ่หลายจ้าง…` = 38.9,
lower than genuine non-repeats). So:
- 60+ → cut;
- **48-59 → printed as `[REVIEW]`, never cut.** Deleting real content is worse than leaving
  a repeat in;
- below → ignored.

Known leftovers on the v5 timeline, for a manual pass: `0:06.25 เอาอีกแล้วสังคมโยนบาป`
(false start) and `0:40.18 คือเหตุการณ์จริงๆนี้เนี่ย` (first of three attempts).
`--start-at <seconds>` drops everything before the real content when the head is junk.

### Round 6 — second clip: `N:\Take A Zeat\14 Vegan\Video Main.mp4`

One file, sound inside the video, so **no sync stage at all**. Draft **`TAZ_Vegan_v1`**:
186.3 s → **135.8 s (cut 27 %)**, 20 picture segments, 60 cards, size 15.

🟥 **DONOR MAP — check this first, it changed.**

| what | donor | why |
|---|---|---|
| picture | **`0813`** | the user's own Vegan project: colour preset + Enhance voice already on it |
| captions | **`0727`** | 71 text segments, `font_size 15.0`, type `text` |

- **`0808` NO LONGER EXISTS.** It was still present at 15:31 on 2026-08-13 (last
  `root_meta_info` backup listing it) and was gone by 16:50, removed inside CapCut while
  the user was working — not by `prune_old_drafts`, which only ever deletes folders
  carrying the `.shorts-pipeline` marker and logged `pruned nothing` on that run. Not in
  the Recycle Bin. The backups here cover `root_meta_info.json` only, never draft folders,
  so it is not recoverable from anything this project holds.
- **Colour preset** = 9 `effects` materials sharing `effect_id 7501974767453474064`
  (brightness .0731 / contrast .0639 / saturation .0959 / highlight / shadow / black /
  clear / temperature / tone) plus one `hsl`. It is NOT an `adjusts` material — nothing in
  any draft uses that bucket. Cloning a `0813` video segment carries the whole grade, the
  beauty effects and Enhance voice in one move.
- **Enhance voice intensity = `ambient_sound_level`.** Values seen across the machine are
  25 / 50 / 75, matching the UI slider. The user wants **25**, which is what `0813` has.
- With embedded sound there is no audio track: the video segment carries the
  `vocal_beautify` itself, and `assert_av_locked` returns early because one file cannot
  desync from itself.

**ASR word accuracy (`hotwords`)** — a new lever, and the one that fixed this clip. The
per-video term list only ever changed how text was SPLIT; `hotwords` changes what the model
HEARS: `วีแค่น` → `วีแกน`, `เคลียเตอร์` → `ครีเอเตอร์`, `เนื้อสองทรัพย์` → `เนื้อสัตว์`,
`รุ่งร่าง` → `รูปร่าง`, `ขนหนึ่งสองสามเรื่องศัพท์` → `ขนมอบ`. Terms live in
`terms_<clip>.txt` and feed both jobs.
🟥 Costs memory: `--batch 4` OOMs with hotwords on the 4 GB card, **use `--batch 2`**
(RTF 3.97x — 186 s of audio took 12 min).

Still garbled after hotwords, for a manual pass: `ปล่อยโคกลาง/ครีมหลั่ง`, `วีแค่นเนื๊อ`,
`มีเดียมแร้ง`, `ไวรัลสนานโซเชียล`, `เชอร์เนี่ยยุคไม้เร็ว`.

### Round 7 — 🟥 EVERY WORD GETS A SUBTITLE (user rule, 2026-08-13)

**Kept audio is either captioned or cut. There is no third state.** The user found 23 s of
the Vegan edit with picture, waveform and no subtitle. Cause and fix: ERRORS **E16**.

- `fill_gaps.py` re-decodes only the voiced spans that carry no card, with the anti-repeat
  knobs off, one span at a time. Safe at that size, fatal file-wide.
- A span whose own decode is degenerate (mic-test counting) is written to
  `<cards>.dead.json` and **cut** by `cut_plan` — no caption exists for it.
- `build_draft` prints `[WARN] N kept spans still have speech with no caption`. Treat any
  line there as a defect, not as noise.
- `fill` is idempotent: re-decoding a span replaces its pieces instead of stacking on them.
- Keep the pre-fill pieces copy (`*_pass1.json`). Recovering the cache needed it once.

Current draft **`TAZ_Vegan_v2`** — 186.3 s → **118.5 s (cut 36 %)**, 23 picture segments,
65 cards, size 15, Enhance 25, colour preset on every clip.
Residual uncaptioned: **3.3 s** in two spans (source `15.42-16.84`, `92.82-94.70`), down
from 27 s.

**S6 (B-roll) is the only stage left.** Not started, per the user's own ordering.

---

## Status by stage

## 🟢 PIPELINE ORDER — fixed by the user 2026-08-13, this is the contract

1. **Sync** picture to sound; camera audio muted, the external mic is the only sound.
2. **Enhance** that mic track.
3. **Lock** — picture and sound move together from here on. Nothing may desync them.
4. **Clean** — dead air and repeated takes out.
5. **Subtitles** last, text size **15**.

Note the operations do not run in that order: repeat detection needs the transcript, so
ASR runs on the uncut audio, the cut plan is built from it, and the card times are then
remapped onto the cut timeline. The finished draft matches the order above.

| Stage | What | State |
|---|---|---|
| S0 | toolchain (venv, CUDA on Pascal — no ffmpeg on this box) | ✅ done |
| S1 | A/V sync (separate recorder ↔ camera) | ✅ done — measured −3.935 s, no drift |
| S2 | Thai ASR | ✅ done — model chosen + tuned |
| S3 | word-level timestamps | ✅ done — waveform-driven (`speech_mask.py`) |
| S4 | dead-air + repeat-take cut planner | ✅ done — `cut_plan.py` |
| S5 | Thai subtitle chunking 3-6 words | ✅ done, regression-tested |
| S6 | B-roll matching | ⬜ not started |
| S7 | CapCut draft writer | ✅ done — `build_draft.py`, cut + locked + size 15 |

---

## Verified environment facts (do not re-derive)

- GPU **GTX 1050 Ti, 4 GB, Pascal (sm_61)**. CTranslate2 offers only
  `int8 / int8_float32 / float32` on this card — **no float16**. Use `int8`.
- 🟥 **PyTorch ≥2.8 default wheels dropped Pascal.** If torch is ever needed, install from
  `--index-url https://download.pytorch.org/whl/cu126`, else CUDA silently falls back to CPU.
  faster-whisper does **not** need torch, which is why it was chosen.
- 🟥 The pip `nvidia-*` wheels put their DLLs where Windows cannot find them →
  `Library cublas64_12.dll is not found`. **`import cuda_setup` before ctranslate2** in every script.
- C: has only ~35 GB free → models and project live on **N:**.
- 🟥 **There is no ffmpeg/ffprobe on this machine** (only FormatFactory's private copy).
  Decode audio with `faster_whisper.audio.decode_audio` and probe durations with `av`
  (PyAV ships with faster-whisper). An earlier "S0 toolchain (ffmpeg…)" note was wrong.
- 🟥 `batch_size=16` **OOMs on a real-length file** — see ERRORS E11. Use `--batch 4`
  (RTF 0.80x, ~3.9 GB of the 4 GB card).
- Screen coords: virtual desktop starts at **X = −1920** (left monitor). Screenshot pixel 0
  = real X −1920. `spike/click.ps1` converts automatically; do not pass raw screen coords.

## CapCut facts (verified on this machine)

- CapCut **international 9.2.0.3931**, draft root
  `C:\Users\Admin\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\`
- `draft_content.json` is **plain JSON, not encrypted** on 9.2 (public reports only covered ≤5.9).
- `version: 360000` is **constant from app 3.3.0 → 9.2.0** → schema is stable, low drift risk.
- Time unit = **microseconds**. `target_timerange` = position on timeline,
  `source_timerange` = in-point in the source file (this pair does dead-air cutting AND B-roll).
- Text track: `flag: 1`, segment `render_index` from 14000 upward, no overlapping segments allowed.
- 🟥 **`root_meta_info.json` is the gatekeeper** — it lives INSIDE `com.lveditor.draft\`
  (not at Projects root as public write-ups claim). A draft folder not listed there is
  rejected with "unusual path". Back it up before writing (`backup/` holds a copy).
- `template-2.tmp` is a byte-identical backup of `draft_content.json`, not a rival source.
- Thai renders correctly **regardless of declared font** — CapCut falls back. Setting `th.ttf`
  is harmless and explicit but fixes nothing (an earlier claim that this was a bug was wrong).
- Method that works: **clone-from-donor** — deep-copy segments + their whole material graph
  out of a draft CapCut itself wrote (`0808`), re-id, re-time. Never build materials from scratch.

## Chosen stack

| Job | Tool | Why |
|---|---|---|
| Thai ASR | `Vinxscribe/biodatlab-whisper-th-large-v3-faster` (Thonburian) | won the A/B outright |
| Runtime | `faster-whisper` 1.2.1 + CTranslate2 int8 | no torch → dodges the Pascal problem |
| Anti-loop | `condition_on_previous_text=False`, `repetition_penalty=1.15`, `no_repeat_ngram_size=4`, temperature fallback | model hallucinated a slot-machine advert 10× without it |
| Speed | `BatchedInferencePipeline(batch_size=16)` | RTF 7.61x → 0.36x (**21× faster**) |
| Thai words | PyThaiNLP 5.3.5 (`newmm`; `nlpo3` available) | Whisper's pieces are NOT Thai words |
| Chunking | own DP over POS-tagged units | see `thai_subtitle.py` |
| Output | `pysubs2` (UTF-8 — CapCut requires it) | |

⚠️ `pythainlp[compact]` **fails to install on Windows** (pyicu needs ICU + pkg-config).
Install `pythainlp` + `nlpo3` separately.

## Files

```
N:\shorts-pipeline\
  cuda_setup.py        import FIRST, before ctranslate2 — adds nvidia DLL dirs
  speech_mask.py       RMS speech/silence mask off the waveform — drives all timing
  cut_plan.py          dead air + repeated takes -> ONE keep list everything obeys
  fill_gaps.py         2nd ASR pass over voiced spans with no caption; marks dead spans
  export_audio.py      renders the cleaned audio to .wav (same keep list as the draft)
  thai_subtitle.py     Thai word chunking (DP + POS + bind rules + custom dict)
  thai_timing.py       char→time clock (voiced-time only), word timings, gaps, SRT out
  run_subs.py          CLI: audio → .srt + .json (--pieces caches ASR, --from-pieces reuses)
  build_draft.py       CLI: cards .json + video + audio → editable CapCut draft
  terms_kidsgun.txt    per-video vocabulary for the Kids Gun clip
  test_chunker.py      🟥 GOLDEN REGRESSION TESTS — run after ANY chunker change
  bench_asr.py         model A/B
  bench_asr2.py        anti-loop + batching benchmark
  corpus_thai.txt      32 real narration lines lifted from CapCut project 0808
  spike/               frozen proof-of-concept (build_spike.py) + screenshot/click/focus
                       helpers. focus2.ps1 replaces focus.ps1: plain SetForegroundWindow
                       is refused from a background process, AttachThreadInput fixes it.
  backup/              root_meta_info.json backups
  models/              HF + CT2 model cache
```

## Benchmark results (60 s clip of the user's own voice)

| Model | RTF | Thai quality |
|---|---|---|
| **Thonburian large-v3** | 7.61x → **0.36x batched** | **best**, wins clearly |
| baseline large-v3 | 4.22x | worse, injects English junk (`SsangKok`) |
| turbo large-v3 | 0.65x | unusable for Thai (`說 cổ alum Passover`) |

**Beats CapCut Auto Caption** on the same file — CapCut produced `สังคมโยนบั๊บ` (ours
`สังคมโยนบาป`), `ไฮเกม` (ours `ให้เกม`), `ให้แกเป็น` (ours `ให้เกมเป็น`), and spelled the
school name three different ways. CapCut also captions B-roll/BGM audio because it reads the
mixed timeline; we read the clean mic track only.

**CapCut Auto Caption cannot be automated** — `recognize_task_id` is a server-side job needing
UI + login. Only usable as a manual one-click step.

## User's own work as the benchmark set

CapCut project **`0808`** is the user's hand-made version of this exact pipeline:
1 camera file cut into 61 pieces + 1 external mic wav + 79 auto-caption cards.
Sources still on disk: `N:\Take A Zeat\Kids Gun\kids Gun.wav` (231.825 s) and
`E:\DCIM\235D5500\DSC_0198.MOV` (251.040 s). Edited timeline 224.6 s → **they cut 10.6 %**.
Use it to score every stage against their own manual result.

🟥 **0808 is a work in progress, NOT a synced reference edit.** Its audio is one uncut
segment while its 61 video segments were trimmed, so the implied A/V offset drifts from
+3.25 s at the head to +66.25 s at the end. Do not read a sync offset out of it.

**Measured A/V offset for this take: `-3.935 s`** (`video_time - audio_time`; the recorder
was rolling 3.935 s before the camera). Envelope cross-correlation at wav 5 s / 100 s /
185 s all returned −3.935 ± 0.002 s, so there is **no clock drift on this pair**;
correlation over the whole overlap 0.87, versus 0.04 for the 0808-derived +3.25 s.
The sign convention was pinned with a synthetic known-shift case first.

## Hard requirements from the user

- Subtitles: **3-6 words**, never break a word, **sentence structure beats word count**.
- Every generated element must be a **separate editable CapCut layer**.
- **Enhancing voice stays ON** (their raw audio is echoey) — make it a toggle, default on.
- B-roll: they supply news/related clips and **approve each one themselves**.
- Thai output, no crude pronouns.

## Open items

- Sync (S1) and cut planner (S4) not started. `audio-offset-finder` + `auto-editor --export v1`
  + `rapidfuzz` on the transcript are the researched picks; no tool handles **clock drift** —
  check the offset at 3 points across a long take.
- `word_timestamps=True` costs ~5× speed (RTF 0.36 → 1.8).
- Per-video custom dictionary is the highest-leverage quality knob (names, games, streamers).
- Legal: *Cordova v. Huneault* (N.D. Cal., Feb 2026) let a **DMCA §1201** claim proceed against a
  reaction/commentary YouTuber for stream-ripped clips, and held §1201 separate from fair use.
  Scope: motion-to-dismiss denial, one district, not binding precedent. User was told, reaffirmed
  their approach, and approves each clip personally.

---

## 🟢 RUNBOOK — one clip, start to finish (rewritten 2026-08-20 after 14 Vegan shipped)

Input is a single `Video Main.mp4` with the narration already inside it. There is no separate
mic recording, so there is no sync stage.

### What the user prepares, per clip

| | where | note |
|---|---|---|
| `Video Main.mp4` | `N:\Take A Zeat\<clip>\` | narration inside; nothing else needed |
| B-roll source clips | `<clip>\broll2\` | user downloads them — yt-dlp cannot fetch TikTok here, ssstik.io works |
| screenshots (profile, video grid) | `<clip>\B-Roll\` | jpg/png |
| comment screenshots | `<clip>\comments\` | png |
| `terms_<clip>.txt` | repo root | proper nouns so the tokeniser keeps them whole |
| `caption_terms_<clip>.json` | repo root | Thai-script English -> English, spelled numbers -> numerals |
| the title line | in chat | e.g. "เมื่อ Vegan 14 ปี กินเนื้อครั้งแรก??" |

Two manual steps in CapCut, both by the user:

1. New draft, import the mp4, **Captions > Auto captions > Thai**.
2. **Do the cleaning themselves** — dead air, repeated takes, counting in. Their cut is the
   standard; the automatic cleaner under-cuts badly (19% against their 56% on this clip) and
   the captions generated after their cut leave the removed takes with no text to detect.
3. **Close CapCut.** It rewrites `draft_content.json` from memory on exit and will silently
   undo everything below. Every script here refuses to run while it is open.

### The scripted part

```
1.  normalise_tracks.py  --draft "<name>"
        main picture first, B-roll second, stills third, captions last; drops the duplicate
        track CapCut invents when segments overlap. RUN FIRST AND AFTER ANY CAPCUT SESSION —
        every later script identifies tracks by position.
2.  resplit_captions.py  --draft "<name>" --terms-file terms_<clip>.txt
        paragraph captions -> 3-5 word cards, CapCut's timings preserved
3.  apply_caption_terms.py --draft-file <draft> --rules caption_terms_<clip>.json --out <draft>
4.  enrich_draft.py      --draft "<name>" --skip-look --zoom-share 0
                         --broll-plan broll_<clip>.json --comments stills_<clip>.json
        B-roll and stills, placed by CAPTION ANCHOR not by seconds.
        --skip-look because the user's own draft already carries grade + retouch + Enhance.
5.  add_title.py         --draft "<name>" --text "…
…" --at 0 --until <n> --box 0.92
6.  fix_layout.py        --draft "<name>" --follow-draft --main-bottom
        pairs every split window: presenter BOTTOM, B-roll TOP. Asserts no half is empty
        and that the sound is untouched.
7.  face_frame.py        --draft "<name>"
        aims each split crop at the measured face instead of the middle of the frame
8.  fill_frame.py        --draft "<name>" --skip-track 2
        scales up anything that would letterbox (a 4:3 insert in a 9:16 frame)
9.  uniform_captions.py  --draft "<name>" --size 20
        ONE size for every card, Latin at 0.783 of it so it stands the same height as Thai.
        Cards too long to fit are split, never shrunk.
10. normalise_tracks.py --draft "<name>"      # re-assert the structure
11. check_black.py      --draft "<name>"      # must print "ไม่พบจอดำ"
```

`run_vegan_v6.sh` is the worked example of steps 6-10 chained with the CapCut-is-open guard.

### Step 4b — inserting a source clip (agreed 2026-08-20, NOT BUILT YET)

The user has handed this job over: pick the moment, insert the clip with its own sound, and
write the Thai captions for it. On 14 Vegan they did it by hand — an 11.7s reaction inserted
at 44.67s, everything after it shifted +11.70s, music split around it, three captions added.

Verified this is doable before promising it:

* English ASR runs offline. `mobiuslabsgmbh/faster-whisper-large-v3-turbo` is already in the
  HF cache alongside `Systran/faster-whisper-medium`; both are multilingual.
* 🟥 `vad_filter=True` merges a whole clip into ONE 37-second segment with no usable timings.
  Use `vad_filter=False, word_timestamps=True` to get word-level starts.
* Run against the clip the user inserted, the ASR found their exact subtitle points:
  "are you okay" at 63.98s -> their caption at timeline 50.70 (computed 50.68);
  "really" at 68.32 -> theirs 55.20 (computed 55.02). Two of three within 0.02s.

What still has to be written: `insert_clip.py`. Inserting is NOT the same as the existing
B-roll overlay — it lengthens the timeline, so every segment on every track after the insert
point moves by the clip's duration. Required invariant: the sound that was already there is
the same sound, shifted by exactly one constant; nothing dropped, nothing overlapping. Assert
it, because the last time picture segments were rebuilt without that check, 1.8s of narration
disappeared (E20).

Division of labour agreed with the user: Claude picks the moment and reports each insert as a
line (source range, why, the Thai captions with the English they came from); the user vetoes
or reworks BY CHAT, not by opening CapCut mid-flight.

### What the user still does by hand afterwards (and should keep doing)

On 14 Vegan the finished version differed from the scripted draft by exactly four things, all
of them editorial rather than mechanical:

* an 11.7s reaction clip inserted mid-video with its own sound, everything after it shifted
* background music on its own track at volume 0.019, split around the insert so the insert
  can be heard
* three captions written by hand for the inserted clip
* one comment still removed

None of that is worth automating. The scripts should hand over a draft that is correct on
timing, framing and type; the edit decisions stay with the user.

### Hard rules learned the expensive way

* 🟥 **Close CapCut before every write.** See E20 — it reorganises tracks on open.
* 🟥 **Never identify a track by index without running `normalise_tracks` first.**
* 🟥 **"Same time span" is not "same content".** Two segments can hold the same seconds and
  play different parts of the source. Deleting one on a timeline-overlap test destroyed 1.8s
  of the user's narration (E20).
* 🟥 **Slice in whole microseconds.** Rounding start and duration separately drifts pieces
  1-2 us apart and the clip stops adding up to what it replaced (E17, E19).
* 🟥 **Measure text in the font that actually renders it.** The captions render in `en.ttf`,
  which sets Thai 39% wider than NotoSansThai; measuring with the wrong font certified cards
  that then wrapped. `PX_PER_UNIT = 5.6`, verified against the user's own screenshot.
* 🟥 **Keep only the newest draft and backup.** Marker file `.shorts-pipeline`,
  `prune_old_drafts()`.
