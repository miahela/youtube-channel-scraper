"""
Extracts chapter timestamps from YouTube videos using Selenium.

Reads the configured video-ID file and saves chapter results in the output folder.
Run merge_chapter_data.py afterwards to combine these with an optional earlier run.
"""

import json
import time
from pathlib import Path

from selenium.common.exceptions import WebDriverException

from selenium_manager import SeleniumManager
from config import load_settings


def save_to_json(data, path=None):
    path = Path(path) if path is not None else load_settings().chapters_file
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def save_failed_ids(ids, path=None):
    path = Path(path) if path is not None else load_settings().failed_ids_file
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for vid_id in ids:
            f.write(vid_id + "\n")


def scrape_chapters(video_ids, settings=None):
    settings = settings or load_settings()
    if settings.max_videos:
        video_ids = video_ids[:settings.max_videos]
    chapter_data = {}
    failed_ids = []

    for i, video_id in enumerate(video_ids, start=1):
        sm = None
        try:
            sm = SeleniumManager(settings)
            sm.open_link(f"https://www.youtube.com/watch?v={video_id}")
            time.sleep(settings.page_delay)
            sm.click_element('//div[@id="description-inner"]')
            time.sleep(settings.page_delay)

            timestamps = []
            chapters = []

            while True:
                for el in sm.get_elements("//div[@id='time']"):
                    timestamps.append(el.text)
                for el in sm.get_elements(
                    "//h4[@class='macro-markers style-scope ytd-macro-markers-list-item-renderer']"
                ):
                    chapters.append(el.text)

                chapter_data[video_id] = {"timestamps": timestamps, "chapters": chapters}

                try:
                    sm.click_element('//div[@id="right-arrow"]')
                except WebDriverException:
                    break  # No more chapter pages

        except WebDriverException as e:
            print(f"Error on video {video_id}: {e}")
            failed_ids.append(video_id)

        finally:
            try:
                save_to_json(chapter_data, settings.chapters_file)
            finally:
                if sm is not None:
                    try:
                        sm.quit()
                    except WebDriverException:
                        print(f"Warning: browser cleanup failed for {video_id}")
            print(f"[{i}/{len(video_ids)}] {video_id}")

    if failed_ids:
        save_failed_ids(failed_ids, settings.failed_ids_file)
        print(f"\n{len(failed_ids)} video(s) failed. IDs saved to {settings.failed_ids_file}")

    print(f"Done. Chapter data saved to {settings.chapters_file}")
    return failed_ids


if __name__ == "__main__":
    try:
        settings = load_settings()
        with open(settings.video_ids_file, encoding="utf-8-sig") as f:
            video_ids = [line.strip() for line in f if line.strip()]
        if not video_ids:
            raise ValueError(f"No video IDs found in {settings.video_ids_file}")
        if scrape_chapters(video_ids, settings):
            raise SystemExit("Some videos failed. Review the saved failed IDs before retrying.")
    except (OSError, ValueError) as e:
        raise SystemExit(f"Setup or file error: {e}") from None
    except KeyboardInterrupt:
        raise SystemExit("Interrupted. Chapter progress is saved in the output folder.") from None
