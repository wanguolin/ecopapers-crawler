import requests
from fake_useragent import UserAgent
import time
from bs4 import BeautifulSoup
import json
import os
import re


class EconPapersCrawler:
    def __init__(self):
        """Initialize the crawler with configuration"""
        self.base_url = "https://econpapers.repec.org/scripts/search.pf"
        self.output_file = "papers_data.json"
        self.sleep_time = 1.5  # Sleep time in seconds (reduced from 5 to 1.5)
        self.papers_data = {}  # Store all papers data

    def parse_paper_info(self, paper_li):
        """Parse single paper information from li element"""
        try:
            paper_info = {}

            # Title and URL
            title_link = paper_li.find("a")
            if title_link:
                paper_info["title"] = title_link.text.strip()
                paper_info["url"] = f"https://econpapers.repec.org{title_link['href']}"

            # Authors
            authors = paper_li.find("i")
            if authors:
                paper_info["authors"] = authors.text.strip()

            # Institution and Year
            small_text = paper_li.find("small")
            if small_text:
                # Institution
                inst_match = re.search(r"from\s+<i>(.*?)</i>", str(small_text))
                if inst_match:
                    paper_info["institution"] = inst_match.group(1).strip()

                # Year
                year_match = re.search(r"\((\d{4})\)", str(small_text))
                if year_match:
                    paper_info["year"] = year_match.group(1)

                # Keywords
                keywords_match = re.search(
                    r"<b>Keywords:</b>(.*?)<br>", str(small_text)
                )
                if keywords_match:
                    paper_info["keywords"] = keywords_match.group(1).strip()

                # JEL codes
                jel_match = re.search(r"<b>JEL-codes:</b>(.*?)<br>", str(small_text))
                if jel_match:
                    paper_info["jel_codes"] = jel_match.group(1).strip()

                # Dates
                created_match = re.search(
                    r"<b>Created/Revised:</b>\s*([\d-]+)", str(small_text)
                )
                if created_match:
                    paper_info["created_date"] = created_match.group(1)

                modified_match = re.search(
                    r"<b>Added/Modified:</b>\s*([\d-]+)", str(small_text)
                )
                if modified_match:
                    paper_info["modified_date"] = modified_match.group(1)

            return paper_info
        except Exception as e:
            print(f"Error parsing paper info: {e}")
            return None

    def fetch_page(self, page_num):
        """Fetch a specific page"""
        ua = UserAgent()
        headers = {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        params = {
            "jel": "G14",
            "ni": "",
            "inpage": "1000",
            "pg": str(page_num) if page_num > 1 else None,
        }

        try:
            print(
                f"Waiting {self.sleep_time} seconds before fetching page {page_num}..."
            )
            time.sleep(self.sleep_time)
            response = requests.get(
                self.base_url, params=params, headers=headers, timeout=30
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching page {page_num}: {e}")
            return None

    def process_page(self, html_content, page_num):
        """Process page content and extract paper information"""
        if not html_content:
            return False

        soup = BeautifulSoup(html_content, "html.parser")

        # Extract max page number from the first page
        if page_num == 1:
            page_info = soup.find(string=re.compile(r"page \d+ of \d+"))
            if page_info:
                match = re.search(r"page \d+ of (\d+)", page_info)
                if match:
                    self.max_pages = int(match.group(1))
                    print(f"Total pages to process: {self.max_pages}")

        # Extract papers
        papers = []
        paper_items = soup.find_all("li")
        for item in paper_items:
            if item.find("a", href=re.compile(r"/paper/")):
                paper_info = self.parse_paper_info(item)
                if paper_info:
                    papers.append(paper_info)

        if papers:
            self.papers_data[f"page_{page_num}"] = papers
            print(f"Found {len(papers)} papers on page {page_num}")
            return True
        return False

    def save_data(self):
        """Save all collected data to JSON file"""
        try:
            with open(self.output_file, "w", encoding="utf-8") as f:
                json.dump(self.papers_data, f, indent=2, ensure_ascii=False)
            print(f"\nSuccessfully saved all data to {self.output_file}")
        except Exception as e:
            print(f"Error saving data: {e}")

    def crawl(self):
        """Main crawling function"""
        print("Starting fresh crawl...")
        self.papers_data = {}  # Reset data
        page_num = 1

        # Process first page to get total pages
        html_content = self.fetch_page(page_num)
        if not html_content or not self.process_page(html_content, page_num):
            print("Failed to process first page. Exiting.")
            return

        # Process remaining pages

        page_num += 1
        while page_num <= getattr(self, "max_pages", 1):
            html_content = self.fetch_page(page_num)
            if not html_content or not self.process_page(html_content, page_num):
                print(f"Failed to process page {page_num}. Stopping.")
                break
            page_num += 1

        # Save all collected data

        self.save_data()
        print("\nCrawling completed!")


if __name__ == "__main__":
    crawler = EconPapersCrawler()
    crawler.crawl()
