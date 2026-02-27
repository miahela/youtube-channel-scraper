"""
Scrapes all videos from a YouTube channel via the YouTube Data API v3.

Outputs:
    combined_video_data.csv  —  one row per video with title, URL, view count,
                                duration, chapter markers, description, and
                                any playlists the video belongs to.
"""

import csv
import os
import re

import googleapiclient.discovery
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise EnvironmentError(
        "YOUTUBE_API_KEY not set. Copy .env.example to .env and fill in your key."
    )


def get_channel_id(youtube, username):
    response = (
        youtube.search()
        .list(q=username, type="channel", part="id", maxResults=1)
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


def get_all_videos(youtube, channel_id, playlists):
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
                maxResults=50,
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

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return sorted(videos, key=lambda v: v["Published Date"], reverse=True)


def scrape_channel(username):
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)

    print(f"Looking up channel '{username}'...")
    channel_id = get_channel_id(youtube, username)

    print("Fetching playlists...")
    playlists = get_channel_playlists(youtube, channel_id)
    print(f"  Found {len(playlists)} playlists.")

    print("Fetching videos...")
    videos = get_all_videos(youtube, channel_id, playlists)
    print(f"  Found {len(videos)} unique videos.")

    output_file = "data/combined_video_data.csv"
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
    scrape_channel("baldandbankrupt")
