import requests
from fake_useragent import UserAgent
import time
from bs4 import BeautifulSoup, Tag
import json
import os
import re
import threading
import queue
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import logging
from urllib.parse import unquote, urljoin
import argparse
import datetime


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("paper_updater.log"), logging.StreamHandler()],
)
logger = logging.getLogger("PaperDetailsUpdater")


class PaperDetailsUpdater:
    def __init__(
        self,
        input_file="papers_data.json",
        output_file="paper_details.json",
        num_threads=4,
        sleep_time_range=(2.0, 3.0),
        max_retries=3,
        checkpoint_minutes=15,
    ):
        """
        Initialize the paper details updater with configuration

        Args:
            input_file: Path to the input JSON file containing paper data
            output_file: Path to the output JSON file for storing paper details
            num_threads: Number of concurrent threads for fetching details
            sleep_time_range: Range of sleep time between requests (min, max) in seconds
            max_retries: Maximum number of retries for failed requests
            checkpoint_minutes: Time interval in minutes for automatic checkpoint saves
        """
        self.input_file = input_file
        self.output_file = output_file
        self.num_threads = num_threads
        self.sleep_time_range = sleep_time_range
        self.max_retries = max_retries
        self.checkpoint_minutes = checkpoint_minutes
        self.paper_details = {}
        self.papers_queue = queue.Queue()
        self.lock = threading.Lock()
        self.active_threads = 0
        self.thread_lock = threading.Lock()
        self.processed_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.total_papers = 0
        self.session = requests.Session()
        self.last_checkpoint_time = datetime.datetime.now()
        self.checkpoint_lock = threading.Lock()
        self.running = True
        self.checkpoint_thread = None

    def load_existing_details(self):
        """
        Load existing paper details from output file if it exists
        """
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, "r", encoding="utf-8") as f:
                    self.paper_details = json.load(f)
                logger.info(f"Loaded {len(self.paper_details)} existing paper details")
            except Exception as e:
                logger.error(f"Error loading existing paper details: {e}")
                self.paper_details = {}
        else:
            logger.info(f"No existing details file found at {self.output_file}")
            self.paper_details = {}

    def checkpoint_monitor(self):
        """
        Monitor thread that saves checkpoints at regular time intervals
        """
        logger.info(
            f"Starting checkpoint monitor thread (every {self.checkpoint_minutes} minutes)"
        )

        while self.running:
            # Sleep for a short interval, checking if we should exit
            for _ in range(60):  # Check every second if we should exit
                if not self.running:
                    break
                time.sleep(1)

            if not self.running:
                break

            now = datetime.datetime.now()
            time_since_last_checkpoint = (
                now - self.last_checkpoint_time
            ).total_seconds() / 60

            if time_since_last_checkpoint >= self.checkpoint_minutes:
                with self.checkpoint_lock:
                    logger.info(
                        f"Time-based checkpoint: {time_since_last_checkpoint:.1f} minutes since last save"
                    )
                    self.save_details(is_checkpoint=True)
                    self.last_checkpoint_time = now

        logger.info("Checkpoint monitor thread exiting")

    def load_papers_data(self):
        """
        Load papers data from the input file and enqueue papers for processing
        """
        try:
            with open(self.input_file, "r", encoding="utf-8") as f:
                papers_data = json.load(f)

            page_num = 1
            total_papers = 0

            # Process pages from page_1 until a non-existent page is found
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
                f"Loaded {total_papers} papers for processing and skipped {self.skipped_count} already processed papers"
            )

        except Exception as e:
            logger.error(f"Error loading papers data: {e}")
            return False

        return total_papers > 0

    def clean_section_text(self, text, remove_section_markers=True):
        """
        Helper function to clean extracted section text

        Args:
            text: The text to clean
            remove_section_markers: Whether to remove common section markers

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove newlines and carriage returns
        cleaned = text.replace("\r", " ").replace("\n", " ")

        # Remove multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if remove_section_markers:
            # List of patterns that indicate section boundaries
            section_markers = [
                r"Keywords\s*:",
                r"JEL-codes\s*:",
                r"Date\s*:",
                r"New Economics Papers\s*:",
                r"References\s*:",
                r"Citations\s*:",
                r"Downloads\s*:",
                r"Related works\s*:",
                r"Export reference\s*:",
                r"Persistent link\s*:",
                r"Ordering information\s*:",
                r"Access Statistics\s*:",
                r"More\s+(?:papers|articles)\s+in",
                r"\(search for similar items in EconPapers\)",
                r"Bibliographic data for series",
            ]

            # Find first occurrence of any section marker
            first_marker_pos = len(cleaned)
            first_marker = None

            for marker in section_markers:
                match = re.search(marker, cleaned, re.IGNORECASE)
                if match and match.start() < first_marker_pos:
                    first_marker_pos = match.start()
                    first_marker = match.group(0)

            # If found, truncate at that position
            if first_marker_pos < len(cleaned):
                logger.debug(
                    f"Truncating at marker: '{first_marker}' at position {first_marker_pos}"
                )
                cleaned = cleaned[:first_marker_pos].strip()

        return cleaned

    def extract_abstract(self, soup):
        """
        Extract abstract from BeautifulSoup object

        Args:
            soup: BeautifulSoup object of the paper page

        Returns:
            String containing the abstract or None if not found
        """
        # Try to find abstract using various methods
        abstract = None

        # Method 1: Look for paragraph with Abstract: label
        abstract_paragraphs = soup.find_all("p")
        for p in abstract_paragraphs:
            p_text = str(p)
            if "<b>Abstract:</b>" in p_text:
                # Extract text after the Abstract: label
                abstract_match = re.search(
                    r"<b>Abstract:</b>(.*?)</p>", p_text, re.DOTALL | re.IGNORECASE
                )
                if abstract_match:
                    abstract = abstract_match.group(1).strip()
                    break

        # Method 2: If not found, try other common patterns
        if not abstract:
            abstract_div = soup.find(
                "div", class_=lambda x: x and "abstract" in x.lower()
            )
            if abstract_div:
                abstract = abstract_div.get_text().strip()
                # If there's a label, remove it
                abstract = re.sub(
                    r"^Abstract[:\\s]*", "", abstract, flags=re.IGNORECASE
                )

        return abstract

    def extract_download_links(self, soup):
        """
        Extract download links from BeautifulSoup object

        Args:
            soup: BeautifulSoup object of the paper page

        Returns:
            List of dictionaries containing download links information
        """
        download_links = []

        # Method 1: Look for Downloads section
        download_sections = soup.find_all("p")
        for section in download_sections:
            section_text = str(section)
            if "<b>Downloads:</b>" in section_text:
                links = section.find_all("a")
                for link in links:
                    href = link.get("href")
                    text = link.text.strip()
                    if href and text:
                        # Parse redirected URL if needed
                        redirect_match = re.search(r"u=([^;]+);", href)
                        final_url = redirect_match.group(1) if redirect_match else href

                        # URL decode if needed
                        if "%3A" in final_url or "%2F" in final_url:
                            try:
                                final_url = unquote(final_url)
                            except:
                                pass

                        download_links.append(
                            {
                                "href": href,  # Original href for reference
                                "url": final_url,  # Extracted final URL
                                "text": text,
                            }
                        )
                break

        # Method 2: If not found, look for any links in sections that might contain downloads
        if not download_links:
            download_divs = soup.find_all(
                ["div", "p"],
                string=lambda s: s and ("download" in s.lower() or "file" in s.lower()),
            )
            for div in download_divs:
                links = div.find_all("a")
                for link in links:
                    href = link.get("href")
                    text = link.text.strip()
                    if (
                        href
                        and text
                        and (
                            "pdf" in href.lower()
                            or "doc" in href.lower()
                            or "download" in href.lower()
                        )
                    ):
                        download_links.append({"href": href, "url": href, "text": text})

        return download_links

    def get_random_headers(self):
        """
        Generate random headers to mimic browser behavior

        Returns:
            Dictionary of HTTP headers
        """
        ua = UserAgent()
        return {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://econpapers.repec.org/scripts/search.pf",
            "Cache-Control": "max-age=0",
        }

    def fetch_with_retry(self, url, max_retries=None):
        """
        Fetch URL with retry mechanism

        Args:
            url: URL to fetch
            max_retries: Maximum number of retries (defaults to self.max_retries)

        Returns:
            Response object or None if all retries failed
        """
        if max_retries is None:
            max_retries = self.max_retries

        retries = 0
        while retries <= max_retries:
            try:
                # # Random sleep time to mimic human behavior (longer after retries)
                # sleep_time = random.uniform(*self.sleep_time_range) * (
                #     1 + retries * 0.5
                # )
                # time.sleep(sleep_time)

                # Get fresh headers for each attempt
                headers = self.get_random_headers()

                response = self.session.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response

            except requests.RequestException as e:
                retries += 1
                if retries > max_retries:
                    logger.error(
                        f"Failed to fetch {url} after {max_retries} retries: {e}"
                    )
                    return None

                logger.warning(f"Retry {retries}/{max_retries} for {url}: {e}")
                # Exponential backoff
                time.sleep(2**retries + random.uniform(0, 1))

        return None

    def fetch_paper_details(self, paper):
        """
        Fetch details for a specific paper by parsing the main content div.

        Args:
            paper: Dictionary containing basic paper information (title, url, etc.)

        Returns:
            Dictionary with structured extracted details or None on failure.
        """
        url = paper.get("url")
        if not url:
            logger.warning(f"Paper missing URL: {paper.get('title')}")
            return None

        logger.info(f"Fetching details for paper: {paper.get('title')[:50]}...")

            response = self.fetch_with_retry(url)
            if not response:
            return None  # Failure already logged by fetch_with_retry

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            base_url = "https://econpapers.repec.org"

            # Find the main content div - first try direct approach
            bodytext_div = soup.find("div", class_="bodytext")

            # If not found or empty, try finding it within table structure
            if not bodytext_div or not bodytext_div.text.strip():
                logger.debug(
                    f"Direct bodytext div approach failed for {url}, trying table structure"
                )
                # Look for the first table cell with bodytext class div
                table_cell = soup.find("td", attrs={"valign": "top"})
                if table_cell:
                    bodytext_div = table_cell.find("div", class_="bodytext")

            if not bodytext_div:
                logger.warning(f"Could not find 'bodytext' div for {url}")
                # Fallback or return minimal info? For now, return None.
                return None

            # Initialize details dictionary
            details = {
                "parsed_title": None,
                "parsed_authors": [],
                "parsed_journal_info": {"name": None, "details": None, "url": None},
                "abstract": None,
                "keywords": [],
                "jel_codes": [],
                "publication_date_str": None,
                "references_link": None,
                "citations_info": {"text": None, "count": None, "url": None},
                "download_links": [],
                "persistent_link": None,
                "access_stats_link": None,
                "related_works_search_link": None,
                "original_input_data": paper,  # Keep original input for reference
            }

            # --- Extract Title ---
            title_tag = bodytext_div.find("h1", class_="colored")
            if title_tag:
                details["parsed_title"] = title_tag.get_text(strip=True)

            # --- Extract Authors and Journal Info ---
            # Authors are typically in the first <p> after <h1>
            # Journal info is often in the second <p>
            paragraphs = bodytext_div.find_all(
                "p", recursive=False
            )  # Direct children paragraphs
            if paragraphs:
                # Author paragraph (heuristic: first one with <i> tags)
                author_p = None
                if title_tag:
                    first_p_after_h1 = title_tag.find_next_sibling("p")
                    if first_p_after_h1 and first_p_after_h1.find("i"):
                        author_p = first_p_after_h1
                if not author_p and paragraphs[0].find(
                    "i"
                ):  # Fallback to first <p> if heuristic fails
                    author_p = paragraphs[0]

                if author_p:
                    authors = []
                    # Find potential author names within <i> tags
                    author_tags = author_p.find_all("i")
                    for i_tag in author_tags:
                        name = i_tag.get_text(strip=True)
                        email = None
                        # Try to find associated email link
                        email_link = i_tag.find_next_sibling(
                            "a", href=lambda x: x and x.startswith("mailto:")
                        )
                        if email_link:
                            email = email_link["href"].replace("mailto:", "", 1)
                        # Add more robust email extraction if needed (e.g., from scripts)
                        if name:
                            authors.append({"name": name, "email": email})
                    details["parsed_authors"] = authors

                # Journal paragraph (heuristic: second one, contains <i><a> link)
                journal_p = None
                if (
                    len(paragraphs) > 1
                    and paragraphs[1].find("i")
                    and paragraphs[1].find("a")
                ):
                    journal_p = paragraphs[1]
                # Alternative: Look for specific link structure
                if not journal_p:
                    for p in paragraphs[:3]:  # Check first few paragraphs
                        journal_link = p.find(
                            "a", href=lambda x: x and "/article/" in x
                        )
                        if journal_link and journal_link.find_parent("i"):
                            journal_p = p
                            break

                if journal_p:
                    journal_link = journal_p.find(
                        "a", href=lambda x: x and "/article/" in x
                    )
                    journal_name = (
                        journal_link.get_text(strip=True) if journal_link else None
                    )
                    journal_url = journal_link["href"] if journal_link else None
                    # Get the full text of the paragraph, excluding the journal name itself if needed
                    journal_details_text = journal_p.get_text(strip=True)

                    # Resolve relative URL
                    if journal_url and journal_url.startswith("/"):
                        journal_url = urljoin(base_url, journal_url)

                    details["parsed_journal_info"] = {
                        "name": journal_name,
                        "details": journal_details_text,  # Full text like "Applied Economics Journal, 2012, vol. 19, issue 1, 46-67"
                        "url": journal_url,
                    }

            # === 1. Process Download Links First (Isolate Logic) ===
            download_p = None
            download_bold_tag = bodytext_div.find(
                "b",
                string=lambda text: text
                and text.strip().lower().startswith("downloads:"),
            )
            if download_bold_tag:
                # Ensure we get the immediate parent paragraph
                potential_p = download_bold_tag.find_parent("p")
                if potential_p:
                    download_p = potential_p  # Assign only if a <p> is found

            if download_p:
                # Find links *strictly* within this paragraph
                links_in_download_p = download_p.find_all(
                    "a", recursive=False
                )  # Check direct children first? Maybe not needed if structure is flat. Let's stick to find_all for now.

                if not links_in_download_p:
                    # Fallback if links are nested deeper within the p tag? Unlikely but consider. Let's try regular find_all first.
                    links_in_download_p = download_p.find_all("a")

                logger.debug(
                    f"Found {len(links_in_download_p)} links within the identified download paragraph for {url}"
                )

                for link in links_in_download_p:
                    original_href = link.get("href")
                    text = link.text.strip()

                    if not (original_href and text):
                        logger.debug(
                            f"Skipping incomplete link in download section: href={original_href}, text={text}"
                        )
                        continue  # Skip if link is incomplete

                    # Ensure original_href is an absolute URL if it's relative
                    if original_href.startswith("/"):
                        original_href = urljoin(base_url, original_href)

                    final_url = original_href  # Start with the original href (now potentially resolved)

                    # Parse redirected URL if needed
                    if "/scripts/redir.pf?u=" in original_href:
                        # Use the existing robust redirect parsing
                        redirect_match = re.search(r"u=([^;]+);", original_href)
                        if redirect_match:
                            final_url = redirect_match.group(1)
                            try:
                                final_url = unquote(final_url)
                            except Exception as decode_err:
                                logger.warning(
                                    f"Failed to decode redirect URL {final_url}: {decode_err}"
                                )
            else:
                logger.warning(
                                f"Could not parse redirect URL structure: {original_href}"
                            )

                    # Initialize details for this specific link
                    file_type = None
                    access_info = None
                    following_text = ""  # Accumulate text following the link

                    # Accumulate text from siblings (using the improved logic)
                    for sibling in link.next_siblings:
                        if getattr(sibling, "name", None) == "a":
                            break
                        if isinstance(sibling, str):
                            following_text += sibling.strip() + " "
                        elif getattr(sibling, "name", None) == "br":
                            following_text += " "
                    following_text = following_text.strip()

                    # Search accumulated text for file type and access info
                    if following_text:
                        format_match = re.search(
                            r"\(((?:application|text)/[^)]+)\)", following_text
                        )
                        if format_match:
                            file_type = format_match.group(1)
                        if (
                            "subscribers only" in following_text.lower()
                            or "subscription" in following_text.lower()
                        ):
                            access_match = re.search(
                                r"(subscription|subscribers only.*?)(?:\s|\(|$)[:]?",
                                following_text,
                                re.IGNORECASE,
                            )
                            access_info = (
                                access_match.group(1).strip()
                                if access_match
                                else following_text
                            )

                    # Fallback: If file type wasn't found in text, infer from URL
                    if file_type is None:
                        # Infer type from final_url
                        if final_url.lower().endswith(".pdf"):
                            file_type = "application/pdf"
                        elif final_url.lower().endswith((".doc", ".docx")):
                            file_type = "application/msword"
                        elif final_url.lower().endswith((".html", ".htm")):
                            file_type = "text/html"

                    # Add *only* the identified download link details
                    logger.debug(f"Appending download link: {final_url}")
                    details["download_links"].append(
                        {
                            "original_href": original_href,
                            "url": final_url,
                            "text": text,
                            "file_type": file_type,
                            "access_info": access_info,
                        }
                    )
            else:
                logger.info(f"No 'Downloads:' paragraph found for {url}")

            # === 2. Process Other Sections based on <b> tags ===
            all_bold_tags = bodytext_div.find_all("b")
            logger.debug(
                f"Found {len(all_bold_tags)} <b> tags to process for sections."
            )

            for i, bold_tag in enumerate(all_bold_tags):
                label = bold_tag.get_text(strip=True).lower()
                if not label:  # Skip empty <b> tags
                    continue

                # Skip the downloads label, as it was handled separately
                if label.startswith("downloads:"):
                    continue

                # Determine the end point for this section's content
                # It ends either at the next <b> tag or the end of the container
                section_end_node = None
                if i + 1 < len(all_bold_tags):
                    section_end_node = all_bold_tags[i + 1]

                # Extract all content between the current <b> and the next one (or the end)
                current_node = bold_tag.next_sibling
                section_content_nodes = []
                while current_node:
                    if current_node == section_end_node:
                        break
                    section_content_nodes.append(
                        str(current_node)
                    )  # Store as strings initially
                    current_node = current_node.next_sibling

                # Create a temporary soup object for the section content to parse easily
                section_html = "".join(section_content_nodes)
                section_soup = BeautifulSoup(section_html, "html.parser")

                logger.debug(f"Processing section: '{label}'")

                # --- Parse based on label ---
                if label == "abstract:":
                    # Find the specific paragraph that contains the abstract
                    abstract_p = bold_tag.find_parent("p")

                    if abstract_p:
                        # Extract just the content after the <b>Abstract:</b> tag within this paragraph
                        abstract_html = ""
                        current_node = bold_tag.next_sibling

                        while current_node and (
                            not isinstance(current_node, Tag)
                            or current_node.name != "b"
                        ):
                            if isinstance(current_node, str):
                                abstract_html += current_node
                            elif hasattr(current_node, "name"):
                                abstract_html += str(current_node)
                            current_node = current_node.next_sibling

                            # Safety check - if we've moved outside the paragraph, stop
                            if current_node and current_node.parent != abstract_p:
                                break

                        # Clean the extracted HTML
                        abstract_soup = BeautifulSoup(abstract_html, "html.parser")
                        raw_abstract = abstract_soup.get_text(strip=True)
                        cleaned_abstract = self.clean_section_text(raw_abstract)

                        # Second safety check: look for clear section markers within the extracted text
                        details["abstract"] = cleaned_abstract
                        logger.debug(f"Extracted abstract: {cleaned_abstract[:50]}...")
                    else:
                        # Fallback to the section_soup approach but with more cleanup
                        raw_text = section_soup.get_text(strip=True)
                        details["abstract"] = self.clean_section_text(raw_text)

                elif label == "keywords:":
                    keywords = []
                    links = section_soup.find_all("a")  # Find links within the segment
                    for link in links:
                        term = link.get_text(strip=True)
                        search_url = link.get("href")
                        if term:
                            # Resolve relative URL
                            if search_url and search_url.startswith("/"):
                                search_url = urljoin(base_url, search_url)
                            keywords.append({"term": term, "search_url": search_url})
                    # Only update if keywords were found in this specific segment
                    if keywords:
                        details["keywords"] = keywords

                elif label == "jel-codes:":
                    jel_codes = []
                    links = section_soup.find_all("a")  # Find links within the segment
                    for link in links:
                        code = link.get_text(strip=True)
                        search_url = link.get("href")
                        if code:
                            # Resolve relative URL
                            if search_url and search_url.startswith("/"):
                                search_url = urljoin(base_url, search_url)
                            jel_codes.append({"code": code, "search_url": search_url})
                    # Only update if JEL codes were found in this specific segment
                    if jel_codes:
                        details["jel_codes"] = jel_codes

                elif label == "date:":
                    # Date is usually just text after the <b> tag
                    details["publication_date_str"] = section_soup.get_text(strip=True)

                elif label == "references:":
                    # References might have multiple links
                    ref_links_found = []
                    links = section_soup.find_all("a")
                    for link in links:
                        ref_url = link.get("href")
                        if ref_url:
                            # Resolve relative URL
                            if ref_url.startswith("/"):
                                ref_url = urljoin(base_url, ref_url)
                            ref_links_found.append(
                                {"text": link.get_text(strip=True), "url": ref_url}
                            )
                    # Store all found reference links (or just the first if that's preferred)
                    # Let's store all for now
                    if ref_links_found:
                        details["references_links"] = (
                            ref_links_found  # Changed key name slightly
                        )
                        # If only the citec link was intended, need to filter by URL:
                        # citec_link = next((link for link in ref_links_found if 'citec.repec.org' in link['url']), None)
                        # if citec_link: details["references_link"] = citec_link['url']

                elif label == "citations:":
                    cit_link_tag = section_soup.find("a")  # Usually one link
                    if cit_link_tag:
                        cit_text = section_soup.get_text(strip=True)
                        count_match = re.search(r"\((\d+)\)", cit_text)
                        count = int(count_match.group(1)) if count_match else None
                        cit_url = cit_link_tag.get("href")
                        # Resolve relative URL
                        if cit_url and cit_url.startswith("/"):
                            cit_url = urljoin(base_url, cit_url)
                        details["citations_info"] = {
                            "text": cit_text,  # Store the full text like "View citations...(26)"
                            "count": count,
                            "url": cit_url,
                        }

                elif label == "persistent link:":
                    link_tag = section_soup.find("a")
                    if link_tag:
                        persistent_url = link_tag.get("href")
                        # Resolve relative URL
                        if persistent_url and persistent_url.startswith("/"):
                            persistent_url = urljoin(base_url, persistent_url)
                        details["persistent_link"] = persistent_url

                elif label == "related works:":
                    search_link = section_soup.find(
                        "a", href=lambda x: x and "search.pf" in x
                    )
                    if search_link:
                        related_url = search_link.get("href")
                        # Resolve relative URL
                        if related_url and related_url.startswith("/"):
                            related_url = urljoin(base_url, related_url)
                        details["related_works_search_link"] = related_url

                # Add other labels here if needed (e.g., 'Ordering information:')
                elif label == "ordering information:":
                    # Example: extract link or text
                    ordering_link = section_soup.find("a")
                    if ordering_link:
                        ordering_url = ordering_link.get("href")
                        if ordering_url and ordering_url.startswith("/"):
                            ordering_url = urljoin(base_url, ordering_url)
                        details["ordering_info"] = {
                            "url": ordering_url,
                            "text": section_soup.get_text(strip=True),
                        }
                    else:
                        details["ordering_info"] = {
                            "text": section_soup.get_text(strip=True)
                        }

            # --- Extract Access Statistics Link (Might be outside <b> sections) ---
            # Access stats link might be in its own paragraph without a bold tag
            # Check if already extracted via a label, otherwise search directly
            if not details.get("access_stats_link"):
                access_stats_link_tag = bodytext_div.find(
                    "a", href=lambda x: x and "logec.repec.org" in x
                )
                if access_stats_link_tag:
                    access_stats_url = access_stats_link_tag.get("href")
                    # Resolve relative URL (logec links are usually absolute)
                    if access_stats_url and access_stats_url.startswith("/"):
                        access_stats_url = urljoin(base_url, access_stats_url)
                    details["access_stats_link"] = access_stats_url

            # Clean up specific fields that might contain unwanted content
            if details["abstract"]:
                details["abstract"] = self.clean_section_text(details["abstract"])

            # When we have keywords but they might be in the abstract, verify and clean again
            if details["keywords"] and details["abstract"]:
                # Check if any keywords appear at the end of the abstract
                for keyword in details["keywords"]:
                    term = keyword.get("term", "")
                    if term and details["abstract"].endswith(term):
                        # Found a keyword at the end of abstract, re-clean with more aggressive approach
                        logger.warning(
                            f"Found keyword '{term}' at end of abstract, cleaning more aggressively"
                        )
                        details["abstract"] = self.clean_section_text(
                            details["abstract"], remove_section_markers=True
                        )
                        break

            # Log summary
            log_summary = f"Parsed: Title={'Y' if details['parsed_title'] else 'N'}, "
            log_summary += f"Authors={len(details['parsed_authors'])}, "
            log_summary += f"Abstract={'Y' if details['abstract'] else 'N'}, "
            log_summary += f"Downloads={len(details['download_links'])}"
            logger.info(f"[{threading.current_thread().name}] {log_summary} for {url}")

            return details

        except Exception as e:
            logger.error(f"Unexpected error parsing {url}: {e}", exc_info=True)
            return None  # Return None on parsing error

    def worker(self):
        """
        Worker thread function to process papers from the queue
        """
        thread_name = threading.current_thread().name
        with self.thread_lock:
            self.active_threads += 1
            logger.info(f"Starting worker thread {thread_name}")

        try:
            while True:
                try:
                    # Get paper with timeout to allow thread to exit when queue is empty
                    paper = self.papers_queue.get(timeout=1)

                    # Process the paper
                    url = paper.get("url")
                    if url and url not in self.paper_details:
                        logger.info(
                            f"[{thread_name}] Processing paper: {paper.get('title')[:50]}..."
                        )
                        paper_detail = self.fetch_paper_details(paper)

                        if paper_detail:
                            with self.lock:
                                self.paper_details[url] = paper_detail
                                self.processed_count += 1

                        else:
                            with self.lock:
                                self.failed_count += 1

                        logger.info(
                            f"Progress: {self.processed_count}/{self.total_papers} papers processed, {self.failed_count} failed"
                        )

                    self.papers_queue.task_done()

                except queue.Empty:
                    logger.info(f"[{thread_name}] Queue is empty, exiting")
                    break
                except Exception as e:
                    logger.error(
                        f"[{thread_name}] Error in worker thread: {e}", exc_info=True
                    )
                    # Ensure we mark the task as done even if there's an error
                    try:
                        self.papers_queue.task_done()
                    except:
                        pass
        finally:
            with self.thread_lock:
                self.active_threads -= 1
                logger.info(
                    f"[{thread_name}] Worker thread finished, {self.active_threads} threads still active"
                )

    def save_details(self, is_checkpoint=False):
        """
        Save collected details to JSON file
        """
        try:
            with self.lock:
                # Create backup of existing file if it exists
                if os.path.exists(self.output_file):
                    backup_file = f"{self.output_file}.bak"
                    try:
                        import shutil

                        shutil.copy2(self.output_file, backup_file)
                        logger.info(
                            f"Created backup of existing details file: {backup_file}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to create backup: {e}")

                with open(self.output_file, "w", encoding="utf-8") as f:
                    json.dump(self.paper_details, f, indent=2, ensure_ascii=False)
                logger.info(
                    f"Saved {len(self.paper_details)} paper details to {self.output_file}"
                )

            if is_checkpoint:
                with self.checkpoint_lock:
                    self.last_checkpoint_time = datetime.datetime.now()
        except Exception as e:
            logger.error(f"Error saving paper details: {e}", exc_info=True)

    def run(self):
        """
        Main function to run the updater
        """
        logger.info("Starting paper details updater...")

        # Print example of regex for debugging
        test_url = "/scripts/redir.pf?u=http%3A%2F%2Fwww.sciencedirect.com%2Fscience%2Farticle%2Fpii%2FS2214804314000184;h=repec:eee:soceco:v:49:y:2014:i:c:p:35-43"
        redirect_match = re.search(r"u=([^;]+);", test_url)
        if redirect_match:
            logger.info(
                f"Regex test passed: extracted {unquote(redirect_match.group(1))}"
            )
        else:
            logger.warning(f"Regex test failed for URL: {test_url}")

        # Load existing details
        self.load_existing_details()

        # Load papers data and enqueue for processing
        if not self.load_papers_data():
            logger.info("No papers to process. Exiting.")
            return

        logger.info(
            f"Starting {self.num_threads} worker threads to process {self.total_papers} papers"
        )

        try:
            # Start checkpoint monitor thread
            self.running = True
            self.checkpoint_thread = threading.Thread(
                target=self.checkpoint_monitor, name="CheckpointMonitor", daemon=True
            )
            self.checkpoint_thread.start()

            # Create worker threads
            threads = []
            for i in range(self.num_threads):
                t = threading.Thread(target=self.worker, name=f"Worker-{i+1}")
                t.daemon = True
                threads.append(t)
                t.start()

            # Wait for all tasks to be completed
            self.papers_queue.join()
            logger.info("All tasks completed")

            # Stop checkpoint monitor
            self.running = False
            if self.checkpoint_thread and self.checkpoint_thread.is_alive():
                self.checkpoint_thread.join(timeout=5)

            # Wait for all threads to finish
            for t in threads:
                t.join(timeout=1)

            # Save final results
            self.save_details()

            logger.info("\nProcessing completed!")
            logger.info(f"Total papers processed: {self.processed_count}")
            logger.info(
                f"Total papers skipped (already in database): {self.skipped_count}"
            )
            logger.info(f"Total papers failed: {self.failed_count}")
            logger.info(f"Total paper details in database: {len(self.paper_details)}")

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt. Shutting down gracefully...")
            # Stop checkpoint monitor
            self.running = False
            # Save results before exiting
            self.save_details()
            logger.info(f"Saved progress: {self.processed_count} papers processed")
            return


def parse_args():
    """
    Parse command-line arguments

    Returns:
        Parsed arguments object
    """
    parser = argparse.ArgumentParser(
        description="Update paper details with abstracts and download links"
    )

    parser.add_argument(
        "--input",
        "-i",
        default="papers_data.json",
        help="Input JSON file with paper data (default: papers_data.json)",
    )

    parser.add_argument(
        "--output",
        "-o",
        default="paper_details.json",
        help="Output JSON file for paper details (default: paper_details.json)",
    )

    parser.add_argument(
        "--threads",
        "-t",
        type=int,
        default=4,
        help="Number of concurrent threads (default: 4)",
    )

    parser.add_argument(
        "--min-sleep",
        type=float,
        default=1.0,
        help="Minimum sleep time between requests in seconds (default: 1.0)",
    )

    parser.add_argument(
        "--max-sleep",
        type=float,
        default=3.0,
        help="Maximum sleep time between requests in seconds (default: 3.0)",
    )

    parser.add_argument(
        "--retries",
        "-r",
        type=int,
        default=3,
        help="Maximum number of retries for failed requests (default: 3)",
    )

    parser.add_argument(
        "--checkpoint-minutes",
        "-c",
        type=int,
        default=15,
        help="Time interval in minutes for automatic checkpoint saves (default: 15)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (debug level)",
    )

    args = parser.parse_args()

    # Set log level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    return args


if __name__ == "__main__":
    args = parse_args()

    # Configure sleep time range
    sleep_time_range = (args.min_sleep, args.max_sleep)

    # Create and run updater with command line arguments
    updater = PaperDetailsUpdater(
        input_file=args.input,
        output_file=args.output,
        num_threads=args.threads,
        sleep_time_range=sleep_time_range,
        max_retries=args.retries,
        checkpoint_minutes=args.checkpoint_minutes,
    )

    updater.run()
