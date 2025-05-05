import requests
import time
import json
import os
import logging
import argparse
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote
from fake_useragent import UserAgent
import threading
import queue
import random


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("paper_updater.log"), logging.StreamHandler()],
)
logger = logging.getLogger("PaperDetailsUpdater")


class PaperDetailsUpdater:
    def __init__(
        self,
        input_file="papers_data.json",
        output_file="paper_details.json",
        num_threads=4,
    ):
        self.input_file = input_file
        self.output_file = output_file
        self.num_threads = num_threads
        self.paper_details = {}
        self.papers_queue = queue.Queue()
        self.lock = threading.Lock()
        self.processed_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.total_papers = 0
        self.session = requests.Session()

    def load_existing_details(self):
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, "r", encoding="utf-8") as f:
                    self.paper_details = json.load(f)
                logger.info(f"Loaded {len(self.paper_details)} existing paper details")
            except Exception as e:
                logger.error(f"Error loading existing paper details: {e}")
                self.paper_details = {}
        else:
            self.paper_details = {}

    def load_papers_data(self):
        try:
            with open(self.input_file, "r", encoding="utf-8") as f:
                papers_data = json.load(f)

            page_num = 1
            total_papers = 0

            while f"page_{page_num}" in papers_data:
                page_key = f"page_{page_num}"
                papers = papers_data.get(page_key, [])

                for paper in papers:
                    url = paper.get("url")
                    if url and url not in self.paper_details:
                        self.papers_queue.put(paper)
                        total_papers += 1
                    elif url:
                        self.skipped_count += 1

                page_num += 1

            self.total_papers = total_papers
            logger.info(
                f"Loaded {total_papers} papers for processing, skipped {self.skipped_count} already processed"
            )
            return total_papers > 0
        except Exception as e:
            logger.error(f"Error loading papers data: {e}")
            return False

    def extract_download_links(self, soup):
        download_links = []
        download_sections = soup.find_all("p")

        for section in download_sections:
            section_text = str(section)
            if "<b>Downloads:</b>" in section_text:
                links = section.find_all("a")
                for link in links:
                    href = link.get("href")
                    text = link.text.strip()
                    if href and text:
                        redirect_match = re.search(r"u=([^;]+);", href)
                        final_url = redirect_match.group(1) if redirect_match else href

                        if "%3A" in final_url or "%2F" in final_url:
                            try:
                                final_url = unquote(final_url)
                            except:
                                pass

                        download_links.append(
                            {
                                "href": href,
                                "url": final_url,
                                "text": text,
                            }
                        )
                break

        return download_links

    def extract_abstract(self, soup):
        abstract = None

        abstract_paragraphs = soup.find_all("p")
        for p in abstract_paragraphs:
            p_text = str(p)
            if "<b>Abstract:</b>" in p_text:
                abstract_match = re.search(
                    r"<b>Abstract:</b>(.*?)</p>", p_text, re.DOTALL | re.IGNORECASE
                )
                if abstract_match:
                    abstract = abstract_match.group(1).strip()
                    break

        if not abstract:
            abstract_div = soup.find(
                "div", class_=lambda x: x and "abstract" in x.lower()
            )
            if abstract_div:
                abstract = abstract_div.get_text().strip()
                abstract = re.sub(
                    r"^Abstract[:\\s]*", "", abstract, flags=re.IGNORECASE
                )

        return abstract

    def get_random_headers(self):
        ua = UserAgent()
        return {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def fetch_paper_details(self, paper):
        url = paper.get("url")
        if not url:
            return None

        logger.info(f"Fetching details for paper: {paper.get('title')[:50]}...")

        try:
            time.sleep(random.uniform(1.0, 3.0))
            headers = self.get_random_headers()
            response = self.session.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            paper_detail = {
                "title": paper.get("title", ""),
                "url": url,
                "authors": paper.get("authors", ""),
                "date": paper.get("date", ""),
                "abstract": self.extract_abstract(soup),
                "download_links": self.extract_download_links(soup),
            }

            return paper_detail

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def worker(self):
        thread_name = threading.current_thread().name
        logger.info(f"Starting worker thread {thread_name}")

        try:
            while not self.papers_queue.empty():
                try:
                    paper = self.papers_queue.get(timeout=1)
                    url = paper.get("url")

                    if url and url not in self.paper_details:
                        paper_detail = self.fetch_paper_details(paper)

                        if paper_detail:
                            with self.lock:
                                self.paper_details[url] = paper_detail
                                self.processed_count += 1
                        else:
                            with self.lock:
                                self.failed_count += 1

                        logger.info(
                            f"Progress: {self.processed_count}/{self.total_papers} processed, {self.failed_count} failed"
                        )

                    self.papers_queue.task_done()

                except queue.Empty:
                    break
                except Exception as e:
                    logger.error(f"Error in worker thread: {e}")
                    try:
                        self.papers_queue.task_done()
                    except:
                        pass
        finally:
            logger.info(f"Worker thread {thread_name} finished")

    def save_details(self):
        try:
            with self.lock:
                with open(self.output_file, "w", encoding="utf-8") as f:
                    json.dump(self.paper_details, f, indent=2, ensure_ascii=False)
                logger.info(
                    f"Saved {len(self.paper_details)} paper details to {self.output_file}"
                )
        except Exception as e:
            logger.error(f"Error saving paper details: {e}")

    def run(self):
        logger.info("Starting paper details updater...")

        self.load_existing_details()

        if not self.load_papers_data():
            logger.info("No papers to process. Exiting.")
            return

        logger.info(
            f"Starting {self.num_threads} worker threads to process {self.total_papers} papers"
        )

        try:
            threads = []
            for i in range(self.num_threads):
                t = threading.Thread(target=self.worker, name=f"Worker-{i+1}")
                t.daemon = True
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            self.save_details()

            logger.info(f"Processing completed!")
            logger.info(f"Total papers processed: {self.processed_count}")
            logger.info(f"Total papers skipped: {self.skipped_count}")
            logger.info(f"Total papers failed: {self.failed_count}")

        except KeyboardInterrupt:
            logger.info("Interrupted. Saving progress...")
            self.save_details()
            return


def parse_args():
    parser = argparse.ArgumentParser(
        description="Update paper details with abstracts and download links"
    )
    parser.add_argument(
        "--input",
        "-i",
        default="papers_data.json",
        help="Input JSON file with paper data",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="paper_details.json",
        help="Output JSON file for paper details",
    )
    parser.add_argument(
        "--threads", "-t", type=int, default=4, help="Number of concurrent threads"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    updater = PaperDetailsUpdater(
        input_file=args.input,
        output_file=args.output,
        num_threads=args.threads,
    )

    updater.run()
