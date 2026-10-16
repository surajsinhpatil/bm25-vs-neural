"""Text analysis for BM25.

Two analyzers are provided so that their effect can be measured (tokenisation ablation, RQ5):

* ``plain``   – mimics Lucene's default English analyzer used by Pyserini
                (standard tokenisation, possessive removal, lower-casing,
                Lucene's 33 English stopwords, Porter stemming). Used to check
                our BM25 against Pyserini.
* ``id``      – identifier-aware. Security text is full of strings such as
                CVE-2021-44228, SHA-256, TLS 1.3 or x86-64 that a standard tokenizer
                breaks into meaningless pieces ("2021", "256"). This analyzer keeps
                each such identifier as one un-stemmed token *and* also indexes its
                parts, and it normalises protocol versions ("TLS 1.3", "TLSv1.3",
                "TLS v1.3" -> "tls1.3"). Parts are treated like synonyms: they do not
                increase the document length.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Tuple

from nltk.stem.porter import PorterStemmer

# Lucene EnglishAnalyzer.ENGLISH_STOP_WORDS_SET (also Pyserini's default).
# Note that "no" and "not" are stopwords, so BM25 cannot see negation at all.
LUCENE_STOPWORDS = frozenset(
    "a an and are as at be but by for if in into is it no not of on or such that the "
    "their then there these they this to was will with".split()
)

_PORTER = PorterStemmer(mode=PorterStemmer.ORIGINAL_ALGORITHM)


@lru_cache(maxsize=1_000_000)
def _stem(w: str) -> str:
    return _PORTER.stem(w)


# Protocol / product names that are often written with a separate version number.
_PROTOCOLS = (
    "tls|ssl|dtls|quic|http|wpa|ssh|snmp|smb|ipv|bluetooth|usb|pcie|oauth|saml|ntlm|"
    "kerberos|android|ios|windows|tpm|armv|lte|wep|ikev|ike|eap|sha|md|rc|des|ecdsa|python"
)
_PROTO_VERSION_RE = re.compile(rf"\b({_PROTOCOLS})\s*/?\s*v?\s*(\d+(?:\.\d+)*)\b")
# Compound strings joined by separators, e.g. cve-2021-44228, sha-256, aes-128-gcm, 10.1145/123
_COMPOUND = r"[^\W_]+(?:[-._/:+][^\W_]+)+"
_WORD = r"[^\W_]+(?:'[^\W_]+)*"
_TOKEN_RE = re.compile(rf"(?P<cmp>{_COMPOUND})|(?P<word>{_WORD})")
_NUMBER_RE = re.compile(r"^\d+(?:[.,]\d+)*$")
_HAS_DIGIT = re.compile(r"\d")
_HAS_ALPHA = re.compile(r"[^\W\d_]")
_SPLIT_SEP = re.compile(r"[-_/:+]")
_SPLIT_ALL = re.compile(r"[-._/:+]")


@dataclass(frozen=True)
class Analyzer:
    mode: str = "id"          # "id" (identifier-aware) or "plain" (Lucene-like)
    stem: bool = True
    stopwords: bool = True

    @property
    def name(self) -> str:
        return f"{self.mode}{'' if self.stem else '-nostem'}{'' if self.stopwords else '-nostop'}"

    # ------------------------------------------------------------------ public API
    def analyze(self, text: str) -> Tuple[List[str], int]:
        """Return (tokens, length). ``length`` counts only primary tokens, so that the
        extra part-tokens of identifiers do not count towards BM25 length normalisation
        (like Lucene's discountOverlaps for synonym tokens)."""
        text = unicodedata.normalize("NFKC", text).lower()
        if self.mode == "id":
            text = _PROTO_VERSION_RE.sub(r"\1\2", text)
        out: List[str] = []
        length = 0
        for m in _TOKEN_RE.finditer(text):
            cmp_tok = m.group("cmp")
            if cmp_tok is not None:
                length += self._compound(cmp_tok, out)
            else:
                length += self._word(m.group("word"), out)
        return out, length

    def tokens(self, text: str) -> List[str]:
        return self.analyze(text)[0]

    # ------------------------------------------------------------------ internals
    def _word(self, w: str, out: List[str]) -> int:
        if w.endswith("'s"):
            w = w[:-2]
        if not w or (self.stopwords and w in LUCENE_STOPWORDS):
            return 0
        if self.stem and (self.mode == "plain" or not _HAS_DIGIT.search(w)):
            w = _stem(w)
        out.append(w)
        return 1

    def _compound(self, tok: str, out: List[str]) -> int:
        has_digit = bool(_HAS_DIGIT.search(tok))
        if self.mode == "plain":
            # Lucene's StandardTokenizer splits on hyphens/slashes but keeps '.'
            # inside numbers and abbreviations (e.g. "1.3", "e.g").
            n = 0
            for piece in _SPLIT_SEP.split(tok):
                if piece:
                    n += self._word(piece, out)
            return n
        # identifier-aware
        if _NUMBER_RE.match(tok):            # plain number such as 1.3 or 2,048
            out.append(tok)
            return 1
        if has_digit and _HAS_ALPHA.search(tok):
            out.append(tok)                  # whole identifier, never stemmed
            for piece in _SPLIT_ALL.split(tok):
                if piece and not (self.stopwords and piece in LUCENE_STOPWORDS):
                    out.append(piece if _HAS_DIGIT.search(piece) or not self.stem else _stem(piece))
            return 1                         # parts do not add to the length
        # no digits: an ordinary hyphenated phrase (side-channel, man-in-the-middle)
        n = 0
        for piece in _SPLIT_SEP.split(tok):
            if piece:
                n += self._word(piece, out)
        return n


ANALYZERS = {
    "id": Analyzer("id", True, True),
    "plain": Analyzer("plain", True, True),
    "id-nostem": Analyzer("id", False, True),
    "plain-nostem": Analyzer("plain", False, True),
    "id-nostop": Analyzer("id", True, False),
}


def get_analyzer(name: str) -> Analyzer:
    if name not in ANALYZERS:
        raise KeyError(f"unknown analyzer {name!r}; choose from {sorted(ANALYZERS)}")
    return ANALYZERS[name]
