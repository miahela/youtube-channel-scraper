"""Merge chapter runs; the first input keeps precedence for duplicate video IDs."""

import json
from pathlib import Path

from config import load_settings


def merge_chapter_data(sources=None, output_file=None, settings=None):
    settings = settings or load_settings()
    sources = sources if sources is not None else [settings.chapter_base_file, settings.chapters_file]
    output_file = Path(output_file) if output_file is not None else settings.output_dir / "datafinal.json"
    merged = {}
    loaded = 0
    for source in sources:
        source = Path(source)
        if not source.exists():
            print(f"Skipping missing chapter file: {source}")
            continue
        with open(source, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or any(not isinstance(v, dict) for v in data.values()):
            raise ValueError(f"{source} must contain a video-ID-to-chapter-object mapping")
        loaded += 1
        for key, value in data.items():
            if key not in merged:
                merged[key] = value
    if not loaded:
        raise ValueError("No chapter files found. Run chapter_scraper.py or configure YOUTUBE_CHAPTER_BASE_FILE")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)
    print(f"Total videos with chapter data: {len(merged)}")
    print(f"Saved to {output_file}")
    return merged


if __name__ == "__main__":
    try:
        merge_chapter_data()
    except (OSError, ValueError) as e:
        raise SystemExit(f"Chapter merge error: {e}") from None
