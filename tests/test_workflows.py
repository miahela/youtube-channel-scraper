"""Offline checks for API exports, browser failures, and chapter merging."""

import contextlib
import csv
import io
import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import Mock, patch

from googleapiclient.errors import HttpError
from httplib2 import Response
from selenium.common.exceptions import WebDriverException

import chapter_scraper
import playlist_scraper
import video_scraper
from config import Settings
from config import load_settings
from merge_chapter_data import merge_chapter_data


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = Settings(output_dir=self.root / "output", page_delay=0)

    def test_video_pages_keep_deduplication_sorting_and_playlist_matching(self):
        youtube = Mock()

        def item(video_id, day):
            return {"id": {"videoId": video_id}, "snippet": {
                "title": video_id, "publishedAt": f"2026-01-{day}T12:00:00Z",
            }}

        youtube.search().list().execute.side_effect = [
            {"items": [item("a", "01")], "nextPageToken": "next"},
            {"items": [item("a", "01"), item("b", "02")]},
        ]
        youtube.videos().list().execute.return_value = {"items": [{
            "snippet": {"description": "00:00 Intro"},
            "statistics": {"viewCount": "42"}, "contentDetails": {"duration": "PT1M"},
        }]}
        rows = video_scraper.get_all_videos(youtube, "channel", [
            {"title": "Demo playlist", "video_ids": ["a"]},
        ])
        self.assertEqual([row["ID"] for row in rows], ["b", "a"])
        self.assertEqual(rows[1]["Playlists"], "Demo playlist")
        self.assertEqual(rows[0]["View Count"], "42")
        self.assertEqual(youtube.videos().list().execute.call_count, 2)

    def test_api_exports_use_configured_folder(self):
        for module, action, filename, helpers, row in [
            (video_scraper, "scrape_channel", "combined_video_data.csv",
             ["get_channel_playlists", "get_all_videos"], {"Title": "Fixture", "ID": "a"}),
            (playlist_scraper, "scrape_video_playlist_links", "video_playlist_link_data.csv",
             ["get_playlists", "build_video_playlist_map"], {"Video Title": "Fixture", "Playlist URLs": ""}),
        ]:
            with self.subTest(action=action):
                with patch.object(module.googleapiclient.discovery, "build"):
                    with patch.object(module, "get_channel_id", return_value="fixture-channel"):
                        with patch.object(module, helpers[0], return_value=[]):
                            with patch.object(module, helpers[1], return_value=[row]):
                                with contextlib.redirect_stdout(io.StringIO()):
                                    getattr(module, action)("fixture-query", self.settings)
                with (self.settings.output_dir / filename).open(encoding="utf8", newline="") as f:
                    self.assertEqual(len(list(csv.DictReader(f))), 1)

    def test_browser_start_failure_is_saved_without_aborting_remaining_ids(self):
        with patch.object(chapter_scraper, "SeleniumManager", side_effect=WebDriverException("startup failed")) as manager:
            with contextlib.redirect_stdout(io.StringIO()):
                failures = chapter_scraper.scrape_chapters(["first", "second"], self.settings)
        self.assertEqual(failures, ["first", "second"])
        self.assertEqual(manager.call_count, 2)
        self.assertEqual(self.settings.failed_ids_file.read_text().splitlines(), failures)
        self.assertEqual(json.loads(self.settings.chapters_file.read_text()), {})

    def test_navigation_failure_still_closes_browser(self):
        browser = Mock()
        browser.open_link.side_effect = WebDriverException("navigation failed")
        with patch.object(chapter_scraper, "SeleniumManager", return_value=browser):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(chapter_scraper.scrape_chapters(["video"], self.settings), ["video"])
        browser.quit.assert_called_once()

    def test_browser_is_closed_even_when_progress_save_fails(self):
        browser = Mock()
        browser.open_link.side_effect = WebDriverException("navigation failed")
        with patch.object(chapter_scraper, "SeleniumManager", return_value=browser):
            with patch.object(chapter_scraper, "save_to_json", side_effect=OSError("disk full")):
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(OSError, "disk full"):
                        chapter_scraper.scrape_chapters(["video"], self.settings)
        browser.quit.assert_called_once()

    def test_merge_skips_missing_input_and_preserves_first_file_precedence(self):
        first, second = self.root / "first.json", self.root / "second.json"
        first.write_text(json.dumps({"same": {"chapters": ["First"]}}))
        second.write_text(json.dumps({"same": {"chapters": ["Second"]}, "new": {}}))
        with contextlib.redirect_stdout(io.StringIO()):
            merged = merge_chapter_data([self.root / "missing.json", first, second], settings=self.settings)
        self.assertEqual(merged["same"]["chapters"], ["First"])
        self.assertIn("new", merged)

    def test_missing_or_malformed_merge_inputs_do_not_replace_existing_export(self):
        self.settings.output_dir.mkdir()
        output = self.settings.output_dir / "datafinal.json"
        output.write_text('{"keep": {}}')
        bad = self.root / "bad.json"
        for content in [None, "{invalid", "[]", '{"video": 1}']:
            with self.subTest(content=content):
                if content is not None:
                    bad.write_text(content)
                sources = [self.root / "missing.json"] if content is None else [bad]
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(ValueError):
                        merge_chapter_data(sources, output, self.settings)
                self.assertEqual(output.read_text(), '{"keep": {}}')

    def test_api_error_messages_do_not_expose_request_key(self):
        fake_key = "offline-fixture-key"
        error = HttpError(
            Response({"status": "403"}), b'{"error": {"message": "Fixture quota error"}}',
            uri=f"https://example.test/?key={fake_key}",
        )
        for module in [video_scraper, playlist_scraper]:
            with self.subTest(module=module.__name__):
                with patch.dict(os.environ, {"YOUTUBE_API_KEY": fake_key, "YOUTUBE_CHANNEL": "fixture"}):
                    with patch.object(module.googleapiclient.discovery, "build", side_effect=error):
                        with self.assertRaises(SystemExit) as raised:
                            runpy.run_path(str(Path(module.__file__)), run_name="__main__")
                self.assertIn("HTTP 403", str(raised.exception))
                self.assertNotIn(fake_key, str(raised.exception))
                self.assertNotIn("example.test", str(raised.exception))

    def test_small_metadata_run_skips_playlists_and_limits_detail_requests(self):
        settings = replace(self.settings, max_videos=5, include_playlists=False)
        youtube = Mock()
        youtube.search().list().execute.side_effect = [
            {"items": [{"id": {"channelId": "fixture-channel"}}]},
            {"items": [{"id": {"videoId": str(i)}, "snippet": {
                "title": f"Video {i}", "publishedAt": "2026-01-01T12:00:00Z",
            }} for i in range(10)], "nextPageToken": "ignored-after-cap"},
        ]
        youtube.videos().list().execute.return_value = {"items": [{
            "snippet": {"description": "Fixture"}, "statistics": {"viewCount": "1"},
            "contentDetails": {"duration": "PT1M"},
        }]}
        with patch.object(video_scraper.googleapiclient.discovery, "build", return_value=youtube):
            with contextlib.redirect_stdout(io.StringIO()):
                video_scraper.scrape_channel("fixture", settings)
        youtube.playlists.assert_not_called()
        youtube.playlistItems.assert_not_called()
        self.assertEqual(youtube.search().list().execute.call_count, 2)
        self.assertEqual(youtube.videos().list().execute.call_count, 5)
        with (settings.output_dir / "combined_video_data.csv").open(newline="", encoding="utf8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row["Playlists"] == "" for row in rows))

    def test_unavailable_video_details_still_consume_candidate_limit(self):
        youtube = Mock()
        youtube.search().list().execute.return_value = {"items": [
            {"id": {"videoId": str(i)}} for i in range(20)
        ], "nextPageToken": "more"}
        youtube.videos().list().execute.return_value = {"items": []}
        self.assertEqual(video_scraper.get_all_videos(youtube, "channel", [], max_videos=5), [])
        self.assertEqual(youtube.videos().list().execute.call_count, 5)
        self.assertEqual(youtube.search().list().execute.call_count, 1)

    def test_playlist_map_limit_stops_before_the_next_page(self):
        youtube = Mock()
        youtube.search().list().execute.return_value = {"items": [
            {"id": {"videoId": str(i)}, "snippet": {"title": "Fixture"}}
            for i in range(10)
        ], "nextPageToken": "more"}
        rows = playlist_scraper.build_video_playlist_map(youtube, "channel", [], max_videos=3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(youtube.search().list().execute.call_count, 1)

    def test_live_scope_configuration_rejects_invalid_values(self):
        clean = {k: v for k, v in os.environ.items() if not k.startswith("YOUTUBE_")}
        for values in [
            {"YOUTUBE_MAX_VIDEOS": "-1"}, {"YOUTUBE_MAX_VIDEOS": "1.5"},
            {"YOUTUBE_INCLUDE_PLAYLISTS": "maybe"},
        ]:
            with self.subTest(values=values):
                with patch.dict(os.environ, clean | values, clear=True):
                    with patch("config.load_dotenv"):
                        with self.assertRaises(ValueError):
                            load_settings()


if __name__ == "__main__":
    unittest.main()
