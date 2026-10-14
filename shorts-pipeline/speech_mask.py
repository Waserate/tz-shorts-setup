"""Where in the audio is somebody actually speaking?

Whisper's Thai `word_timestamps` are per-character and its DTW parks silence wherever it
likes: one code point can be handed a 5.7 s span that is 71 % real speech, and another can
be handed 3 s that is nearly all pause. A character-count clamp cannot tell those two
apart — it truncated 18.4 s of real speech out of the card timeline while trying to stop
an 11 s subtitle (ERRORS E10/E13).

The audio itself can tell them apart. This builds a boolean speech mask straight off the
waveform, and the timing code uses it to decide where a piece's time was really spent.

Reads the clean mic track only, never a mixed timeline, so "energy" means "the narrator",
not music or B-roll.
"""
from __future__ import annotations

import numpy as np

SR = 8000          # plenty for an energy envelope, and cheap to decode
HOP = 0.02         # 20 ms frames


class SpeechMask:
    """Boolean speech/silence per 20 ms frame, with the helpers the timing code needs."""

    def __init__(self, audio_path: str, *, level: float = 0.45,
                 close_gap: float = 0.20, pad: float = 0.06):
        from faster_whisper.audio import decode_audio      # PyAV; there is no ffmpeg here

        x = decode_audio(audio_path, sampling_rate=SR).astype(np.float64)
        n = int(len(x) / SR / HOP)
        rms = np.sqrt(np.array([
            np.mean(x[int(i * HOP * SR):int((i + 1) * HOP * SR)] ** 2) for i in range(n)
        ]) + 1e-12)
        db = 20 * np.log10(rms)

        # Threshold relative to this recording's own floor and loud level, so it does not
        # depend on how hot the mic was set. Absolute dB would need retuning per video.
        floor, loud = np.percentile(db, 10), np.percentile(db, 90)
        self.threshold_db = floor + level * (loud - floor)
        m = db > self.threshold_db

        # A stop consonant is a 40 ms silence in the middle of a word. Close short holes
        # first, so only real pauses survive, then pad the edges back out a little: a word
        # onset ramps up through the threshold, so the mask always starts slightly late.
        m = _close(m, int(round(close_gap / HOP)))
        m = _dilate(m, int(round(pad / HOP)))

        self.frames = m
        self.n = n
        self.duration = n * HOP

    # ---- frame helpers -------------------------------------------------------

    def _idx(self, t: float) -> int:
        return max(0, min(self.n - 1, int(t / HOP)))

    def is_speech(self, t: float) -> bool:
        return bool(self.frames[self._idx(t)])

    def voiced_spans(self, a: float, b: float) -> list[tuple[float, float]]:
        """The [start, end) stretches of real speech inside [a, b)."""
        i, j = self._idx(a), max(self._idx(a), min(self.n, int(b / HOP)))
        out, run = [], None
        for k in range(i, j):
            if self.frames[k] and run is None:
                run = k
            elif not self.frames[k] and run is not None:
                out.append((run * HOP, k * HOP))
                run = None
        if run is not None:
            out.append((run * HOP, j * HOP))
        if out:                              # never report outside the asked-for window
            out[0] = (max(a, out[0][0]), out[0][1])
            out[-1] = (out[-1][0], min(b, out[-1][1]))
        return [(s, e) for s, e in out if e > s]

    def voiced_duration(self, a: float, b: float) -> float:
        return sum(e - s for s, e in self.voiced_spans(a, b))

    def run_start_at(self, t: float, floor: float = 0.0) -> float:
        """Start of the voiced run that `t` sits in (or the one just before it).

        Used to anchor a piece whose reported start Whisper cannot be trusted on: the
        characters belong to the run their END falls in, not to whatever was being said
        two seconds earlier.
        """
        i = self._idx(t)
        while i > 0 and not self.frames[i]:
            i -= 1
        while i > 0 and self.frames[i - 1]:
            i -= 1
        return max(floor, i * HOP)

    def run_end_at(self, t: float, ceiling: float | None = None) -> float:
        """End of the voiced run `t` belongs to — where a card has to be gone by.

        If `t` lands in silence the run it belongs to is the one AHEAD of it (a card can
        start a fraction early, it can never belong to a sentence already finished), so
        search forward. Searching backward here reported a run end BEFORE the card even
        started and made the overrun check nonsense.
        """
        i = self._idx(t)
        while i < self.n and not self.frames[i]:
            i += 1
        if i >= self.n:
            return self.duration
        while i + 1 < self.n and self.frames[i + 1]:
            i += 1
        e = (i + 1) * HOP
        return min(e, ceiling) if ceiling is not None else e

    def last_voiced_before(self, t: float, floor: float = 0.0) -> float:
        """Last moment at or before `t` that anybody was speaking.

        This is the honest bound on a card's end: it may span a short pause inside a
        sentence, but it may not still be up once the talking has stopped.
        """
        i = self._idx(t)
        while i > 0 and not self.frames[i]:
            i -= 1
        if not self.frames[i]:
            return floor
        return max(floor, min(t, (i + 1) * HOP))

    def first_silence(self, a: float, b: float, min_len: float) -> tuple[float, float] | None:
        """First pause of at least min_len inside [a, b) — where a word's span really ends."""
        spans = self.voiced_spans(a, b)
        prev = a
        for s, e in spans:
            if s - prev >= min_len:
                return (prev, s)
            prev = e
        if b - prev >= min_len:
            return (prev, b)
        return None


def _close(m: np.ndarray, k: int) -> np.ndarray:
    """Fill silence runs shorter than k frames."""
    if k <= 0:
        return m
    out = m.copy()
    i = 0
    while i < len(m):
        if not m[i]:
            j = i
            while j < len(m) and not m[j]:
                j += 1
            if i > 0 and j < len(m) and (j - i) < k:
                out[i:j] = True
            i = j
        else:
            i += 1
    return out


def _dilate(m: np.ndarray, k: int) -> np.ndarray:
    if k <= 0:
        return m
    out = m.copy()
    for s in range(1, k + 1):
        out[s:] |= m[:-s]
        out[:-s] |= m[s:]
    return out
