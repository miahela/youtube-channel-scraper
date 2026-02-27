"""
Extracts chapter timestamps from YouTube videos using Selenium.

Reads video IDs from filtered_video_ids.txt and writes results to data_s2.json.
Run merge_chapter_data.py afterwards to combine with data_s.json into datafinal.json.
"""

import json
import time

from selenium_manager import SeleniumManager


def save_to_json(data, path="data/data_s2.json"):
    with open(path, "w") as f:
        json.dump(data, f)


def save_failed_ids(ids, path="data/failed_video_ids.txt"):
    with open(path, "w") as f:
        for vid_id in ids:
            f.write(vid_id + "\n")


def scrape_chapters(video_ids):
    chapter_data = {}
    failed_ids = []

    for i, video_id in enumerate(video_ids, start=1):
        sm = SeleniumManager()
        sm.open_link(f"https://www.youtube.com/watch?v={video_id}")
        time.sleep(2)

        try:
            sm.click_element('//div[@id="description-inner"]')
            time.sleep(2)

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
                except Exception:
                    break  # No more chapter pages

        except Exception as e:
            print(f"Error on video {video_id}: {e}")
            failed_ids.append(video_id)

        finally:
            save_to_json(chapter_data)
            sm.quit()
            print(f"[{i}/{len(video_ids)}] {video_id}")

    if failed_ids:
        save_failed_ids(failed_ids)
        print(f"\n{len(failed_ids)} video(s) failed. IDs saved to failed_video_ids.txt")

    print("Done. Chapter data saved to data_s2.json")


if __name__ == "__main__":
    with open("data/filtered_video_ids.txt") as f:
        video_ids = [line.strip() for line in f if line.strip()]

    scrape_chapters(video_ids)
