"""
Data loading utilities
"""

import json
from pathlib import Path
from typing import Optional


def load_jsonl(filepath: Path, limit: Optional[int] = None) -> list[dict]:
    """Load JSONL file"""
    entries = []

    if not filepath.exists():
        return entries

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass

    if limit:
        return entries[-limit:]
    return entries


def load_ratings(data_dir: Path, limit: int = 100) -> list[dict]:
    """Load user ratings"""
    ratings_file = data_dir / "user_ratings.jsonl"
    return load_jsonl(ratings_file, limit)


def calculate_gap_stats(ratings: list[dict]) -> dict:
    """Calculate gap statistics from ratings"""
    if not ratings:
        return {
            "avg_gap": 0,
            "overconfident_count": 0,
            "underconfident_count": 0,
            "accurate_count": 0,
            "total": 0
        }

    gaps = [r.get("gap", 0) for r in ratings]
    return {
        "avg_gap": sum(gaps) / len(gaps),
        "overconfident_count": sum(1 for g in gaps if g < 0),
        "underconfident_count": sum(1 for g in gaps if g > 0),
        "accurate_count": sum(1 for g in gaps if g == 0),
        "total": len(gaps)
    }
