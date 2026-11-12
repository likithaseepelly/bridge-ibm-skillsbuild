"""Retrieval over the local discharge guidance corpus.

Deliberately small. The point is grounding, not search quality: every clinical
statement the system makes has to be traceable to a passage id in this index.
"""

import math
import re
from collections import Counter
from functools import lru_cache
from typing import Dict, List, Tuple

from . import config

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> List[str]:
    return _WORD.findall(text.lower())


class Index:
    """A passage index. One passage per bullet or paragraph."""

    def __init__(self):
        self.passages: List[Dict[str, str]] = []
        self._df: Counter = Counter()
        self._load()

    def _load(self) -> None:
        for path in sorted(config.KNOWLEDGE_DIR.glob("*.md")):
            doc = path.stem
            section = ""
            for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    section = line.lstrip("# ").strip()
                    continue
                if line.startswith("- "):
                    text = line[2:].strip()
                elif line.startswith("Source note:"):
                    continue
                else:
                    text = line
                pid = "%s:%d" % (doc, lineno)
                self.passages.append({
                    "id": pid, "doc": doc, "section": section, "text": text,
                })
        for p in self.passages:
            for t in set(_tokens(p["text"])):
                self._df[t] += 1

    def _score(self, query_tokens: List[str], passage: Dict[str, str]) -> float:
        ptokens = _tokens(passage["text"]) + _tokens(passage["section"])
        if not ptokens:
            return 0.0
        counts = Counter(ptokens)
        n = len(self.passages)
        score = 0.0
        for t in query_tokens:
            if t not in counts:
                continue
            tf = counts[t] / len(ptokens)
            idf = math.log((1 + n) / (1 + self._df.get(t, 0))) + 1.0
            score += tf * idf
        return score

    def search(self, query: str, doc_filter: str = "", k: int = 5
               ) -> List[Dict[str, str]]:
        qt = _tokens(query)
        pool = [p for p in self.passages
                if not doc_filter or p["doc"].startswith(doc_filter)]
        scored: List[Tuple[float, Dict[str, str]]] = [
            (self._score(qt, p), p) for p in pool]
        scored = [s for s in scored if s[0] > 0]
        scored.sort(key=lambda s: s[0], reverse=True)
        return [p for _, p in scored[:k]]

    def warning_signs(self, condition: str) -> List[Dict[str, str]]:
        """Every warning sign carries the id of the passage it came from."""
        doc = {"heart_failure": "heart_failure", "copd": "copd",
               "type2_diabetes": "type2_diabetes"}[condition]
        return [p for p in self.passages
                if p["doc"].startswith(doc)
                and "Warning signs" in p["section"]]

    def get(self, passage_id: str) -> Dict[str, str]:
        for p in self.passages:
            if p["id"] == passage_id:
                return p
        raise KeyError(passage_id)


@lru_cache(maxsize=1)
def index() -> Index:
    return Index()
