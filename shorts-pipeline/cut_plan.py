"""Decide what to cut out of the take: dead air and repeated takes.

Output is a list of KEEP intervals in **audio-file time**. Everything downstream — the
video segments, the audio segments and the subtitle card times — is derived from that one
list, so picture, sound and text cannot drift apart: they are all the same cut.

Two passes, in this order:

1. **Dead air** — straight off the waveform (`speech_mask`). Silence longer than
   `min_silence` is removed, keeping `pad` on each side so words do not get clipped and
   the cut does not sound like a splice.
2. **Repeated takes** — the speaker flubs a line and says it again. Utterances are compared
   with rapidfuzz; in a group of near-identical utterances only the LAST survives, which is
   the normal convention: you retake because the previous one was wrong.

The transcript is required for pass 2, which is why ASR still has to run before cutting
even though the cut comes before subtitles in the finished timeline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

# --- dead air -------------------------------------------------------------------------
MIN_SILENCE = 0.35     # a pause longer than this is dead air
PAD = 0.12             # breathing room kept on both sides of every kept run

# --- repeated takes -------------------------------------------------------------------
# Compared over a fixed CHARACTER WINDOW from each card's start, NOT card by card and not
# utterance by utterance. A retake does not respect either boundary: the speaker trails off
# at the end of one breath group and starts the line again at the head of the next, and
# three attempts can land inside one utterance where nothing can compare them against each
# other. Calibrated against a hand-read answer key over all 97 cards of this take:
# threshold 60 catches every repeat that text CAN see, with zero false positives across
# every pair in the file.
WINDOW_CHARS = 18
SIMILARITY = 60
REPEAT_WINDOW = 45.0   # a retake follows its flub closely
MAX_REPEAT_SPAN = 9.0  # never delete more than this between a flub and its retake
LOOKBACK = 10          # cards
UTTERANCE_GAP = 0.8    # cards separated by more than this are different utterances
MIN_CARD_AFTER_CUT = 0.30   # a card left with less than this after the cut is a flash

# Flagged but NOT cut. Deleting real content is worse than leaving a repeat in, so
# anything in this band is reported for the user to judge instead of being removed.
SUSPECT_SIMILARITY = 48

# Mic-test counting and its ASR manglings ("หนึ่ง สอง สาม" comes back as นี่สองซ่าม /
# นี่สิงห์สองซั่ม / นี่สองทราม / 123). Per-video: pass your own list if a clip differs.
JUNK_PATTERNS = (
    r"^\d+$",                       # bare digits — counting
    # "สอง" followed by whatever the model made of "สาม". Every clip mangles it
    # differently (ซ่าม / ซั่ม / ทราม in one take, ซ่ำ / ทรัพย์ in the next), so match the
    # stable part and allow the tail to vary.
    r"สอง\s*(ซ่าม|ซั่ม|ซ่ำ|ซ้ำ|ทราม|ทรัพย์|สาม|ซาม|ซัม|ซำ)",
    r"^เอาอยู่แล้ว$",
    r"หนึ่ง\s*สอง",          # counting, however the rest of it came out
    # Once the captions have been rewritten to numerals the mic test reads literally as
    # "1 2 3", sometimes with a stray word stuck on the end of it.
    r"^\s*1\s*2\s*3\b",
    r"^[\d\s]+$",
)


@dataclass
class Utterance:
    start: float
    end: float
    text: str
    cards: list = field(default_factory=list)


@dataclass
class CutReport:
    source_dur: float
    kept_dur: float
    silence_removed: float
    repeats_removed: float
    junk_removed: float = 0.0
    dropped_utterances: list = field(default_factory=list)
    suspects: list = field(default_factory=list)
    junk: list = field(default_factory=list)

    @property
    def removed(self) -> float:
        return self.source_dur - self.kept_dur

    def lines(self) -> list[str]:
        pct = self.removed / self.source_dur * 100 if self.source_dur else 0
        out = [f"source {self.source_dur:.1f}s -> kept {self.kept_dur:.1f}s "
               f"(cut {self.removed:.1f}s, {pct:.0f}%)",
               f"  dead air removed  {self.silence_removed:.1f}s",
               f"  mic-test / junk   {self.junk_removed:.1f}s ({len(self.junk)} cards)",
               f"  repeat takes cut  {self.repeats_removed:.1f}s "
               f"({len(self.dropped_utterances)} takes)"]
        for c, keeper, s in self.dropped_utterances:
            out.append(f"    {c['start']:7.2f} -> {keeper:7.2f}  score {s:4.0f}  "
                       f"{c['text'][:38]!r}")
        if self.suspects:
            # plain ASCII: this prints to a cp874 console that cannot encode emoji
            out.append(f"  [REVIEW] NOT cut, {len(self.suspects)} borderline pairs - text "
                       "similarity too weak to delete content on")
            for a, b, s in self.suspects:
                out.append(f"    {a['start']:7.2f} ~ {b['start']:7.2f}  score {s:4.0f}  "
                           f"{a['text'][:26]!r} ~ {b['text'][:26]!r}")
        return out


def group_utterances(cards: list[dict], gap: float = UTTERANCE_GAP) -> list[Utterance]:
    """Cards close together are one spoken sentence; a real pause starts a new one."""
    out: list[Utterance] = []
    for c in cards:
        if out and c["start"] - out[-1].end <= gap:
            u = out[-1]
            u.end = c["end"]
            u.text += c["text"]
            u.cards.append(c)
        else:
            out.append(Utterance(c["start"], c["end"], c["text"], [c]))
    return out


def _stutters(t: str, min_unit: int = 3, cover: float = 0.65) -> bool:
    """Is this card mostly one chunk said back-to-back?

    The gap-fill pass decodes short spans with the anti-repeat guard off, which is how
    it hears retakes — but it also lets stutter through: เน็ตเน็ตเน็ต, ข้อมูลข้อมูล,
    บรรยากาศบรรยากาศ. Normal Thai does not repeat a 3+ character run immediately; it uses ๆ.

     is deliberately high. At 0.4 this also removed cards where the stutter was
    stuck onto REAL narration ('ของเนยนมไข่บรรยากาศบรรยากาศ'), and dropping the card drops
    its audio too — losing content is worse than leaving an ugly caption the user can
    retype. Only cards that are almost entirely stutter are cut.
    """
    n = len(t)
    for u in range(min_unit, n // 2 + 1):
        for i in range(0, n - 2 * u + 1):
            unit = t[i:i + u]
            reps = 1
            j = i + u
            while t[j:j + u] == unit:
                reps += 1
                j += u
            if reps >= 2 and (reps * u) / n >= cover:
                return True
    return False


def is_junk(text: str, patterns=JUNK_PATTERNS) -> bool:
    """Mic-test counting and the like: audible, transcribed, and worth nothing."""
    t = text.strip()
    return any(re.search(p, t) for p in patterns) or _stutters(t)


def _keeper_is_complete(cards, offset, text, hit, slack: float = 0.9) -> bool:
    """Would this cut throw away the FULLER version of the line?

    'Keep the last take' assumes the retake is the good one. In this take it often is not:
    the speaker restarts and trails off, so the later attempt is shorter. Cutting then
    deletes the complete sentence and leaves the fragment — 'ไม่ได้แตะมากกว่า | แหมแบบนี้'
    with '14 ปีรวด' gone. Only cut when what survives is at least as long as what goes.
    """
    i, j, _ = hit
    # CARD-ALIGNED on both sides. Slicing the keeper as `len(dropped)` characters of the
    # flat stream always yields exactly that many characters — the check could never fail.
    # Comparing the same NUMBER OF CARDS is what makes the lengths differ.
    k = min(j + (j - i), len(cards))
    dropped = text[offset[i]:offset[j]]
    kept = text[offset[j]:offset[k]] if k < len(offset) else text[offset[j]:]
    return len(kept.strip()) >= slack * len(dropped.strip())


def find_repeats(cards: list[dict], similarity: int = SIMILARITY,
                 window: float = REPEAT_WINDOW, suspect: int = SUSPECT_SIMILARITY
                 ) -> tuple[list[tuple[int, int, float]], list[tuple[int, int, float]]]:
    """Find `...X | X...` — a take restarted a few seconds later.

    Returns (cuts, suspects) as (from_card, to_card, score): everything from the start of
    `from_card` up to the start of `to_card` is a discarded attempt. Suspects score in the
    grey band and are reported, never cut.
    """
    stream, offset, pos = [], [], 0
    for c in cards:
        offset.append(pos)
        stream.append(c["text"])
        pos += len(c["text"])
    text = "".join(stream)

    def win(i: int) -> str:
        return text[offset[i]:offset[i] + WINDOW_CHARS]

    cuts, suspects = [], []
    for j in range(1, len(cards)):
        best = None
        for i in range(max(0, j - LOOKBACK), j):
            if cards[j]["start"] - cards[i]["start"] > window:
                continue
            a, b = win(i), win(j)
            # Both windows must be FULL. Half a window was allowed once and short cards
            # started matching each other on nothing — a lone 'Vegan' was called a repeat
            # of the 'Vegan' 0.33 s later. Short cards carry too little to judge.
            if min(len(a), len(b)) < WINDOW_CHARS:
                continue
            # A retake follows its flub closely. Without a cap the pair can be 9 s apart
            # and the cut swallows all the real content in between.
            if cards[j]["start"] - cards[i]["start"] > MAX_REPEAT_SPAN:
                continue
            s = fuzz.ratio(a, b)
            if best is None or s > best[2]:
                best = (i, j, s)
        if best and best[2] >= similarity and _keeper_is_complete(cards, offset, text, best):
            cuts.append(best)
        elif best and best[2] >= suspect:
            suspects.append(best)
    return cuts, suspects


def _merge_spans(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _subtract(keeps: list[tuple[float, float]],
              holes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    for hs, he in holes:
        nxt = []
        for ks, ke in keeps:
            if he <= ks or hs >= ke:
                nxt.append((ks, ke))
                continue
            if ks < hs:
                nxt.append((ks, hs))
            if he < ke:
                nxt.append((he, ke))
        keeps = nxt
    return keeps


def plan(mask, cards: list[dict], *, min_silence: float = MIN_SILENCE, pad: float = PAD,
         similarity: int = SIMILARITY, drop_repeats: bool = True,
         start_floor: float = 0.0, start_at: float = 0.0,
         dead_spans: list | None = None
         ) -> tuple[list[tuple[float, float]], CutReport]:
    """Build the keep list. `start_floor` clips the plan to where the camera exists."""
    dur = mask.duration

    # ---- pass 1: dead air
    voiced = mask.voiced_spans(0.0, dur)
    keeps: list[tuple[float, float]] = []
    for s, e in voiced:
        s, e = max(0.0, s - pad), min(dur, e + pad)
        if keeps and s - keeps[-1][1] <= min_silence:
            keeps[-1] = (keeps[-1][0], max(keeps[-1][1], e))   # gap too short to bother
        else:
            keeps.append((s, e))
    silence_removed = dur - sum(e - s for s, e in keeps)

    # ---- pass 2: mic-test counting and other transcribed noise
    before = sum(e - s for s, e in keeps)
    junk = [c for c in cards if is_junk(c["text"])]
    keeps = _subtract(keeps, _merge_spans([(c["start"] - pad, c["end"] + pad) for c in junk]))
    junk_removed = before - sum(e - s for s, e in keeps)

    # ---- pass 3: repeated takes
    dropped, suspects = ([], [])
    if drop_repeats:
        dropped, suspects = find_repeats(cards, similarity)
    before = sum(e - s for s, e in keeps)
    keeps = _subtract(keeps, _merge_spans(
        [(cards[i]["start"] - pad, cards[j]["start"] - pad) for i, j, _ in dropped]))
    repeats_removed = before - sum(e - s for s, e in keeps)

    # ---- pass 3b: audio no caption can ever be written for (mic-test counting that came
    # back degenerate from its own decode). Captioned or cut, never neither.
    if dead_spans:
        before = sum(e - s for s, e in keeps)
        keeps = _subtract(keeps, _merge_spans([(a - pad, b + pad) for a, b in dead_spans]))
        junk_removed += before - sum(e - s for s, e in keeps)

    # ---- optional hard head trim: the user says where the content actually begins
    if start_at:
        before = sum(e - s for s, e in keeps)
        keeps = [(max(s, start_at), e) for s, e in keeps if e > start_at]
        junk_removed += before - sum(e - s for s, e in keeps)

    # ---- the camera did not exist before start_floor, so nothing there can be kept
    keeps = [(max(s, start_floor), e) for s, e in keeps if e > start_floor]
    keeps = [(s, e) for s, e in keeps if e - s > 0.05]

    return keeps, CutReport(dur, sum(e - s for s, e in keeps), silence_removed,
                            repeats_removed, junk_removed,
                            [(cards[i], cards[j]["start"], s) for i, j, s in dropped],
                            [(cards[i], cards[j], s) for i, j, s in suspects], junk)


def remap(t: float, keeps: list[tuple[float, float]]) -> float | None:
    """Source time -> timeline time. None if that moment was cut out."""
    acc = 0.0
    for s, e in keeps:
        if t < s:
            return None
        if t <= e:
            return acc + (t - s)
        acc += e - s
    return None


def remap_cards(cards: list[dict], keeps: list[tuple[float, float]]) -> list[dict]:
    """Move card times onto the cut timeline, clipping cards that straddle a cut."""
    out = []
    for c in cards:
        seg_start = seg_end = None
        acc = 0.0
        for s, e in keeps:
            lo, hi = max(c["start"], s), min(c["end"], e)
            if hi > lo:
                a, b = acc + (lo - s), acc + (hi - s)
                seg_start = a if seg_start is None else seg_start
                seg_end = b
            acc += e - s
        # A card whose audio was mostly cut away leaves a sliver. Below this it is a
        # one-frame flash nobody can read, so it is not worth a segment.
        if seg_start is not None and seg_end - seg_start >= MIN_CARD_AFTER_CUT:
            out.append({"start": seg_start, "end": seg_end, "text": c["text"]})
    return out
