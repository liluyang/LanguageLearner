#!/usr/bin/env python3
"""
dictionary_fixer.py — Fix Spanish spelling errors in data/dictionary.txt,
and fill in missing English meanings via translation API.

Uses the free LanguageTool public API (no key required) for spell-checking,
and the free MyMemory translation API (no key required) for missing meanings.

Usage:
    # Preview changes without writing
    python tool/dictionary_fixer.py --dry-run

    # Fix first 200 entries and overwrite in-place (creates .bak backup)
    python tool/dictionary_fixer.py --limit 200

    # Fix all entries, write to a different file
    python tool/dictionary_fixer.py --output data/dictionary_fixed.txt

    # Resume from a specific word (useful after interruption)
    python tool/dictionary_fixer.py --start-from "acudir"

    # Fill missing English meanings (dry-run preview)
    python tool/dictionary_fixer.py --fill-meanings --dry-run

    # Fill missing English meanings and save
    python tool/dictionary_fixer.py --fill-meanings

    # Combine flags
    python tool/dictionary_fixer.py --limit 500 --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Tuple

import requests

# ---------------------------------------------------------------------------
# Project root so lib.file_util is importable when run from any directory
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.file_util import parse_dictionary_text, read_text_file, write_text_file

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DICTIONARY_FILE = PROJECT_ROOT / "data" / "dictionary.txt"
LANGUAGETOOL_API = "https://api.languagetool.org/v2/check"
MYMEMORY_API = "https://api.mymemory.translated.net/get"
LANGUAGE = "es"

# Free-tier limits: 20 req/min, ~20 000 chars/req.
# We use ~8 000 chars per batch to stay well within limits and a 3 s delay
# between requests (≈ 20 req/min max).
BATCH_CHAR_LIMIT = 8_000
REQUEST_DELAY = 3.0  # seconds
TRANSLATION_DELAY = 0.5  # seconds between MyMemory requests


# ---------------------------------------------------------------------------
# LanguageTool helpers
# ---------------------------------------------------------------------------

def _get_spelling_corrections(text: str) -> list[tuple[int, int, str]]:
    """
    Call LanguageTool for *text* and return a list of (offset, length, replacement)
    for misspelling matches only (ignores grammar/style rules).
    """
    resp = requests.post(
        LANGUAGETOOL_API,
        data={"text": text, "language": LANGUAGE},
        timeout=15,
    )
    resp.raise_for_status()
    matches = resp.json().get("matches", [])
    corrections: list[tuple[int, int, str]] = []
    for m in matches:
        if m.get("rule", {}).get("issueType") != "misspelling":
            continue
        replacements = m.get("replacements", [])
        if not replacements:
            continue
        corrections.append((m["offset"], m["length"], replacements[0]["value"]))
    return corrections


def _apply_corrections(text: str, corrections: list[tuple[int, int, str]]) -> str:
    """Apply offset-based corrections in reverse order so earlier offsets stay valid."""
    chars = list(text)
    for offset, length, replacement in sorted(corrections, key=lambda c: c[0], reverse=True):
        chars[offset: offset + length] = list(replacement)
    return "".join(chars)


def fix_text(text: str) -> str:
    """Return *text* with Spanish spelling errors corrected via LanguageTool."""
    if not text.strip():
        return text
    corrections = _get_spelling_corrections(text)
    return _apply_corrections(text, corrections)


# ---------------------------------------------------------------------------
# MyMemory translation helpers
# ---------------------------------------------------------------------------

def _translate_es_to_en(text: str) -> str | None:
    """
    Translate *text* from Spanish to English using the free MyMemory API.
    Returns the translated string, or None if the request fails or is low-confidence.
    """
    try:
        resp = requests.get(
            MYMEMORY_API,
            params={"q": text, "langpair": "es|en"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        # responseStatus 200 means OK; responseData contains the translation.
        if data.get("responseStatus") != 200:
            return None
        translation = data.get("responseData", {}).get("translatedText", "").strip()
        return translation if translation else None
    except requests.RequestException as exc:
        print(f"    WARNING: translation API error for {text!r}: {exc}", file=sys.stderr)
        return None


def fill_missing_meanings(
    input_path: Path,
    *,
    output_path: Path,
    dry_run: bool,
    limit: int | None,
) -> None:
    """
    Find entries in *input_path* whose English meaning field is empty,
    fetch a translation via MyMemory, and write the updated dictionary.
    """
    raw_text = read_text_file(input_path)
    raw_lines = raw_text.splitlines()

    # Parse lines
    entries: list[tuple[str, str, str, str]] = []  # (raw_line, word, meaning, example)
    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            entries.append((raw, "", "", ""))
            continue
        parts = [p.strip() for p in line.split(":", 2)]
        word = parts[0]
        meaning = parts[1] if len(parts) >= 2 else ""
        example = parts[2] if len(parts) == 3 else ""
        entries.append((raw, word, meaning, example))

    missing = [(i, word, example) for i, (_, word, meaning, example) in enumerate(entries) if word and not meaning]

    if limit is not None:
        missing = missing[:limit]

    print(f"Found {len(missing)} entries with no English meaning.")

    changed_count = 0
    output_entries = [list(e) for e in entries]  # mutable copy

    for pos, (idx, word, example) in enumerate(missing, 1):
        print(f"  [{pos}/{len(missing)}] Translating {word!r} …", flush=True)
        translation = _translate_es_to_en(word)
        if translation:
            print(f"    → {translation!r}")
            output_entries[idx][2] = translation  # update meaning field
            changed_count += 1
        else:
            print(f"    → (no translation found, skipping)")
        if pos < len(missing):
            time.sleep(TRANSLATION_DELAY)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Filled {changed_count} missing meanings.")

    if dry_run:
        print("No files written (--dry-run).")
        return

    if output_path == input_path:
        backup = input_path.with_suffix(".txt.bak")
        backup.write_text(raw_text, encoding="utf-8")
        print(f"Backup written to {backup}")

    new_lines = []
    for raw, word, meaning, example in output_entries:
        if not word:  # blank / comment line
            new_lines.append(raw)
        else:
            new_lines.append(_serialize_entry(word, meaning, example))

    write_text_file(output_path, "\n".join(new_lines) + "\n")
    print(f"Updated dictionary written to {output_path}")


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def _make_batches(lines: list[str]) -> list[list[tuple[int, str]]]:
    """
    Group (index, line) pairs into batches where the joined text stays within
    BATCH_CHAR_LIMIT characters. Returns list of batches; each batch is a list
    of (original_index, line) tuples.
    """
    batches: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    current_len = 0

    for idx, line in enumerate(lines):
        needed = len(line) + (1 if current else 0)  # +1 for the "\n" separator
        if current and current_len + needed > BATCH_CHAR_LIMIT:
            batches.append(current)
            current = []
            current_len = 0
        current.append((idx, line))
        current_len += needed

    if current:
        batches.append(current)
    return batches


def fix_lines_batch(lines: list[str], *, label: str = "") -> list[str]:
    """
    Fix a list of single-field strings (e.g. all Spanish words, or all example
    blocks) using batched LanguageTool calls.

    Each element in *lines* maps 1-to-1 with an entry in the dictionary.
    Empty strings are preserved as-is without an API call.
    """
    results = list(lines)
    non_empty = [(i, l) for i, l in enumerate(lines) if l.strip()]

    batches = _make_batches([l for _, l in non_empty])
    index_map = [i for i, _ in non_empty]  # maps batch position → original index

    processed = 0
    for batch_num, batch in enumerate(batches, 1):
        joined = "\n".join(line for _, line in batch)
        print(
            f"  [{label}] batch {batch_num}/{len(batches)} "
            f"({len(batch)} items, {len(joined)} chars) …",
            flush=True,
        )
        try:
            corrected_joined = fix_text(joined)
        except requests.RequestException as exc:
            print(f"    WARNING: API error — skipping batch: {exc}", file=sys.stderr)
            corrected_joined = joined

        corrected_lines = corrected_joined.split("\n")
        # Guard against unexpected line count change (shouldn't happen for spelling)
        if len(corrected_lines) != len(batch):
            print(
                f"    WARNING: line count mismatch after correction "
                f"(expected {len(batch)}, got {len(corrected_lines)}); skipping batch",
                file=sys.stderr,
            )
        else:
            for batch_pos, (_, _orig_line) in enumerate(batch):
                orig_idx = index_map[processed + batch_pos]
                results[orig_idx] = corrected_lines[batch_pos]

        processed += len(batch)
        if batch_num < len(batches):
            time.sleep(REQUEST_DELAY)

    return results


# ---------------------------------------------------------------------------
# Entry-level helpers
# ---------------------------------------------------------------------------

def _serialize_entry(word: str, meaning: str, example: str) -> str:
    return f"{word} : {meaning} : {example}"


def _diff_entry(
    original: str,
    fixed_word: str,
    meaning: str,
    fixed_example: str,
) -> list[str]:
    """Return human-readable diff lines for a changed entry, or empty list if unchanged."""
    orig_word, _, orig_example = (p.strip() for p in original.split(":", 2)) if original.count(":") >= 2 else (original.strip(), "", "")
    changes = []
    if orig_word != fixed_word:
        changes.append(f"  word:    {orig_word!r}  →  {fixed_word!r}")
    if orig_example != fixed_example:
        changes.append(f"  example: {orig_example!r}  →  {fixed_example!r}")
    return changes


# ---------------------------------------------------------------------------
# Main fix logic
# ---------------------------------------------------------------------------

def fix_dictionary(
    input_path: Path,
    *,
    output_path: Path,
    dry_run: bool,
    limit: int | None,
    start_from: str | None,
) -> None:
    raw_text = read_text_file(input_path)
    raw_lines = raw_text.splitlines()

    # Parse into (word, meaning, example) triples while preserving raw lines
    entries: list[tuple[str, str, str, str]] = []  # (raw_line, word, meaning, example)
    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            entries.append((raw, "", "", ""))  # pass-through
            continue
        parts = [p.strip() for p in line.split(":", 2)]
        word = parts[0]
        meaning = parts[1] if len(parts) >= 2 else ""
        example = parts[2] if len(parts) == 3 else ""
        entries.append((raw, word, meaning, example))

    # Determine the slice to fix
    start_idx = 0
    if start_from:
        for i, (_, word, _, _) in enumerate(entries):
            if word == start_from:
                start_idx = i
                break
        else:
            print(f"WARNING: --start-from word {start_from!r} not found; starting from beginning.", file=sys.stderr)

    end_idx = len(entries)
    if limit is not None:
        end_idx = min(start_idx + limit, len(entries))

    work = entries[start_idx:end_idx]
    untouched_before = entries[:start_idx]
    untouched_after = entries[end_idx:]

    print(f"Processing {len(work)} entries (lines {start_idx + 1}–{end_idx}) …")

    # Extract word and example fields for batch fixing
    words = [word for _, word, _, _ in work]
    # Join each entry's pipe-separated examples with "\n" so LanguageTool sees
    # them as separate sentences, then reassemble later.
    example_blocks: list[str] = []
    for _, _, _, example in work:
        if example.strip():
            # replace "|" separators with newline for API, restore after
            example_blocks.append(example.replace("|", "\n"))
        else:
            example_blocks.append("")

    print("Fixing Spanish words …")
    fixed_words = fix_lines_batch(words, label="words")
    time.sleep(REQUEST_DELAY)

    print("Fixing example sentences …")
    fixed_example_blocks = fix_lines_batch(example_blocks, label="examples")

    # Restore "|" separators
    fixed_examples: list[str] = []
    for orig_block, fixed_block in zip(example_blocks, fixed_example_blocks):
        if orig_block.strip():
            # Preserve spacing around "|" as " | "
            parts = [s.strip() for s in fixed_block.split("\n")]
            fixed_examples.append(" | ".join(p for p in parts if p))
        else:
            fixed_examples.append("")

    # Build output lines
    changed_count = 0
    output_lines: list[str] = []

    for raw, _ in ((e[0], None) for e in untouched_before):
        output_lines.append(raw)

    for (raw, _word, meaning, _example), fw, fe in zip(work, fixed_words, fixed_examples):
        line = raw.strip()
        if not line or line.startswith("#"):
            output_lines.append(raw)
            continue

        diff = _diff_entry(raw, fw, meaning, fe)
        if diff:
            changed_count += 1
            print(f"\n{_word!r}:")
            for d in diff:
                print(d)
            output_lines.append(_serialize_entry(fw, meaning, fe))
        else:
            output_lines.append(raw)

    for raw, _ in ((e[0], None) for e in untouched_after):
        output_lines.append(raw)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Changed {changed_count} entries.")

    if dry_run:
        print("No files written (--dry-run).")
        return

    # Backup original if writing in-place
    if output_path == input_path:
        backup = input_path.with_suffix(".txt.bak")
        backup.write_text(raw_text, encoding="utf-8")
        print(f"Backup written to {backup}")

    write_text_file(output_path, "\n".join(output_lines) + "\n")
    print(f"Fixed dictionary written to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix Spanish spelling errors in dictionary.txt via LanguageTool."
    )
    parser.add_argument(
        "--input",
        default=str(DICTIONARY_FILE),
        help="Path to input dictionary.txt (default: data/dictionary.txt)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write fixed file (default: overwrite input in-place with .bak backup)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print changes but do not write any files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Only process the first N content entries",
    )
    parser.add_argument(
        "--start-from",
        default=None,
        metavar="WORD",
        help="Skip entries before this Spanish word (useful to resume after interruption)",
    )
    parser.add_argument(
        "--fill-meanings",
        action="store_true",
        help="Fill empty English meaning fields using the MyMemory translation API",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path

    if args.fill_meanings:
        fill_missing_meanings(
            input_path,
            output_path=output_path,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    else:
        fix_dictionary(
            input_path,
            output_path=output_path,
            dry_run=args.dry_run,
            limit=args.limit,
            start_from=args.start_from,
        )


if __name__ == "__main__":
    main()
