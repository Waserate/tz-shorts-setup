"""Second ASR pass over the stretches the first pass left uncaptioned.

Why a second pass is needed: `no_repeat_ngram_size` + `repetition_penalty` exist to stop a
hallucination loop (ERRORS E4) and they work — but they also gag the model exactly where
the speaker is repeating themselves. On the Vegan take the model returned **nothing** for
33 s of clearly voiced audio because that audio was a retake of a line it had already
transcribed. The result is the worst of both worlds: no subtitle, and no text for the
repeat cleaner to see, so the audio is not cut either.

The rule this restores: **kept audio is either captioned or cut, never neither.**

The relaxed settings are safe here in a way they are not globally, because each gap is a
few seconds long and is decoded on its own — a loop cannot run away across the whole file —
and any span that still comes back degenerate is rejected by a repetition check.
"""
from __future__ import annotations

import numpy as np

SR = 16000
# 1.0-1.4 s of voiced audio is still a word or two, and the user's rule is that every word
# gets a caption. Anything that decodes to nothing or to garbage is marked dead and cut,
# so attempting a short span costs nothing but a second of GPU.
MIN_GAP = 0.8
PAD = 0.20             # decode slightly wide so word onsets are not clipped
LOOP_MAX = 0.35        # reject a span whose own output is mostly repeated 6-grams


def uncaptioned_spans(mask, cards, *, min_gap: float = MIN_GAP,
                      limit: float | None = None) -> list[tuple[float, float]]:
    """Voiced stretches with no card on them."""
    covered = np.zeros(mask.n, dtype=bool)
    for c in cards:
        covered[mask._idx(c["start"]):mask._idx(c["end"]) + 1] = True
    hole = mask.frames & ~covered

    out, run = [], None
    for i in range(mask.n):
        if hole[i] and run is None:
            run = i
        elif not hole[i] and run is not None:
            out.append((run, i))
            run = None
    if run is not None:
        out.append((run, mask.n))

    hop = mask.duration / mask.n
    spans = [(a * hop, b * hop) for a, b in out if (b - a) * hop >= min_gap]
    if limit is not None:
        spans = [(a, b) for a, b in spans if a < limit]
    return spans


def _loop_score(text: str) -> float:
    g = [text[i:i + 6] for i in range(max(0, len(text) - 6))]
    return 1 - len(set(g)) / max(1, len(g))


def fill(audio_path: str, pieces: list[tuple[str, float, float]], mask, cards,
         *, hotwords: str = "", decode: dict | None = None, verbose: bool = True
         ) -> tuple[list[tuple[str, float, float]], list[tuple[float, float]]]:
    """Decode every uncaptioned voiced span.

    Returns (merged pieces, dead spans). A dead span is voiced audio whose own decode came
    back degenerate — in practice mic-test counting, "หนึ่ง สอง สาม หนึ่ง สอง สาม". There is
    no sensible caption for it, so it is handed to the cut planner to be removed instead.
    That is what keeps the promise: captioned or cut, never neither.
    """
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    import run_subs

    spans = uncaptioned_spans(mask, cards)
    if not spans:
        return pieces, []
    if verbose:
        total = sum(b - a for a, b in spans)
        print(f"gap fill: {len(spans)} uncaptioned spans, {total:.1f}s of speech")

    d = dict(decode or run_subs.DECODE)
    # the two knobs that gag a retake — off for these short, isolated spans only
    d["no_repeat_ngram_size"] = 0
    d["repetition_penalty"] = 1.0
    d["vad_filter"] = False
    d.pop("vad_parameters", None)
    d["compression_ratio_threshold"] = None

    audio = decode_audio(audio_path, sampling_rate=SR)
    device, ctype = run_subs.whisper_device()
    model = WhisperModel(run_subs.MODEL, device=device, compute_type=ctype,
                         download_root=run_subs.ROOT)

    added, dead, redecoded = [], [], []
    for a, b in spans:
        lo = max(0.0, a - PAD)
        hi = min(len(audio) / SR, b + PAD)
        chunk = audio[int(lo * SR):int(hi * SR)]
        if len(chunk) < SR // 2:
            continue
        segs, _ = model.transcribe(chunk, hotwords=hotwords or None, **d)
        got = [(w.word, w.start + lo, w.end + lo) for s in segs for w in (s.words or [])]
        text = "".join(t for t, _, _ in got)
        if not text.strip():
            if verbose:
                print(f"   {a:7.2f}-{b:7.2f}  nothing decoded -> mark for cutting")
            dead.append((a, b))
            continue
        if _loop_score(text) > LOOP_MAX:
            if verbose:
                print(f"   {a:7.2f}-{b:7.2f}  degenerate -> mark for cutting "
                      f"({text[:28]!r})")
            dead.append((a, b))
            continue
        if verbose:
            print(f"   {a:7.2f}-{b:7.2f}  +{len(got):3d} pieces  {text[:46]!r}")
        added.extend(got)
        redecoded.append((lo, hi))

    # Idempotence. Running fill twice used to decode a span that an earlier run had already
    # filled and stack the new pieces on top of the old ones, which produced overlapping
    # cards and tripped assert_timing_sane. A span that gets re-decoded replaces whatever
    # was there; it never adds to it.
    if redecoded:
        # OVERLAP, not just "starts inside": a piece beginning before the window and
        # running into it used to survive and then sit on top of the freshly decoded
        # pieces, which produced overlapping cards downstream.
        pieces = [p for p in pieces
                  if not any(p[2] > lo and p[1] < hi for lo, hi in redecoded)]
    merged = sorted(pieces + added, key=lambda p: p[1]) if added else pieces

    # Belt and braces: the piece stream must be monotonic. Anything downstream that turns
    # pieces into cards assumes it, and assert_timing_sane will (rightly) crash if not.
    clean, prev_end = [], 0.0
    for txt, st, en in merged:
        st = max(st, prev_end)
        en = max(en, st)
        clean.append((txt, st, en))
        prev_end = en
    merged = clean
    if verbose:
        print(f"gap fill: {len(pieces)} -> {len(merged)} pieces, "
              f"{len(dead)} spans marked for cutting")
    return merged, dead
