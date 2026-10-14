"""Thai subtitle card chunker.

Goal: cards of 3-5 Thai words that read naturally — never break a word, never break a
Thai Character Cluster, never strand a connector at a card edge, prefer sentence ends.

Approach: dynamic programming over the word sequence, minimising a cost that encodes
"what a Thai reader would find awkward". Greedy left-to-right chunking is what produces
the classic ugly result (a lone orphan word at the end of every sentence), so we don't
use it.

Word identity always comes from PyThaiNLP, never from an ASR tokenizer — Whisper's BPE
pieces are not Thai words.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from pythainlp.tokenize import word_tokenize, sent_tokenize, subword_tokenize
from pythainlp.corpus import thai_words
from pythainlp.util import Trie

_THAI_VOCAB = None


def _vocab():
    global _THAI_VOCAB
    if _THAI_VOCAB is None:
        _THAI_VOCAB = set(thai_words())
    return _THAI_VOCAB


def build_dict(custom_terms=()):
    """Per-video vocabulary: proper nouns, streamer/game names, places.

    This is the single highest-leverage knob for this channel's content, which is
    dense with names the base dictionary has never seen.
    """
    return Trie(set(thai_words()) | set(custom_terms))

MIN_WORDS = 3
MAX_WORDS = 6
HARD_MAX = 8          # never exceed, even if the cost says so
MIN_CHARS = 8         # a very short card looks like a stutter on screen
MAX_CHARS = 26        # vertical Short at text size 22; 24 breaks a golden case

# GLUE: relational markers. They join a left thing to a right thing, so BOTH things
# belong on the same card — these must sit INSIDE a card, never at either edge.
# (Getting this wrong is what produced "โยนบาป | ให้เกมหลังเกิด": ให้ was only banned
#  from the card end, so it jumped to the head of the next card and split the verb
#  from its object.)
GLUE = {
    "ให้", "ของ", "ใน", "บน", "กับ", "แก่", "ต่อ", "จาก", "โดย", "เพื่อ",
    "ที่", "ซึ่ง", "แบบ", "ตาม", "เรื่อง",
}

# OPENERS: start a new phrase, so a card should not END on them.
OPENERS = {
    "หลัง", "ก่อน", "ตอน", "ระหว่าง", "เมื่อ", "พอ", "จน", "จนกระทั่ง", "เพราะ",
    "เนื่องจาก", "ดังนั้น", "แต่", "และ", "หรือ", "ถ้า", "หาก", "ทั้ง", "ส่วน",
    "ก็", "จะ", "คือ", "เป็น", "การ", "ความ", "ยัง", "ต้อง", "ไม่", "มี",
}

# CLOSERS: lean back on what precedes, so a card should not START on them.
CLOSERS = {
    "ครับ", "ค่ะ", "คะ", "นะ", "น่ะ", "ล่ะ", "ละ", "เลย", "แล้ว", "อยู่", "ด้วย",
    "ไหม", "มั้ย", "หรอ", "เหรอ", "จ้า", "สิ", "เนี่ย", "เนี้ย", "นี่", "นั้น", "นี้",
    "กัน", "ๆ", "ได้", "ไป", "มา", "อีก",
}

NO_END = GLUE | OPENERS
NO_START = GLUE | CLOSERS


# --- pairs that must never be split across two cards ------------------------
QUANTIFIERS = {"หลาย", "ทุก", "บาง", "แต่ละ", "ทั้ง", "อีก", "สอง", "สาม", "สี่", "ห้า",
               "หนึ่ง", "กี่", "หลาย ๆ", "ล้าน", "พัน", "หมื่น", "แสน", "ร้อย", "สิบ"}
CLASSIFIERS = {"คน", "อัน", "ตัว", "ที่", "ครั้ง", "อย่าง", "เรื่อง", "แห่ง", "ชิ้น",
               "ประเทศ", "ปี", "วัน", "เดือน", "บาท", "เท่า", "ข้อ", "ราย"}
NEGATORS = {"ไม่", "มิ", "ยัง"}
INDEFINITE = {"ใคร", "อะไร", "ไหน", "ใด", "ไร"}
POSSESSIVE_HEADS = {"บ้าน", "พวก", "ของ", "ฝ่าย", "ทาง"}
PRONOUNS = {"เรา", "เขา", "มัน", "ผม", "ฉัน", "คุณ", "ท่าน", "ตัวเอง"}


def _is_thai(tok: str) -> bool:
    return any("฀" <= ch <= "๿" for ch in tok)


def _must_bind(a: str, b: str) -> bool:
    """True if tokens a,b form a unit a Thai reader would not want split."""
    if a in QUANTIFIERS and b in CLASSIFIERS:
        return True
    if a in NEGATORS:
        return True
    if a in POSSESSIVE_HEADS and b in PRONOUNS:
        return True
    if b == "ๆ":
        return True
    if a in PREFIXES:
        return True
    if (a, b) in COMPOUNDS:
        return True
    if b in INDEFINITE:
        return True
    if a == b:
        return True        # Thai reduplication: จริงจริง, ลอยลอย, เพื่อนเพื่อน
    # fragments of a name the tokenizer failed on: glue unknown Thai pieces together
    v = _vocab()
    if _is_thai(a) and _is_thai(b) and (a not in v or b not in v):
        if a not in v and b not in v:
            return True
        # a known word + an unknown fragment is usually a broken proper noun
        if (a not in v and len(a) <= 4) or (b not in v and len(b) <= 4):
            return True
    return False


MAX_UNIT_WORDS = 4   # bind rules chain; without a cap they fuse a whole clause


def merge_units(words: list[str]) -> list[list[str]]:
    """Group the word list into units that must stay on the same card.

    Capped: each rule is individually right, but applied greedily they chain
    (ล้าน+ล้าน+คน+หลาย+คน+เนี่ย) into one unbreakable blob that then blows past the
    card size limit. A unit is a phrase fragment, not a clause.
    """
    if not words:
        return []
    units = [[words[0]]]
    for w in words[1:]:
        cur = units[-1]
        joined = "".join(cur)
        bind = _must_bind(cur[-1], w) or (joined, w) in COMPOUNDS
        if bind and len(cur) < MAX_UNIT_WORDS:
            cur.append(w)
        else:
            units.append([w])
    return units


@dataclass
class Card:
    words: list[str]
    start: float | None = None
    end: float | None = None

    @property
    def text(self) -> str:
        return "".join(self.words).strip()

    def __repr__(self):
        t = f" [{self.start:.2f}-{self.end:.2f}]" if self.start is not None else ""
        return f"Card({len(self.words)}w{t}: {self.text!r})"


def tokenize(text: str, engine: str = "newmm", custom_dict=None) -> list[str]:
    """Thai words, whitespace-only tokens dropped."""
    kw = {"engine": engine, "keep_whitespace": False}
    if custom_dict is not None:
        kw["custom_dict"] = custom_dict
    try:
        toks = word_tokenize(text, **kw)
    except Exception:
        toks = word_tokenize(text, engine="newmm", keep_whitespace=False)
    return [t for t in toks if t.strip()]


def split_sentences(text: str) -> list[str]:
    try:
        return [s for s in sent_tokenize(text, engine="crfcut") if s.strip()]
    except Exception:
        return [text]


# ---------------------------------------------------------------- break cost
# Hand-written word lists can never cover Thai compounds (they split สื่อ|ใหญ่ and
# โยน|บาป). Part-of-speech of the two words either side of a candidate break is the
# general signal: some tags bind forward, some bind backward, some open a new phrase.

# ว่า/ๆ close a clause: never start a card with them, and cutting right after is ideal
CLAUSE_CLOSERS = {"ว่า"}
# productive Thai prefixes — always glued to the word that follows
PREFIXES = {"ชาว", "นัก", "ผู้", "ช่าง", "เจ้า", "ความ", "การ", "คน", "ทาง", "ฝ่าย"}
# lexicalised compound verbs where ให้ binds BACKWARD, unlike โยนบาป|ให้|เกม
COMPOUNDS = [("ทำ", "ให้"), ("แต่", "ว่า"), ("เพราะ", "ว่า"), ("ถึง", "แม้"),
             ("แม้", "ว่า"), ("เนื่อง", "จาก"), ("ทั้ง", "ที่"), ("ไม่ว่า", "จะ"),
             ("ไม่", "ว่า"), ("หรือ", "ว่า"), ("แม้", "แต่")]

BINDS_FORWARD = {"ADP", "DET", "NUM", "AUX", "PART", "CCONJ", "SCONJ"}   # never break AFTER
BINDS_BACKWARD = {"ADJ", "PART"}                                        # never break BEFORE
PHRASE_OPENERS_POS = {"CCONJ", "SCONJ"}                                 # nice place to break


def pos_of(words: list[str]) -> list[str]:
    try:
        from pythainlp.tag import pos_tag
        return [t for _, t in pos_tag(words, engine="perceptron", corpus="orchid_ud")]
    except Exception:
        return ["X"] * len(words)


def break_cost(lw: str, lt: str, rw: str, rt: str) -> float:
    """Cost of cutting a card between word lw (tag lt) and word rw (tag rt)."""
    # a clause closer ends its card; the next clause starts clean on the next one
    if lw in CLAUSE_CLOSERS:
        return -4.0
    if rw in CLAUSE_CLOSERS:
        return 14.0
    if lw in PREFIXES:
        return 14.0
    if lw in OPENERS:
        return 12.0        # a card must not END on a word that opens the next phrase
    # explicit relational markers dominate: they must sit inside a card
    if lw in GLUE or rw in GLUE:
        return 14.0
    if rw in CLOSERS:
        return 12.0
    # a phrase opener is exactly where we WANT the break, even if it's an ADP
    if rw in OPENERS:
        return -3.0
    if rt in PHRASE_OPENERS_POS:
        return -2.0

    cost = 0.0
    if lt in BINDS_FORWARD:
        cost += 10.0          # ใน|โรงเรียน , หลาย|เจ้า
    if rt in BINDS_BACKWARD:
        cost += 10.0          # สื่อ|ใหญ่
    if lt == "VERB" and rt in ("NOUN", "PROPN"):
        cost += 6.0           # โยน|บาป  (verb + object)
    if lt in ("NOUN", "PROPN") and rt in ("NOUN", "PROPN"):
        cost += 6.0           # noun compound: อาวุธ|ปืน
    if lt == "ADV" and rt == "VERB":
        # the tagger frequently mislabels a Thai verb as ADV (โยน/ADV บาป/VERB),
        # so treat this the same as splitting a verb from its object
        cost += 6.0
    return cost


def _card_cost(units: list[list[str]], is_last: bool) -> float:
    """Lower is better. Encodes what makes a card awkward to read.

    Operates on UNITS (groups that must not split), but the size budget counts real
    words, because that's what the reader perceives.
    """
    words = [w for u in units for w in u]
    n = len(words)
    if n > HARD_MAX:
        return math.inf

    # size: 3-5 free, outside that grows quadratically. A 1-word card is very bad.
    if n < MIN_WORDS:
        cost = (MIN_WORDS - n) ** 2 * 6.0
        if n == 1 and not is_last:
            cost += 12.0
    elif n > MAX_WORDS:
        # a 6-word card that keeps a phrase whole beats a 3+3 split that cuts it,
        # so going over is only mildly discouraged
        cost = (n - MAX_WORDS) ** 2 * 2.0
    else:
        cost = 0.0

    # (edge-word penalties now live in break_cost, which can see BOTH sides of a cut)

    # Screen width, not word count, is what actually overflows a vertical Short.
    # Thai words vary wildly in length, so a 5-word card can still be 45 chars.
    chars = sum(len(w) for w in words)
    if chars > MAX_CHARS:
        cost += (chars - MAX_CHARS) ** 2 * 0.5
    elif chars < MIN_CHARS and not is_last:
        cost += (MIN_CHARS - chars) * 0.8

    # slight preference for the middle of the range
    cost += abs(n - 4) * 0.4
    return cost


def chunk_words(words: list[str]) -> list[list[str]]:
    """Optimal segmentation of ONE sentence into cards (DP, not greedy).

    Breaks are only ever considered at UNIT boundaries, so a bound pair such as
    หลาย+คน or a fragmented proper noun can never land on two different cards.
    """
    units = merge_units(words)
    n = len(units)
    if n == 0:
        return []

    tag_of = pos_of(words)
    # flat index of each unit's first/last word, to look up the POS at a cut
    flat, first_idx, last_idx = 0, [], []
    for u in units:
        first_idx.append(flat)
        flat += len(u)
        last_idx.append(flat - 1)

    def cut_cost(j: int) -> float:
        """Cost of breaking before unit j."""
        if j <= 0 or j >= n:
            return 0.0
        li, ri = last_idx[j - 1], first_idx[j]
        return break_cost(words[li], tag_of[li], words[ri], tag_of[ri])

    INF = math.inf
    best = [INF] * (n + 1)
    back = [0] * (n + 1)
    best[0] = 0.0
    for i in range(1, n + 1):
        for j in range(max(0, i - HARD_MAX), i):
            if best[j] == INF:
                continue
            c = best[j] + _card_cost(units[j:i], is_last=(i == n)) + cut_cost(j)
            if c < best[i]:
                best[i] = c
                back[i] = j

    cards, i = [], n
    while i > 0:
        j = back[i]
        cards.append([w for u in units[j:i] for w in u])
        i = j
    cards.reverse()
    return cards


def chunk_text(text: str, engine: str = "newmm", custom_dict=None) -> list[Card]:
    """Full text -> subtitle cards, respecting sentence boundaries."""
    cards: list[Card] = []
    for sent in split_sentences(text):
        words = tokenize(sent, engine=engine, custom_dict=custom_dict)
        for group in chunk_words(words):
            if group:
                cards.append(Card(words=group))
    return cards


# ---------------------------------------------------------------- invariants

class ThaiChunkError(AssertionError):
    pass


def assert_cards_sane(cards: list[Card], source_text: str) -> None:
    """Crash loudly rather than ship broken Thai."""
    # 1. nothing lost, nothing invented
    joined = "".join(c.text for c in cards)
    src = "".join(source_text.split())
    if joined != src:
        raise ThaiChunkError(
            f"text not preserved: {len(joined)} chars out vs {len(src)} in")

    # 2. no card is empty
    for c in cards:
        if not c.text:
            raise ThaiChunkError("empty card")
        if len(c.words) > HARD_MAX:
            raise ThaiChunkError(f"card over hard max: {c!r}")

    # 3. no card boundary falls inside a Thai Character Cluster
    clusters = subword_tokenize(src, engine="tcc")
    edges, pos = set(), 0
    for cl in clusters:
        pos += len(cl)
        edges.add(pos)
    pos = 0
    for c in cards[:-1]:
        pos += len(c.text)
        if pos not in edges:
            raise ThaiChunkError(
                f"card boundary at char {pos} splits a Thai character cluster "
                f"(near {src[max(0,pos-8):pos+8]!r})")


if __name__ == "__main__":
    import io, os, sys, collections

    raw = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus_thai.txt"), encoding="utf-8").read()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    # the long lines are the real narration; short ones are junk auto-caption fragments
    lines = [l for l in lines if len(l) >= 25]

    # per-video vocabulary: the names this episode is about
    CUSTOM = ["เทพศิรินทร์", "เทพสิรินทร์", "เทพสิรินธร", "นนทบุรี", "เกมเมอร์",
              "กราดยิง", "แพะรับบาป"]
    cdict = build_dict(CUSTOM)

    out = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chunk_report.txt"), "w", encoding="utf-8")
    sizes = collections.Counter()
    total = 0
    for line in lines:
        cards = chunk_text(line, custom_dict=cdict)
        assert_cards_sane(cards, line)
        out.write(f"\nSOURCE: {line}\n")
        for c in cards:
            sizes[len(c.words)] += 1
            total += 1
            out.write(f"   {len(c.words)}w | {c.text}\n")

    out.write(f"\n\n=== {total} cards from {len(lines)} lines ===\n")
    for k in sorted(sizes):
        pct = sizes[k] / total * 100
        out.write(f"  {k} words: {sizes[k]:3d}  ({pct:4.1f}%)  {'#' * int(pct/2)}\n")
    in_range = sum(v for k, v in sizes.items() if MIN_WORDS <= k <= MAX_WORDS)
    out.write(f"  within {MIN_WORDS}-{MAX_WORDS} words: {in_range}/{total} "
              f"({in_range/total*100:.1f}%)\n")
    out.close()
    print(f"OK  {total} cards, {in_range}/{total} within {MIN_WORDS}-{MAX_WORDS} words")
    print("invariants passed (text preserved, no TCC split, no empty/oversized card)")
