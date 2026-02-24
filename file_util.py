from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# =========================================================
# (1) Path management
# =========================================================

def base_dir() -> Path:
    return Path(__file__).resolve().parent


def resolve_path(filename_or_path: str, *, base: Optional[Path] = None) -> Path:
    p = Path(filename_or_path)
    if p.is_absolute():
        return p
    if base is None:
        base = base_dir()
    return (base / p).resolve()


# =========================================================
# (2) Raw file read/write (no parsing)
# =========================================================

def read_text_file(path: str | Path, *, encoding: str = "utf-8") -> str:
    p = path if isinstance(path, Path) else Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    return p.read_text(encoding=encoding)


def write_text_file(path: str | Path, content: str, *, encoding: str = "utf-8") -> None:
    p = path if isinstance(path, Path) else Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding=encoding)


# =========================================================
# (3) Interpret / parse / serialize file contents
# =========================================================

@dataclass(frozen=True)
class Card:
    word: str
    meaning: str
    example: str


# -------- dictionary.txt --------

def parse_dictionary_text(text: str) -> Dict[str, Card]:
    """
    dictionary.txt format per line:
        word : meaning : example_sentence
    Ignores blank lines and lines starting with '#'.
    Skips malformed lines.
    """
    mapping: Dict[str, Card] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(":")]
        if len(parts) != 3:
            continue
        word, meaning, example = parts
        if not word:
            continue
        mapping[word] = Card(word=word, meaning=meaning, example=example)
    return mapping


# -------- to_practice.txt --------

def parse_practice_list_text(text: str) -> List[str]:
    """
    to_practice.txt format per line:
        word_or_phrase
    Ignores blank lines and lines starting with '#'.
    """
    words: List[str] = []
    for raw in text.splitlines():
        w = raw.strip()
        if not w or w.startswith("#"):
            continue
        words.append(w)
    return words


def serialize_practice_list(words: List[str]) -> str:
    # Keep file simple; one word per line, dedup while preserving order.
    seen = set()
    out: List[str] = []
    for w in words:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return "\n".join(out) + ("\n" if out else "")


# -------- difficult_*.txt --------

def _parse_difficult_line(line: str) -> Optional[Tuple[date, str]]:
    """
    Format: yyyy-mm-dd,word
    """
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if "," not in s:
        return None
    d_str, word = [p.strip() for p in s.split(",", 1)]
    if not d_str or not word:
        return None
    try:
        added = datetime.strptime(d_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    return added, word


def parse_difficult_text(text: str) -> Dict[str, date]:
    """
    Returns mapping: word -> added_date
    If duplicates exist, keeps the latest date.
    """
    m: Dict[str, date] = {}
    for raw in text.splitlines():
        parsed = _parse_difficult_line(raw)
        if parsed is None:
            continue
        d, w = parsed
        if (w not in m) or (d > m[w]):
            m[w] = d
    return m


def serialize_difficult_map(m: Dict[str, date]) -> str:
    # Stable output: sort by date then word
    items = sorted(((d, w) for w, d in m.items()), key=lambda x: (x[0], x[1]))
    lines = [f"{d.isoformat()},{w}" for d, w in items]
    return "\n".join(lines) + ("\n" if lines else "")


def due_words_from_difficult_map(
    m: Dict[str, date],
    *,
    interval_days: int,
    today: Optional[date] = None,
) -> List[str]:
    if today is None:
        today = date.today()
    delta = timedelta(days=interval_days)
    due: List[str] = []
    for w, added in m.items():
        if added + delta <= today:
            due.append(w)
    return due


# =========================================================
# Convenience loaders
# =========================================================

def load_dictionary(dictionary_path: str) -> Dict[str, Card]:
    p = resolve_path(dictionary_path)
    text = read_text_file(p)
    return parse_dictionary_text(text)


def filter_words_in_dictionary(words: List[str], dictionary: Dict[str, Card]) -> List[str]:
    return [w for w in words if w in dictionary]


def load_review_words(practice_path: str, dictionary: Dict[str, Card]) -> List[str]:
    p = resolve_path(practice_path)
    text = read_text_file(p)
    words = parse_practice_list_text(text)
    return filter_words_in_dictionary(words, dictionary)


def load_due_words(
    difficult_path: str,
    *,
    interval_days: int,
    dictionary: Dict[str, Card],
    today: Optional[date] = None,
) -> List[str]:
    p = resolve_path(difficult_path)
    text = read_text_file(p)
    m = parse_difficult_text(text)
    due = due_words_from_difficult_map(m, interval_days=interval_days, today=today)
    return filter_words_in_dictionary(due, dictionary)


# =========================================================
# File operations (mutations) used by app
# =========================================================

def remove_word_from_practice_file(practice_path: str, word: str) -> None:
    p = resolve_path(practice_path)
    text = read_text_file(p)
    words = parse_practice_list_text(text)
    words = [w for w in words if w != word]
    write_text_file(p, serialize_practice_list(words))


def upsert_word_in_difficult_file(difficult_path: str, word: str, added: date) -> None:
    """
    Add if absent; if present, set date to `added` (today).
    """
    p = resolve_path(difficult_path)
    # If file might not exist yet, create it.
    try:
        text = read_text_file(p)
    except FileNotFoundError:
        text = ""
    m = parse_difficult_text(text)
    m[word] = added
    write_text_file(p, serialize_difficult_map(m))


def remove_word_from_difficult_file(difficult_path: str, word: str) -> None:
    p = resolve_path(difficult_path)
    try:
        text = read_text_file(p)
    except FileNotFoundError:
        return
    m = parse_difficult_text(text)
    if word in m:
        m.pop(word, None)
        write_text_file(p, serialize_difficult_map(m))


def move_word_between_difficult_files(
    src_path: str,
    dst_path: str,
    word: str,
    added: date,
) -> None:
    """
    Remove from src; upsert into dst with date=added.
    """
    remove_word_from_difficult_file(src_path, word)
    upsert_word_in_difficult_file(dst_path, word, added)
