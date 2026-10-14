"""End-to-end: audio -> Thai ASR -> word timings -> subtitle cards -> .srt"""
import os, sys, time, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cuda_setup  # noqa: F401

from faster_whisper import WhisperModel, BatchedInferencePipeline
from speech_mask import SpeechMask
from thai_subtitle import build_dict
from thai_timing import cards_with_times, to_srt

MODEL = "Vinxscribe/biodatlab-whisper-th-large-v3-faster"   # best Thai in our A/B
from config import MODELS_DIR as ROOT, PIPELINE_DIR, whisper_device

DECODE = dict(
    language="th",
    beam_size=5,
    word_timestamps=True,
    condition_on_previous_text=False,     # stops a hallucination loop propagating
    repetition_penalty=1.15,
    no_repeat_ngram_size=4,
    temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    compression_ratio_threshold=2.2,
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=400),
)


def transcribe(audio: str, batch_size: int = 16, hotwords: str = ""):
    """hotwords biases what the model HEARS. The per-video term list only ever fixed how
    the text was split; the names and loanwords still came back wrong (วีแกน -> วีแค่น,
    ครีเอเตอร์ -> เคลียเตอร์). faster-whisper applies hotwords per window, which is what
    we need since condition_on_previous_text is off."""
    device, ctype = whisper_device()
    m = WhisperModel(MODEL, device=device, compute_type=ctype, download_root=ROOT)
    pipe = BatchedInferencePipeline(model=m)
    t0 = time.time()
    segs, info = pipe.transcribe(audio, batch_size=batch_size,
                                 hotwords=hotwords or None, **DECODE)
    pieces = []
    for s in segs:
        for w in (s.words or []):
            pieces.append((w.word, w.start, w.end))
    return pieces, time.time() - t0, info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("-o", "--out", default=os.path.join(PIPELINE_DIR, "out.srt"))
    ap.add_argument("--terms", default="", help="comma-separated per-video vocabulary")
    ap.add_argument("--terms-file", default="", help="file with one vocabulary term per line")
    ap.add_argument("--batch", type=int, default=16)
    # ASR is the slow part (~7 min for 4 min of audio) while re-chunking is instant, so
    # cache the pieces and iterate on the dictionary without paying for ASR again.
    ap.add_argument("--pieces", default="", help="cache file for raw Whisper pieces")
    ap.add_argument("--from-pieces", action="store_true",
                    help="reuse --pieces instead of running ASR")
    ap.add_argument("--no-fill", action="store_true",
                    help="skip the second pass over uncaptioned speech")
    ap.add_argument("--no-mask", action="store_true",
                    help="time cards by character count instead of the waveform (worse)")
    a = ap.parse_args()

    terms_pre = [t.strip() for t in a.terms.split(",") if t.strip()]
    if a.terms_file:
        terms_pre += [ln.strip() for ln in open(a.terms_file, encoding="utf-8")
                      if ln.strip() and not ln.startswith("#")]

    if a.from_pieces:
        pieces = [tuple(p) for p in json.load(open(a.pieces, encoding="utf-8"))]
        print(f"ASR: skipped, {len(pieces)} pieces loaded from {a.pieces}")
    else:
        pieces, el, info = transcribe(a.audio, a.batch, hotwords=" ".join(terms_pre))
        print(f"ASR: {len(pieces)} pieces in {el:.1f}s  (audio {info.duration:.1f}s, "
              f"RTF {el/max(info.duration,1):.2f}x)")
        if a.pieces:
            json.dump(pieces, open(a.pieces, "w", encoding="utf-8"), ensure_ascii=False)
    if not pieces:
        print("no speech found"); sys.exit(1)

    terms = terms_pre

    # The waveform decides where a piece's time was really spent; character counting
    # cannot tell a long pause from long speech and threw away 18.4 s (ERRORS E13).
    mask = None if a.no_mask else SpeechMask(a.audio)
    cd = build_dict(terms)
    cards = cards_with_times(pieces, custom_dict=cd, mask=mask)

    # Kept audio must be captioned or cut, never neither. The anti-repeat settings gag the
    # model exactly where the speaker retakes a line, so re-decode just those spans.
    if mask is not None and not a.no_fill:
        import fill_gaps
        filled, dead = fill_gaps.fill(
            a.audio, pieces, mask, [{"start": c.start, "end": c.end} for c in cards],
            hotwords=" ".join(terms_pre))
        if len(filled) != len(pieces):
            pieces = filled
            if a.pieces:
                json.dump(pieces, open(a.pieces, "w", encoding="utf-8"), ensure_ascii=False)
            cards = cards_with_times(pieces, custom_dict=cd, mask=mask)
        # audio with no possible caption: hand it to the cut planner
        json.dump(dead, open(a.out.replace(".srt", ".dead.json"), "w"), indent=1)
    to_srt(cards, a.out)

    durs = [c.end - c.start for c in cards]
    sizes = [len(c.words) for c in cards]
    print(f"cards: {len(cards)}  dur min/median/max "
          f"{min(durs):.2f}/{sorted(durs)[len(durs)//2]:.2f}/{max(durs):.2f}s  "
          f"words min/max {min(sizes)}/{max(sizes)}")
    print(f"wrote {a.out}")
    json.dump([{"start": c.start, "end": c.end, "text": c.text} for c in cards],
              open(a.out.replace(".srt", ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
