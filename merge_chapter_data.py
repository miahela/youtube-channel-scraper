"""
Merges data_s.json and data_s2.json into a single datafinal.json.

Run this after chapter_scraper.py to combine results from multiple scraping sessions.
"""

import json

merged = {}

for source_file in ("data/data_s.json", "data/data_s2.json"):
    with open(source_file) as f:
        data = json.load(f)
    for key, value in data.items():
        if key not in merged:
            merged[key] = value

print(f"Total videos with chapter data: {len(merged)}")

with open("data/datafinal.json", "w") as f:
    json.dump(merged, f)

print("Saved to data/datafinal.json")
