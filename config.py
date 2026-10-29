"""Shared environment settings for the API and browser scripts."""

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default="", repr=False)
    channel: str = ""
    output_dir: Path = Path("output")
    video_ids_file: Path = Path("video_ids.txt")
    chapter_base_file: Path = Path("output/data_s.json")
    browser_wait: float = 5.0
    page_delay: float = 2.0
    max_videos: int = 0
    include_playlists: bool = True

    @property
    def chapters_file(self):
        return self.output_dir / "data_s2.json"

    @property
    def failed_ids_file(self):
        return self.output_dir / "failed_video_ids.txt"


def load_settings(*, require_api=False) -> Settings:
    load_dotenv(Path(__file__).with_name(".env"), override=False)

    def value(key, default=""):
        result = os.environ.get(key, str(default)).strip()
        if not result:
            raise ValueError(f"{key} must not be empty")
        return result

    def number(key, default, *, positive=False):
        try:
            result = float(value(key, default))
        except ValueError:
            raise ValueError(f"{key} must be a valid number") from None
        if not math.isfinite(result) or result < 0 or (positive and result == 0):
            raise ValueError(f"{key} must be finite and {'positive' if positive else 'non-negative'}")
        return result

    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    channel = os.environ.get("YOUTUBE_CHANNEL", "").strip()
    if require_api:
        if not api_key or api_key.lower().startswith("your_"):
            raise ValueError("Set YOUTUBE_API_KEY in .env or your environment")
        if not channel or channel == "channel_name_or_handle":
            raise ValueError("Set YOUTUBE_CHANNEL to a channel name or handle")
    output = Path(value("YOUTUBE_OUTPUT_DIR", "output"))
    try:
        max_videos = int(value("YOUTUBE_MAX_VIDEOS", 0))
    except ValueError:
        raise ValueError("YOUTUBE_MAX_VIDEOS must be a non-negative integer") from None
    if max_videos < 0:
        raise ValueError("YOUTUBE_MAX_VIDEOS must be a non-negative integer")
    include_playlists = value("YOUTUBE_INCLUDE_PLAYLISTS", "true").lower()
    if include_playlists not in ("true", "false"):
        raise ValueError("YOUTUBE_INCLUDE_PLAYLISTS must be true or false")
    return Settings(
        api_key=api_key,
        channel=channel,
        output_dir=output,
        video_ids_file=Path(value("YOUTUBE_VIDEO_IDS_FILE", "video_ids.txt")),
        chapter_base_file=Path(value("YOUTUBE_CHAPTER_BASE_FILE", output / "data_s.json")),
        browser_wait=number("YOUTUBE_BROWSER_WAIT", 5, positive=True),
        page_delay=number("YOUTUBE_PAGE_DELAY", 2),
        max_videos=max_videos,
        include_playlists=include_playlists == "true",
    )
