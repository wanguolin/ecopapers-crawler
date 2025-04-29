# EconPapers Crawler

A Python-based crawler that automatically fetches and structures academic paper information from EconPapers (RePEc) with JEL code G14 (Information and Market Efficiency; Event Studies; Insider Trading).

## Features

- Fetches paper information including titles, authors, institutions, and metadata
- Supports pagination with checkpoint saving for interrupted crawls
- Structures data in JSON format for easy access
- Runs monthly via GitHub Actions to keep data updated
- Includes rate limiting to be respectful to the server

## Data Structure

The crawler saves data in `papers_data.json` with the following structure:

```json
{
  "page_1": [
    {
      "title": "Paper Title",
      "url": "Paper URL",
      "authors": "Author Names",
      "institution": "Institution Name",
      "year": "Publication Year",
      "keywords": "Keywords",
      "jel_codes": "JEL Codes",
      "created_date": "Creation Date",
      "modified_date": "Modification Date"
    },
    ...
  ],
  "page_2": [...],
  ...
}
```

## Usage

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the crawler:
```bash
python crawler.py
```

The crawler will automatically:
- Resume from the last checkpoint if interrupted
- Save progress after each page
- Structure and save data to `papers_data.json`

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