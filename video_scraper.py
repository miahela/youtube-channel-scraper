"""
Collects channel video search results via the YouTube Data API v3.

Outputs:
    combined_video_data.csv  —  one row per video with title, URL, view count,
                                duration, chapter markers, description, and
                                any playlists the video belongs to.
"""

import csv
import re

import googleapiclient.discovery
from googleapiclient.errors import HttpError

from config import load_settings


def get_channel_id(youtube, username):
    response = (
        youtube.search()
        .list(q=username, type="channel", part="snippet", maxResults=1)
        .execute()
    )
    items = response.get("items", [])
    if not items:
        raise ValueError(f"Channel '{username}' not found.")
    return items[0]["id"]["channelId"]


def fetch_playlist_video_ids(youtube, playlist_id):
    """Return all video IDs in a playlist, handling pagination."""
    video_ids = []
    page_token = None
    while True:
        response = (
            youtube.playlistItems()
            .list(
                playlistId=playlist_id,
                part="snippet",
                maxResults=50,
                pageToken=page_token,
            )
            .execute()
        )
        for item in response.get("items", []):
            video_ids.append(item["snippet"]["resourceId"]["videoId"])
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return video_ids


def get_channel_playlists(youtube, channel_id):
    """Return playlist metadata (title, ID, contained video IDs) for a channel."""
    playlists = []
    page_token = None
    while True:
        response = (
            youtube.playlists()
            .list(
                channelId=channel_id,
                part="snippet",
                maxResults=50,
                pageToken=page_token,
            )
            .execute()
        )
        if "items" not in response:
            break
        for item in response["items"]:
            pid = item["id"]
            playlists.append(
                {
                    "title": item["snippet"]["title"],
                    "id": pid,
                    "video_ids": fetch_playlist_video_ids(youtube, pid),
                }
            )
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return playlists


def get_all_videos(youtube, channel_id, playlists, max_videos=0):
    """Fetch metadata for every unique video on a channel."""
    videos = []
    seen_ids = set()
    page_token = None

    while True:
        response = (
            youtube.search()
            .list(
                channelId=channel_id,
                type="video",
                part="snippet",
                maxResults=min(50, max_videos) if max_videos else 50,
                pageToken=page_token,
            )
            .execute()
        )
        if "items" not in response:
            break

        for item in response["items"]:
            video_id = item["id"]["videoId"]
            if video_id in seen_ids:
                continue
            if max_videos and len(seen_ids) >= max_videos:
                break
            seen_ids.add(video_id)

            # Fetch stats, full description, and duration in a single API call
            details_response = (
                youtube.videos()
                .list(part="statistics,snippet,contentDetails", id=video_id)
                .execute()
            )
            if not details_response.get("items"):
                continue

            detail = details_response["items"][0]
            description = detail["snippet"]["description"]
            chapter_markers = re.findall(r"\d{0,2}:\d{2}", description)
            published = (
                item["snippet"]["publishedAt"].replace("T", " ").replace("Z", "")
            )

            videos.append(
                {
                    "Title": item["snippet"]["title"],
                    "ID": video_id,
                    "URL": f"https://www.youtube.com/watch?v={video_id}",
                    "Published Date": published,
                    "View Count": detail["statistics"].get("viewCount", "0"),
                    "Duration": detail["contentDetails"]["duration"],
                    "Chapter Markers": ", ".join(chapter_markers),
                    "Description": description,
                    "Playlists": ", ".join(
                        p["title"] for p in playlists if video_id in p["video_ids"]
                    ),
                }
            )

        if max_videos and len(seen_ids) >= max_videos:
            break
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return sorted(videos, key=lambda v: v["Published Date"], reverse=True)


def scrape_channel(username=None, settings=None):
    settings = settings or load_settings(require_api=True)
    username = username or settings.channel
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=settings.api_key)

    print(f"Looking up channel '{username}'...")
    channel_id = get_channel_id(youtube, username)
    print(f"  Resolved channel ID: {channel_id}")

    if settings.include_playlists:
        print("Fetching playlists...")
        playlists = get_channel_playlists(youtube, channel_id)
        print(f"  Found {len(playlists)} playlists.")
    else:
        playlists = []
        print("Playlist collection disabled; playlist fields will be empty.")

    print("Fetching videos...")
    print(f"  Candidate video limit: {settings.max_videos or 'unlimited'}")
    videos = get_all_videos(youtube, channel_id, playlists, max_videos=settings.max_videos)
    print(f"  Found {len(videos)} unique videos.")

    output_file = settings.output_dir / "combined_video_data.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "Title",
        "ID",
        "URL",
        "Published Date",
        "View Count",
        "Duration",
        "Chapter Markers",
        "Description",
        "Playlists",
    ]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(videos)

    print(f"Saved to {output_file}.")


if __name__ == "__main__":
    try:
        scrape_channel()
    except HttpError as e:
        # HttpError text can include the request URL and its API key.
        raise SystemExit(
            f"YouTube API request failed (HTTP {e.resp.status}). "
            "Check API access, key restrictions, and available quota."
        ) from None
    except (OSError, ValueError) as e:
        raise SystemExit(f"Setup or file error: {e}") from None
    except (KeyError, TypeError, IndexError):
        raise SystemExit("Unexpected YouTube response fields. No complete export was written.") from None
    except KeyboardInterrupt:
        raise SystemExit("Interrupted. The API export is written only after collection completes.") from None
