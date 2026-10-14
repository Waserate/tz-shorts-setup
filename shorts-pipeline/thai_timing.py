"""Give every Thai word a start/end time, then time the subtitle cards.

The problem: Whisper's `word_timestamps` are timings for BPE sub-tokens, which for a
script with no spaces do not line up with Thai words at all. PyThaiNLP knows where the
words are but nothing about the audio.

The bridge: build a character -> time map from Whisper's pieces, then look up each
PyThaiNLP word by its character span. Word identity comes from PyThaiNLP, timing comes
from the audio, and neither has to know about the other.

This deliberately avoids MMS/ctc-forced-aligner: its default checkpoint is CC-BY-NC-4.0,
which does not permit the monetised use this pipeline is for.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass

from thai_subtitle import Card, chunk_words, split_sentences, tokenize


@dataclass
class TimedWord:
    text: str
    start: float
    end: float


# A Thai character takes roughly 0.05-0.25 s of speech. Whisper hands back pieces like
# ('้', 5.44, 11.28) — a single tone mark holding 5.8 s — because it swallows the
# following silence into the piece rather than reporting a gap. Clamping the piece
# makes that silence visible as a gap, which is what card splitting keys off.
MAX_PIECE_DUR = 0.5

# Tone marks and the above/below vowels are written on top of the preceding consonant
# and take NO time to say, so they must not buy a word more clamp budget. Counting them
# let ทั้งที่ (3 spoken characters, 7 code points) claim 2.05 s and hold a card on screen
# for 4.31 s across a 2.8 s pause.
_SILENT_MARKS = set("ั") | set(map(chr, range(0x0E34, 0x0E3B))) | \
                set(map(chr, range(0x0E47, 0x0E4F)))


def spoken_len(text: str) -> int:
    """Characters that actually cost time to pronounce."""
    return max(1, sum(1 for c in text if c not in _SILENT_MARKS))


class CharClock:
    """Maps a character offset in the transcript to a time in the audio.

    With a `SpeechMask`, characters advance through **voiced time only**: the silence
    Whisper swallowed into a piece is stepped over rather than written on, so text lands
    where the speaking is. Without one, fall back to the character-count clamp — it is
    blind (see ERRORS E13) but needs no audio, which keeps the chunker tests offline.
    """

    def __init__(self, pieces: list[tuple[str, float, float]], mask=None):
        """pieces: (text, start, end) straight from Whisper, in order."""
        self.text = ""
        self.mask = mask
        self._starts: list[int] = []      # char offset where each piece begins
        self._spans: list[list[tuple[float, float]]] = []   # voiced runs per piece
        for txt, st, en in pieces:
            if not txt:
                continue
            self._starts.append(len(self.text))
            self._spans.append(self._runs(txt, st, en))
            self.text += txt
        self._ends = self._starts[1:] + [len(self.text)]

    def _runs(self, txt: str, st: float, en: float) -> list[tuple[float, float]]:
        budget = MAX_PIECE_DUR * spoken_len(txt.strip())
        if self.mask is None:
            return [(st, min(en, st + budget))]
        if en - st > budget:
            # Whisper dumped the audio BEFORE this character into it: ('จ', 71.19, 73.17)
            # is one consonant holding 1.98 s, and the 'จ' sound is at 73.14. The piece's
            # END is trustworthy — the next piece pins it — but its START is not. So the
            # characters belong to the voiced run the END sits in, not to whatever was
            # being said two seconds earlier.
            st = max(st, self.mask.run_start_at(en, floor=max(st, en - budget)))
        runs = self.mask.voiced_spans(st, en)
        if not runs:
            # Whisper heard something here but the waveform is silent: give the piece a
            # token width rather than zero, so char offsets stay strictly increasing.
            return [(st, min(en, st + 0.05))]
        return runs

    def _piece_at(self, ci: int) -> int:
        i = bisect.bisect_right(self._starts, ci) - 1
        return max(0, min(i, len(self._spans) - 1))

    def time_at(self, ci: int, *, end: bool = False) -> float:
        """Time of character index ci, interpolating across the piece's voiced runs."""
        if not self._spans:
            return 0.0
        i = self._piece_at(ci)
        runs = self._spans[i]
        lo, hi = self._starts[i], self._ends[i]
        n = max(1, hi - lo)
        frac = ((ci - lo) + (1 if end else 0)) / n
        frac = min(1.0, max(0.0, frac))
        want = frac * sum(e - s for s, e in runs)
        for s, e in runs:
            if want <= e - s:
                return s + want
            want -= e - s
        return runs[-1][1]


def words_with_times(pieces: list[tuple[str, float, float]], custom_dict=None,
                     mask=None) -> list[TimedWord]:
    """Whisper pieces -> Thai words carrying real timings."""
    clock = CharClock(pieces, mask=mask)
    out: list[TimedWord] = []
    cursor = 0
    for sent in split_sentences(clock.text):
        for w in tokenize(sent, custom_dict=custom_dict):
            idx = clock.text.find(w, cursor)
            if idx < 0:                      # tokenizer normalised something away
                idx = cursor
            st = clock.time_at(idx)
            en = clock.time_at(idx + len(w) - 1, end=True)
            # A pause can also sit INSIDE one word (ให้ = pieces 'ให' + '้' with 2 s of
            # silence between them), which a word-to-word gap check can never see.
            if mask is None:
                # blind fallback: bound the word by what speech physically takes
                en = min(en, st + 0.25 * spoken_len(w) + 0.30)
            else:
                sil = mask.first_silence(st, en, GAP_SPLIT)
                if sil is not None:
                    en = min(en, sil[0])     # the word stops where the speaking stops
            out.append(TimedWord(w, st, max(en, st + 0.06)))
            cursor = idx + len(w)
    return out


# A card must never outlast the sentence being spoken — if the text needs more room it
# becomes a NEW card instead. Matched to the dead-air threshold in cut_plan: a pause that
# long is going to be CUT, so a card must never have been built across one in the first
# place. (Was 0.55 s, which let cards straddle pauses that later got removed.)
GAP_SPLIT = 0.35
MAX_CARD_DUR = 4.0   # a card on screen longer than this is a bug, not a style choice
MAX_OVERRUN = 0.20   # tolerance for a card still up after the speaking stopped


def _split_on_gaps(words: list[TimedWord]) -> list[list[TimedWord]]:
    """Chunking was purely textual, so a card could span a pause and sit on screen for
    11 seconds. Words on opposite sides of a silence are never the same card."""
    runs, cur = [], []
    for w in words:
        if cur and w.start - cur[-1].end > GAP_SPLIT:
            runs.append(cur)
            cur = []
        cur.append(w)
    if cur:
        runs.append(cur)
    return runs


def _split_on_sentences(words: list[TimedWord]) -> list[list[TimedWord]]:
    text = "".join(w.text for w in words)
    blocks, i = [], 0
    for sent in split_sentences(text):
        n, consumed = 0, 0
        while i + n < len(words) and consumed < len(sent):
            consumed += len(words[i + n].text)
            n += 1
        if n:
            blocks.append(words[i:i + n])
            i += n
    if i < len(words):
        blocks.append(words[i:])
    return blocks


def cards_with_times(pieces: list[tuple[str, float, float]], custom_dict=None,
                     min_dur: float = 0.45, gap: float = 0.02, mask=None) -> list[Card]:
    """Full pipeline: audio pieces -> timed, correctly-chunked subtitle cards."""
    timed = words_with_times(pieces, custom_dict=custom_dict, mask=mask)
    if not timed:
        return []

    cards: list[Card] = []
    for run in _split_on_gaps(timed):
        for block in _split_on_sentences(run):
            rest = block
            for group in chunk_words([w.text for w in block]):
                chunk, rest = rest[:len(group)], rest[len(group):]
                if chunk:
                    cards.append(Card(words=[w.text for w in chunk],
                                      start=chunk[0].start, end=chunk[-1].end))
    if mask is not None:
        # A card with no speech inside it is captioning silence. This is where Whisper's
        # stray tokens end up — a lone '1' from the mic-test counting parked in a 3 s gap,
        # a bare 'ก็' in a pause — and nothing anchors them, so they surface 1-3 s before
        # the words they claim to be. There is no correct time for text nobody said.
        cards = [c for c in cards if mask.voiced_duration(c.start, c.end) > 0.0]
        if not cards:
            return []
    _tidy(cards, min_dur, gap, mask)
    assert_timing_sane(cards)
    if mask is not None:
        assert_no_overrun(cards, mask)
    return cards


def _tidy(cards: list[Card], min_dur: float, gap: float, mask=None) -> None:
    """Enforce readability: no zero-length card, no overlap, monotonic order."""
    for i, c in enumerate(cards):
        if c.end - c.start < min_dur:
            c.end = c.start + min_dur
        if mask is not None:
            # Never leave a card up once the talking has stopped. Bounding it by the END
            # of a single run was too strict — a sentence can contain a 0.2 s pause and
            # the card should ride over it; what it must not do is sit there in silence.
            c.end = max(mask.last_voiced_before(c.end, floor=c.start + 0.15), c.start + 0.15)
        # A few cards land on a long VOICED stretch that Whisper barely transcribed —
        # 3 words over 4.4 s of continuous speech. The start is right, so keep it and cap
        # how long the card sits on screen; the untranscribed remainder gets no caption
        # because there is no text for it, not because the timing is wrong.
        c.end = min(c.end, c.start + MAX_CARD_DUR)
        if i + 1 < len(cards):
            nxt = cards[i + 1]
            if c.end > nxt.start - gap:
                c.end = max(c.start + 0.15, nxt.start - gap)


class TimingError(AssertionError):
    pass


def assert_timing_sane(cards: list[Card]) -> None:
    """CapCut forbids overlapping segments on a text track; catch it here, loudly."""
    prev_end = -1.0
    for c in cards:
        if c.start is None or c.end is None:
            raise TimingError(f"untimed card: {c!r}")
        if c.end <= c.start:
            raise TimingError(f"non-positive duration: {c!r}")
        if c.start < prev_end:
            raise TimingError(f"overlapping cards near {c!r} (prev end {prev_end:.3f})")
        if c.end - c.start > MAX_CARD_DUR + 0.01:
            raise TimingError(
                f"card on screen {c.end - c.start:.2f}s (>{MAX_CARD_DUR}s): {c!r} — "
                "it is spanning a pause instead of being split at it")
        prev_end = c.end


def assert_no_overrun(cards: list[Card], mask, tol: float = MAX_OVERRUN) -> None:
    """The user's rule, as an invariant: a card may not stay up after the sentence ends.

    Kept as an assertion rather than a test because the failure is silent and only visible
    by watching the video — exactly the kind of thing that ships if nothing crashes.
    """
    for c in cards:
        spoke_until = mask.last_voiced_before(c.end, floor=c.start)
        if c.end > spoke_until + tol:
            raise TimingError(
                f"card outlasts its sentence by {c.end - spoke_until:.2f}s "
                f"(ends {c.end:.2f}, speaking stopped {spoke_until:.2f}): {c!r}")


def to_srt(cards: list[Card], path: str) -> None:
    import pysubs2
    subs = pysubs2.SSAFile()
    for c in cards:
        subs.append(pysubs2.SSAEvent(start=pysubs2.make_time(s=c.start),
                                     end=pysubs2.make_time(s=c.end), text=c.text))
    subs.save(path, encoding="utf-8", format_="srt")   # CapCut requires UTF-8
