"""
Maps each video on a YouTube channel to the playlists it belongs to.

Outputs:
    video_playlist_link_data.csv  —  video title and playlist URLs for each video.
"""

import csv
import os

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


def build_video_playlist_map(youtube, channel_id, playlists):
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
                maxResults=50,
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
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return rows


def scrape_video_playlist_links(username):
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)

    print(f"Looking up channel '{username}'...")
    channel_id = get_channel_id(youtube, username)

    print("Fetching playlists...")
    playlists = get_playlists(youtube, channel_id)
    print(f"  Found {len(playlists)} playlists.")

    print("Mapping videos to playlists...")
    rows = build_video_playlist_map(youtube, channel_id, playlists)

    output_file = "data/video_playlist_link_data.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Video Title", "Playlist URLs"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows to {output_file}.")


if __name__ == "__main__":
    scrape_video_playlist_links("baldandbankrupt")
