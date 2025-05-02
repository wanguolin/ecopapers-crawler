# EconPapers Crawler and Updater

A set of tools for crawling and updating economics paper metadata from EconPapers.

## Overview

This project consists of two main components:

1. **Crawler** (`crawler.py`) - Fetches basic paper metadata from EconPapers search results
2. **Details Updater** (`paper_details_updater.py`) - Enriches the paper data with abstracts and download links

## Requirements

```
requests
fake_useragent
beautifulsoup4
```

Install the requirements using:

```bash
pip install requests fake_useragent beautifulsoup4
```

## Usage

### Step 1: Run the Crawler

First, run the crawler to fetch basic paper metadata:

```bash
python crawler.py
```

This will generate a `papers_data.json` file containing basic information about papers.

### Step 2: Run the Details Updater

Next, run the details updater to fetch abstracts and download links for each paper:

```bash
python paper_details_updater.py
```

This will read the `papers_data.json` file, fetch additional details for each paper, and save the results to `paper_details.json`.

#### Command-line Options

The details updater supports various command-line options:

```
usage: paper_details_updater.py [-h] [--input INPUT] [--output OUTPUT]
                               [--threads THREADS] [--min-sleep MIN_SLEEP]
                               [--max-sleep MAX_SLEEP] [--retries RETRIES]
                               [--checkpoint-minutes CHECKPOINT_MINUTES]
                               [--verbose]

Update paper details with abstracts and download links

optional arguments:
  -h, --help            show this help message and exit
  --input INPUT, -i INPUT
                        Input JSON file with paper data (default: papers_data.json)
  --output OUTPUT, -o OUTPUT
                        Output JSON file for paper details (default: paper_details.json)
  --threads THREADS, -t THREADS
                        Number of concurrent threads (default: 4)
  --min-sleep MIN_SLEEP
                        Minimum sleep time between requests in seconds (default: 1.0)
  --max-sleep MAX_SLEEP
                        Maximum sleep time between requests in seconds (default: 3.0)
  --retries RETRIES, -r RETRIES
                        Maximum number of retries for failed requests (default: 3)
  --checkpoint-minutes CHECKPOINT_MINUTES, -c CHECKPOINT_MINUTES
                        Time interval in minutes for automatic checkpoint saves (default: 15)
  --verbose, -v         Enable verbose logging (debug level)
```

#### Examples

Run with 8 threads and more aggressive timing:

```bash
python paper_details_updater.py --threads 8 --min-sleep 0.5 --max-sleep 2.0
```

Use custom input and output files:

```bash
python paper_details_updater.py -i my_papers.json -o my_paper_details.json
```

Modify checkpoint interval for more frequent saves:

```bash
python paper_details_updater.py --checkpoint-minutes 5
```

## Features

### Crawler (`crawler.py`)

- Fetches paper metadata from EconPapers search results
- Extracts title, authors, institution, year, keywords, JEL codes, and dates
- Handles pagination automatically
- Uses rate limiting to avoid server overload

### Details Updater (`paper_details_updater.py`)

- Multi-threaded processing for efficient downloading
- Robust error handling with automatic retries
- Respects existing data (only processes new papers)
- Extracts abstracts and download links
- Detailed logging
- Automatic backup of output file
- Automatic checkpointing every 100 papers and at regular time intervals
- Graceful shutdown on keyboard interrupt
- Configurable through command-line arguments

## Data Structure

### `papers_data.json`

Contains basic paper information organized by pages:

```json
{
  "page_1": [
    {
      "title": "Paper Title",
      "url": "https://econpapers.repec.org/paper/...",
      "authors": "Author Names",
      "year": "YYYY",
      "institution": "Institution Name",
      "keywords": "keyword1, keyword2",
      "jel_codes": "G14, ...",
      "created_date": "YYYY-MM-DD",
      "modified_date": "YYYY-MM-DD"
    },
    ...
  ],
  "page_2": [
    ...
  ]
}
```

### `paper_details.json`

Contains enriched paper information with abstracts and download links:

```json
{
  "https://econpapers.repec.org/paper/...": {
    "title": "Paper Title",
    "url": "https://econpapers.repec.org/paper/...",
    "authors": "Author Names",
    "year": "YYYY",
    "institution": "Institution Name",
    "keywords": "keyword1, keyword2",
    "jel_codes": "G14, ...",
    "created_date": "YYYY-MM-DD",
    "modified_date": "YYYY-MM-DD",
    "abstract": "The paper abstract text...",
    "download_links": [
      {
        "href": "original href from page",
        "url": "decoded direct URL",
        "text": "link text"
      },
      ...
    ]
  },
  ...
}
```

## Notes

- The script respects rate limits by adding random delays between requests
- Dual checkpointing system for maximum reliability:
  - Count-based checkpoints: Saves progress after every 100 papers processed
  - Time-based checkpoints: Saves progress every 15 minutes (configurable)
- If interrupted, the script will save its progress
- The script creates backups of the output file to prevent data loss

## Automated Updates

This repository is configured with GitHub Actions to run the crawler monthly and automatically commit any updates to the papers data.

### Manual Trigger

You can manually trigger the workflow in two ways:

1. **Via GitHub Web Interface**:
   - Go to your repository on GitHub
   - Click the "Actions" tab
   - Select "Monthly Paper Crawler"
   - Click "Run workflow"
   - Choose the branch to run on

2. **Via GitHub CLI**:
   ```bash
   # Install GitHub CLI if you haven't
   brew install gh  # macOS
   # Login to GitHub
   gh auth login
   # Trigger the workflow
   gh workflow run "Monthly Paper Crawler"
   # Check the workflow status
   gh run list --workflow "Monthly Paper Crawler"
   ```

## License

MIT License

Copyright (c) 2024 Guo Lin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE. 