# EconPapers Trading Strategy Library

A set of tools for crawling, processing, and analyzing economics papers from EconPapers to build a library of trading strategy papers.

## Overview

This project implements a workflow to collect, analyze, and categorize economics papers with a focus on trading strategies:

1. **Crawl Basic Data** (`get_abstracts.py`) - Fetches paper metadata from EconPapers search results
2. **Enrich Data** (`paper_details_updater.py`) - Adds abstracts and download links to paper data
3. **Analyze Papers** (`review_strategy_paper.py`) - Uses AI to determine if papers describe trading strategies
4. **Generate Library** (`generate_library.py`) - Creates a curated library of trading strategy papers

## Manually Install Requirements

```
git commit --allow-empty -m "force update"
git push
# Unless it will be scheduled as running monthly
```

Install the requirements using:

```bash
pip install -r requirements.txt
```

## Environment Setup

Create a `.env` file in the project root with the following API keys:

```
DEEPSEEK_OFFICIAL_API_KEY=your_deepseek_api_key_here
SILICONFLOW_APIKEY=your_siliconflow_api_key_here
```

These API keys are used by the `review_strategy_paper.py` script to analyze paper abstracts.

## Workflow Usage

### Step 1: Crawl Papers Basic Data

Run the crawler to fetch basic paper metadata:

```bash
python get_abstracts.py
```

This will generate a `papers_data.json` file containing basic information about papers from EconPapers. The script will replace any existing file with fresh data.

### Step 2: Update Paper Details

Run the details updater to fetch abstracts and download links for each paper:

```bash
python paper_details_updater.py
```

This script reads `papers_data.json`, fetches additional details for papers not already processed, and updates `paper_details.json` with the results. It preserves existing paper details and only adds new ones.

#### Command-line Options

The details updater supports these command-line options:

```
usage: paper_details_updater.py [-h] [--input INPUT] [--output OUTPUT] [--threads THREADS]

Update paper details with abstracts and download links

optional arguments:
  -h, --help            show this help message and exit
  --input INPUT, -i INPUT
                        Input JSON file with paper data (default: papers_data.json)
  --output OUTPUT, -o OUTPUT
                        Output JSON file for paper details (default: paper_details.json)
  --threads THREADS, -t THREADS
                        Number of concurrent threads (default: 4)
```

### Step 3: Review Papers for Trading Strategies

Run the strategy reviewer to identify papers that describe trading strategies:

```bash
python review_strategy_paper.py
```

This script reads `paper_details.json`, analyzes the abstracts using DeepSeek AI through the SiliconFlow API, and generates `strategy_reviews.json` containing the analysis results. Make sure your `.env` file is properly configured before running this script.

### Step 4: Generate Trading Strategy Library

Finally, generate the library of trading strategy papers:

```bash
python generate_library.py
```

This script combines data from `paper_details.json` and `strategy_reviews.json` to create `library.json`, which contains only papers identified as describing trading strategies. This file can be loaded by the alpha.isnow.ai website.

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
    "date": "YYYY",
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

### `strategy_reviews.json`

Contains the AI analysis of whether papers describe trading strategies:

```json
{
  "https://econpapers.repec.org/paper/...": {
    "strategy": true,
    "reason": "This paper presents a quantifiable trading strategy based on...",
    "model": "Pro/deepseek-ai/DeepSeek-V3"
  },
  ...
}
```

### `library.json`

Contains only papers identified as trading strategies, formatted for use by alpha.isnow.ai:

```json
[
  {
    "title": "Paper Title",
    "abstract": "The paper abstract text...",
    "keywords": ["keyword1", "keyword2", ...],
    "eco_link": "https://econpapers.repec.org/paper/...",
    "reviewed_by": "Pro/deepseek-ai/DeepSeek-V3"
  },
  ...
]
```

## Notes

- The scripts respect rate limits by adding random delays between requests
- The paper_details_updater script uses multi-threading for efficiency
- The review_strategy_paper script skips papers that have already been reviewed
- All scripts save progress periodically to prevent data loss if interrupted

## Automated Updates

You can set up a cron job or scheduled task to run the full workflow monthly:

```bash
#!/bin/bash
cd /path/to/project
python get_abstracts.py
python paper_details_updater.py
python review_strategy_paper.py
python generate_library.py
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