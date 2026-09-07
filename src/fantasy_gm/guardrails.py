import re

# Matches "Firstname Lastname" style capitalized bigrams (NBA player names).
# Each word starts with a capital letter and may contain further letters,
# apostrophes, or hyphens (e.g. "LeBron", "McCollum", "Karl-Anthony").
_NAME_RE = re.compile(r"\b([A-Z][a-zA-Z'-]*(?:\s[A-Z][a-zA-Z'-]*)+)\b")


def ungrounded_players(answer: str, known_names: set[str]) -> list[str]:
    """Capitalized full-name mentions in `answer` that are not in `known_names`.
    known_names = every player name returned by tools this turn."""
    found = _NAME_RE.findall(answer)
    seen: list[str] = []
    for name in found:
        if name not in known_names and name not in seen:
            seen.append(name)
    return seen
