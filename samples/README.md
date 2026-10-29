# Video metadata sample

The CSV contains eight distinct videos selected from an earlier channel export.
It illustrates the current export columns and is not a fresh API run.
Descriptions are shortened to 200 characters; other values are preserved.
Counts and metadata are historical snapshots.

The full channel dataset and repeated intermediate files have been removed
from the current working tree after a hash-verified backup outside the repo.
No Git history was rewritten.

New runs write to the ignored output/ folder. To inspect the sample in PowerShell:

    Import-Csv .\samples\videos.csv | Format-Table Title, ID, 'View Count'
