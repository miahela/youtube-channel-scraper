# YouTube Channel Scraper

A Python scraper that collects complete metadata for every video on a YouTube channel using the YouTube Data API v3 and Selenium.

Built as a data collection project targeting a channel. The collected dataset covers **461 unique videos** including titles, view counts, durations, chapter timestamps, and playlist associations.

## Features

- **Full channel scrape** — paginates through all videos with deduplication
- **Playlist mapping** — links each video to the playlists it belongs to
- **Chapter extraction** — uses Selenium to scrape chapter timestamps directly from YouTube's UI
- **Efficient API usage** — fetches statistics, description, and duration in a single API call per video

## Project Structure

```
youtube-channel-scraper/
├── video_scraper.py        # Main scraper — fetches all video metadata + playlist associations
├── playlist_scraper.py     # Maps each video to the playlist URLs it belongs to
├── chapter_scraper.py      # Selenium scraper that extracts chapter timestamps
├── selenium_manager.py     # Selenium WebDriver wrapper
├── merge_chapter_data.py   # Merges intermediate chapter JSON files into one
├── data/
│   ├── combined_video_data_noduplicate.csv   # Sample output — 461 videos
│   ├── playlist_data.csv                     # Sample output — channel playlists
│   ├── video_playlist_link_data.csv          # Sample output — video → playlist map
│   ├── datafinal.json                        # Sample output — chapter timestamps
│   └── filtered_video_ids.txt               # Input for chapter_scraper.py
├── .env.example
├── requirements.txt
└── README.md
```

## Sample Output

The `data/combined_video_data_noduplicate.csv` in this repo is the result of running `video_scraper.py` on a channel. Each row contains:

| Column | Description |
|--------|-------------|
| Title | Video title |
| ID | YouTube video ID |
| URL | Full watch URL |
| Published Date | Upload date |
| View Count | Total views at time of scrape |
| Duration | ISO 8601 duration (e.g. `PT12M34S`) |
| Chapter Markers | Timestamps parsed from video description |
| Description | Full video description |
| Playlists | Playlist(s) the video appears in |

## Setup

### Prerequisites

- Python 3.8+
- A YouTube Data API v3 key ([create one here](https://console.cloud.google.com/))
- Chrome and [ChromeDriver](https://chromedriver.chromium.org/) matching your Chrome version (for `chapter_scraper.py` only)

### Install

```bash
pip install -r requirements.txt
```

### Configure

Copy `.env.example` to `.env` and add your API key:

```bash
cp .env.example .env
```

```
YOUTUBE_API_KEY=your_key_here
```

## Usage

**Scrape all video metadata:**
```bash
python video_scraper.py
```
Outputs `data/combined_video_data.csv`

**Map videos to playlists:**
```bash
python playlist_scraper.py
```
Outputs `data/video_playlist_link_data.csv`

**Extract chapter timestamps (requires Chrome + ChromeDriver):**
```bash
python chapter_scraper.py
```
Reads `data/filtered_video_ids.txt`, outputs `data/data_s2.json`

**Merge chapter data files:**
```bash
python merge_chapter_data.py
```
Merges `data/data_s.json` + `data/data_s2.json` → `data/datafinal.json`

## Notes

- The YouTube Data API v3 has a daily quota of 10,000 units. Scraping a large channel will consume quota quickly. Plan accordingly or request a quota increase.
- ChromeDriver version must match your installed Chrome version.
- YouTube's UI structure changes occasionally; the Selenium selectors in `chapter_scraper.py` may need updating over time.
