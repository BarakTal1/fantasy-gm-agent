import re

# Matches "Firstname Lastname" style capitalized bigrams (NBA player names).
# Each word starts with a capital letter and may contain further letters,
# apostrophes, or hyphens (e.g. "LeBron", "McCollum", "Karl-Anthony").
# A run can span 2+ consecutive capitalized words, since sentence-initial
# capitalization (e.g. "Add Josh Hart.") glues onto an adjacent name.
_RUN_RE = re.compile(r"\b([A-Z][a-zA-Z'-]*(?:\s[A-Z][a-zA-Z'-]*)+)\b")


def _contains_known_name(words: list[str], known_names: set[str]) -> bool:
    """True if any contiguous sub-phrase (2+ words) of `words` is a known name."""
    n = len(words)
    for i in range(n):
        for j in range(i + 2, n + 1):
            if " ".join(words[i:j]) in known_names:
                return True
    return False


def ungrounded_players(answer: str, known_names: set[str]) -> list[str]:
    """Capitalized full-name mentions in `answer` that are not in `known_names`.
    known_names = every player name returned by tools this turn.

    A run of capitalized words is treated as grounded if it exactly matches a
    known name, or if a known name appears as a contiguous sub-phrase within
    it (so incidental leading capitalization, e.g. a sentence-initial word,
    doesn't cause a false positive)."""
    found = _RUN_RE.findall(answer)
    seen: list[str] = []
    for run in found:
        if run in known_names:
            continue
        if _contains_known_name(run.split(), known_names):
            continue
        if run not in seen:
            seen.append(run)
    return seen
