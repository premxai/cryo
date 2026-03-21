"""Validate the downloaded JSONL corpus before indexing.

Usage:
    python pipeline/validate.py --path data/raw/ --expected 100000

Exits with code 0 on success, 1 on any failure.
Run this between download.py and index.py to fail fast on corrupt data.
"""

import argparse
import json
import sys
from pathlib import Path

from tqdm import tqdm

REQUIRED_FIELDS = {"id", "url", "text", "timestamp", "year", "domain", "word_count"}
MAX_ALLOWED_YEAR = 2021


def validate(data_path: str, expected: int) -> bool:
    """Run all integrity checks. Returns True if corpus is valid."""
    path = Path(data_path)
    if not path.exists():
        print(f"[validate] ERROR: Path does not exist: {path}", file=sys.stderr)
        return False

    jsonl_files = sorted(path.glob("*.jsonl"))
    if not jsonl_files:
        print(f"[validate] ERROR: No .jsonl files found in {path}", file=sys.stderr)
        return False

    print(f"[validate] Found {len(jsonl_files)} JSONL files.")

    total_docs = 0
    errors: list[str] = []

    for jsonl_file in tqdm(jsonl_files, desc="Validating files"):
        with jsonl_file.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    doc = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"{jsonl_file.name}:{line_num} — JSON parse error: {exc}")
                    continue

                total_docs += 1

                # Check required fields present
                missing = REQUIRED_FIELDS - set(doc.keys())
                if missing:
                    errors.append(f"{jsonl_file.name}:{line_num} — Missing fields: {missing}")

                # Check text is non-empty
                if not doc.get("text", "").strip():
                    errors.append(f"{jsonl_file.name}:{line_num} — Empty text field")

                # Check year is in valid range
                year = doc.get("year")
                if year is None or not isinstance(year, int) or year > MAX_ALLOWED_YEAR:
                    errors.append(f"{jsonl_file.name}:{line_num} — Invalid year: {year}")

                # Check doc ID is non-empty
                if not doc.get("id", "").strip():
                    errors.append(f"{jsonl_file.name}:{line_num} — Empty id field")

    # Summarize
    print(f"\n[validate] Total docs found: {total_docs:,}")
    print(f"[validate] Expected:         {expected:,}")

    if total_docs < expected:
        errors.append(
            f"Doc count {total_docs:,} is less than expected {expected:,}. "
            "Re-run download.py to collect more."
        )

    if errors:
        print(f"\n[validate] FAILED — {len(errors)} error(s):", file=sys.stderr)
        for err in errors[:20]:  # show first 20
            print(f"  • {err}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more.", file=sys.stderr)
        return False

    print("[validate] All checks passed.")
    return True


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Validate downloaded JSONL corpus.")
    parser.add_argument("--path", type=str, default="data/raw", help="Directory with JSONL files.")
    parser.add_argument("--expected", type=int, default=100_000, help="Expected doc count.")
    args = parser.parse_args()

    ok = validate(data_path=args.path, expected=args.expected)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
