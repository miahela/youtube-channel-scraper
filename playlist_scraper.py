"""
Maps each video on a YouTube channel to the playlists it belongs to.

Outputs:
    video_playlist_link_data.csv  —  video title and playlist URLs for each video.
"""

import csv

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


def get_playlists(youtube, channel_id):
    """Fetch all playlists and their video IDs for a channel."""
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
            playlist_id = item["id"]
            playlists.append(
                {
                    "title": item["snippet"]["title"],
                    "url": f"https://www.youtube.com/playlist?list={playlist_id}",
                    "video_ids": fetch_playlist_video_ids(youtube, playlist_id),
                }
            )
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return playlists


def build_video_playlist_map(youtube, channel_id, playlists, max_videos=0):
    """Return rows mapping each video to the playlist URLs it appears in."""
    rows = []
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
            playlist_urls = [
                p["url"] for p in playlists if video_id in p["video_ids"]
            ]
            rows.append(
                {
                    "Video Title": item["snippet"]["title"],
                    "Playlist URLs": ", ".join(playlist_urls),
                }
            )
            if max_videos and len(rows) >= max_videos:
                return rows
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return rows


def scrape_video_playlist_links(username=None, settings=None):
    settings = settings or load_settings(require_api=True)
    if not settings.include_playlists:
        raise ValueError("Enable YOUTUBE_INCLUDE_PLAYLISTS to run the playlist-mapping script")
    username = username or settings.channel
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=settings.api_key)

    print(f"Looking up channel '{username}'...")
    channel_id = get_channel_id(youtube, username)
    print(f"  Resolved channel ID: {channel_id}")

    print("Fetching playlists...")
    playlists = get_playlists(youtube, channel_id)
    print(f"  Found {len(playlists)} playlists.")

    print("Mapping videos to playlists...")
    rows = build_video_playlist_map(youtube, channel_id, playlists, max_videos=settings.max_videos)

    output_file = settings.output_dir / "video_playlist_link_data.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Video Title", "Playlist URLs"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows to {output_file}.")


if __name__ == "__main__":
    try:
        scrape_video_playlist_links()
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
