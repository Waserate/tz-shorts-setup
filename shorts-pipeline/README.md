---
title: "Shorts Pipeline"
stage: project
topic: shorts-pipeline
created: 2026-08-13
updated: 2026-08-13
tags: [stage/project, topic/video-automation, topic/thai-nlp, topic/capcut]
---

# Shorts Pipeline

Auto-edit short-form clips for **Take A Zeat** and **Bangkok Esports**, ending in a
**CapCut project where every generated element is its own editable track**.

👉 **Start here:** [`HANDOFF.md`](HANDOFF.md) — status, verified facts, next step.
Failure log: [`ERRORS.md`](ERRORS.md). New chat: [`NEW_CHAT_PROMPT.md`](NEW_CHAT_PROMPT.md).
KB article: `~/memos/wiki/shorts-pipeline.md`.

## Quick start

```powershell
# subtitles from an audio file -> .srt + .json
N:\shorts-pipeline\venv\Scripts\python.exe N:\shorts-pipeline\run_subs.py `
    "N:\Take A Zeat\Kids Gun\kids Gun.wav" `
    -o N:\shorts-pipeline\out.srt `
    --terms "เทพศิรินทร์,ชาวเกมเมอร์,โหนกระแส,หนุ่มกรรชัย"

# 🟥 after ANY edit to thai_subtitle.py
N:\shorts-pipeline\venv\Scripts\python.exe N:\shorts-pipeline\test_chunker.py
```

`--terms` is the per-video vocabulary (names, games, places). It is the single biggest
quality lever — the base dictionary has never seen a streamer or a school name, and a
fragmented proper noun is what makes subtitles look broken.

## Rules

- `import cuda_setup` **before** ctranslate2/faster_whisper, or CUDA dies with
  `cublas64_12.dll is not found`.
- Subtitles: **3-6 words, sentence structure beats word count, never break a word.**
- Back up `root_meta_info.json` before touching a CapCut draft.
- Nothing may be burned into the video — every decision leaves as timestamps.

## Layout

| File | Role |
|---|---|
| `cuda_setup.py` | makes the pip nvidia DLLs findable — import first |
| `thai_subtitle.py` | Thai word chunking: DP over POS-tagged unbreakable units |
| `thai_timing.py` | char→time clock, word timings, gap splitting, SRT output |
| `run_subs.py` | CLI: audio → `.srt` + `.json` |
| `test_chunker.py` | 🟥 golden regression tests (the user's own corrections) |
| `bench_asr.py` / `bench_asr2.py` | model A/B; anti-loop + batching benchmark |
| `corpus_thai.txt` | 32 real narration lines lifted from CapCut project `0808` |
| `spike/` | CapCut draft writer spike + screenshot/click/focus helpers |
| `backup/` | `root_meta_info.json` backups |
