# /sitemap_audit_crawler.py

"""
Sitemap Audit Crawler
=====================

Desktop SEO auditing tool built with PyQt5. It detects sitemap files,
collects URL entries recursively, crawls pages concurrently, extracts
selected SEO fields, saves/restores progress, and exports the result to Excel.

The code is intentionally organized into small classes:
- SitemapDetector: sitemap discovery and XML parsing.
- DetectorThread: background worker for sitemap discovery.
- CrawlerThread: concurrent URL crawler.
- CustomTableWidget: URL table with advanced checkbox selection.
- SitemapCrawler: main application window and UI orchestration.
"""

import sys
import os
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import requests
import pandas as pd
from bs4 import BeautifulSoup

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QSpinBox,
    QDoubleSpinBox,
    QGroupBox,
    QMessageBox,
    QProgressBar,
    QFileDialog,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QInputDialog,
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QMutex, QTimer
from PyQt5.QtGui import QFont, QColor



# Application metadata used in the window title and progress files.
APP_NAME = "Sitemap Audit Crawler"
APP_VERSION = "v12"
PROGRESS_SCHEMA_VERSION = 1
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36 SitemapAuditCrawler/12"
)



# Local file where custom User-Agent profiles are persisted.
USER_AGENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sitemap_audit_user_agents.json")


# Built-in User-Agent profiles that can be selected without editing the code.
PRESET_USER_AGENTS = [
    {
        "name": "Chrome on Windows",
        "value": DEFAULT_USER_AGENT,
        "preset": True,
    },
    {
        "name": "Chrome on macOS",
        "value": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "preset": True,
    },
    {
        "name": "Firefox on Windows",
        "value": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
            "Gecko/20100101 Firefox/121.0"
        ),
        "preset": True,
    },
    {
        "name": "Safari on macOS",
        "value": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15"
        ),
        "preset": True,
    },
    {
        "name": "Googlebot Smartphone",
        "value": (
            "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Mobile Safari/537.36 "
            "(compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        ),
        "preset": True,
    },
    {
        "name": "Bingbot",
        "value": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) Chrome/120.0 Safari/537.36",
        "preset": True,
    },
]



# Normalize User-Agent values before using them in HTTP headers.
def clean_user_agent(value):
    """Return a safe, single-line User-Agent value, falling back to the default."""
    text = (value or "").replace("\r", " ").replace("\n", " ").strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text or DEFAULT_USER_AGENT



# -----------------------------------------------------------------------------
# Sitemap discovery and parsing
# -----------------------------------------------------------------------------
class SitemapDetector:
    """Detect and parse sitemap files recursively."""

    def __init__(self, base_url, timeout=10, stop_checker=None, user_agent=None):
        """Store sitemap discovery settings and prepare a reusable HTTP session."""
        self.base_url = self.normalize_url(base_url)
        self.timeout = timeout
        self.all_urls = {}
        self.detected_sitemaps = []
        self.sitemap_urls_map = {}
        self.max_recursion = 50
        self.recursion_count = 0
        self.processed_sitemaps = set()
        self.stop_checker = stop_checker
        self.user_agent = clean_user_agent(user_agent)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def should_stop(self):
        """Return True when the current operation has been requested to stop."""
        return bool(self.stop_checker and self.stop_checker())

    def normalize_url(self, url):
        """Normalize a domain or direct sitemap URL into an absolute URL."""
        url = (url or "").strip()
        if not url:
            return ""

        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        return url

    def get_base_domain(self):
        """Return the scheme and host portion of the configured base URL."""
        parsed = urlparse(self.base_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def find_sitemaps_from_robots(self, progress_callback=None):
        """Discover sitemap URLs declared inside robots.txt."""
        domain = self.get_base_domain()
        potential_sitemaps = []
        robots_url = urljoin(domain, "/robots.txt")

        try:
            if self.should_stop():
                return potential_sitemaps

            response = self.session.get(robots_url, timeout=self.timeout, allow_redirects=True)
            if response.status_code == 200:
                for line in response.text.split("\n"):
                    if self.should_stop():
                        return potential_sitemaps

                    line = line.strip()
                    if line.lower().startswith("sitemap:"):
                        sitemap_url = line.split(":", 1)[1].strip()
                        if sitemap_url:
                            if self.check_url_exists(sitemap_url):
                                if sitemap_url not in potential_sitemaps:
                                    potential_sitemaps.append(sitemap_url)
                                if progress_callback:
                                    progress_callback(f"✓ robots.txt: {sitemap_url}")
                            else:
                                if progress_callback:
                                    progress_callback(f"❌ Not accessible: {sitemap_url}")
        except Exception as exc:
            if progress_callback:
                progress_callback(f"⚠ Error reading robots.txt: {str(exc)[:80]}")

        return potential_sitemaps

    def find_sitemaps_typical_paths(self, progress_callback=None):
        """Probe common sitemap locations when robots.txt does not provide them."""
        domain = self.get_base_domain()
        potential_sitemaps = []
        typical_paths = [
            "/sitemap.xml",
            "/sitemap_index.xml",
            "/sitemap-index.xml",
            "/wp-sitemap.xml",
            "/sitemap1.xml",
            "/sitemap-es.xml",
            "/es/sitemap.xml",
            "/en/sitemap.xml",
            "/de/sitemap.xml",
            "/fr/sitemap.xml",
            "/sitemaps/sitemap.xml",
        ]

        for path in typical_paths:
            if self.should_stop():
                break

            url = urljoin(domain, path)
            if self.check_url_exists(url):
                if url not in potential_sitemaps:
                    potential_sitemaps.append(url)
                if progress_callback:
                    progress_callback(f"✓ Found: {path}")

        return potential_sitemaps

    def find_sitemaps(self, progress_callback=None):
        """Find sitemap sources, using direct XML input when provided."""
        if self.base_url.lower().endswith(".xml") and self.check_url_exists(self.base_url):
            self.detected_sitemaps = [self.base_url]
            if progress_callback:
                progress_callback(f"✓ Direct sitemap: {self.base_url}")
            return self.detected_sitemaps

        sitemaps_from_robots = self.find_sitemaps_from_robots(progress_callback)
        if sitemaps_from_robots:
            self.detected_sitemaps = sitemaps_from_robots
            if progress_callback:
                progress_callback(f"ℹ️ Using {len(sitemaps_from_robots)} sitemap(s) from robots.txt")
            return sitemaps_from_robots

        if progress_callback:
            progress_callback("ℹ️ Not found in robots.txt; checking common sitemap paths...")

        sitemaps_from_paths = self.find_sitemaps_typical_paths(progress_callback)
        self.detected_sitemaps = sitemaps_from_paths
        return sitemaps_from_paths

    def check_url_exists(self, url):
        """Check whether a URL is reachable, trying HEAD first and GET as fallback."""
        try:
            if self.should_stop():
                return False
            response = self.session.head(url, timeout=self.timeout, allow_redirects=True)
            if response.status_code < 400:
                return True
        except Exception:
            pass

        try:
            if self.should_stop():
                return False
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True, stream=True)
            return response.status_code < 400
        except Exception:
            return False

    def parse_sitemaps_recursive(self, progress_callback=None):
        """Parse every detected sitemap and all nested sitemap indexes."""
        pending = list(self.detected_sitemaps)
        for sitemap in pending:
            if self.should_stop():
                break
            self.sitemap_urls_map.setdefault(sitemap, [])
            self.parse_sitemap(sitemap, progress_callback, parent_sitemap=sitemap)
        return self.all_urls

    def parse_sitemap(self, sitemap_url, progress_callback=None, parent_sitemap=None):
        """Parse a single sitemap XML file or sitemap index file."""
        if self.should_stop():
            return

        if sitemap_url in self.processed_sitemaps:
            return

        self.processed_sitemaps.add(sitemap_url)

        if self.recursion_count >= self.max_recursion:
            if progress_callback:
                progress_callback("⚠ Recursion limit reached")
            return

        self.recursion_count += 1

        try:
            response = self.session.get(sitemap_url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()

            try:
                root = ET.fromstring(response.content)
            except ET.ParseError:
                try:
                    from lxml import etree

                    parser = etree.XMLParser(recover=True)
                    root = etree.fromstring(response.content, parser)
                except Exception:
                    if progress_callback:
                        progress_callback(f"❌ Invalid XML: {sitemap_url}")
                    return

            nested_sitemaps = self.extract_nested_sitemaps(root)
            urls_found = self.extract_urls_from_sitemap(root, parent_sitemap)

            if urls_found > 0 and progress_callback:
                progress_callback(f"✓ {urls_found} URLs in: {sitemap_url.split('/')[-1]}")
            elif nested_sitemaps and progress_callback:
                progress_callback(f"📄 Sitemap index with {len(nested_sitemaps)} sitemaps")

            for nested_sitemap in nested_sitemaps:
                if self.should_stop():
                    break

                if nested_sitemap not in self.detected_sitemaps:
                    self.detected_sitemaps.append(nested_sitemap)
                    self.sitemap_urls_map.setdefault(nested_sitemap, [])

                if progress_callback:
                    progress_callback(f"📄 Processing: {nested_sitemap.split('/')[-1]}")

                self.parse_sitemap(nested_sitemap, progress_callback, parent_sitemap=nested_sitemap)

        except requests.Timeout:
            if progress_callback:
                progress_callback(f"⏱ TIMEOUT: {sitemap_url}")
        except requests.ConnectionError:
            if progress_callback:
                progress_callback(f"❌ CONNECTION ERROR: {sitemap_url}")
        except Exception as exc:
            if progress_callback:
                progress_callback(f"❌ ERROR: {str(exc)[:100]}")

    def extract_nested_sitemaps(self, root):
        """Return nested sitemap URLs found inside a sitemap index."""
        nested = []
        for elem in root.iter():
            tag = self.strip_namespace(elem.tag)
            if tag != "sitemap":
                continue
            loc = self.find_child_text(elem, "loc")
            if loc and loc not in self.processed_sitemaps:
                nested.append(loc)
        return nested

    def extract_urls_from_sitemap(self, root, parent_sitemap):
        """Extract page URLs from a sitemap and attach them to their source sitemap."""
        urls_found = 0
        self.sitemap_urls_map.setdefault(parent_sitemap, [])

        for elem in root.iter():
            tag = self.strip_namespace(elem.tag)
            if tag != "url":
                continue

            loc = self.find_child_text(elem, "loc")
            if not loc:
                continue

            if loc.endswith(".xml"):
                continue

            if loc not in self.all_urls:
                self.all_urls[loc] = parent_sitemap
                self.sitemap_urls_map[parent_sitemap].append(loc)
                urls_found += 1

        return urls_found

    @staticmethod
    def strip_namespace(tag):
        """Remove the XML namespace prefix from a tag name."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def find_child_text(self, elem, child_name):
        """Find the text content of a named XML child element."""
        for child in elem:
            if self.strip_namespace(child.tag) == child_name and child.text:
                return child.text.strip()
        return None



# -----------------------------------------------------------------------------
# Background thread for sitemap detection
# -----------------------------------------------------------------------------
class DetectorThread(QThread):
    """Background thread that detects sitemaps without blocking the UI."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(list, dict, dict)
    error = pyqtSignal(str)

    def __init__(self, url, timeout, user_agent=None):
        """Store the detection request parameters for the background thread."""
        super().__init__()
        self.url = url
        self.timeout = timeout
        self.user_agent = clean_user_agent(user_agent)
        self._running = True
        self.mutex = QMutex()

    def is_running_flag(self):
        """Read the thread running flag in a mutex-protected way."""
        self.mutex.lock()
        value = self._running
        self.mutex.unlock()
        return value

    def should_stop(self):
        """Return True when the current operation has been requested to stop."""
        return not self.is_running_flag()

    def run(self):
        """Run the background task managed by this thread."""
        try:
            detector = SitemapDetector(self.url, self.timeout, stop_checker=self.should_stop, user_agent=self.user_agent)
            detected = detector.find_sitemaps(self.progress.emit)

            if self.should_stop():
                return

            if not detected:
                self.error.emit("No sitemaps were found")
                return

            urls_dict = detector.parse_sitemaps_recursive(self.progress.emit)

            if self.should_stop():
                return

            self.finished.emit(detected, urls_dict, detector.sitemap_urls_map)

        except Exception as exc:
            if not self.should_stop():
                self.error.emit(f"Error: {str(exc)}")

    def stop(self):
        """Request the running worker to stop as soon as possible."""
        self.mutex.lock()
        self._running = False
        self.mutex.unlock()



# -----------------------------------------------------------------------------
# Concurrent crawler worker
# -----------------------------------------------------------------------------
class CrawlerThread(QThread):
    """Background crawler that fetches many URLs using a configurable worker pool."""

    progress = pyqtSignal(int, int, str, str, dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, urls, timeout, delay, columns_to_extract, worker_count=8, user_agent=None):
        """Store crawl settings, selected extractors, and concurrency limits."""
        super().__init__()
        self.urls = list(urls)
        self.timeout = timeout
        self.delay = delay
        self.columns_to_extract = columns_to_extract
        self.worker_count = max(1, int(worker_count or 1))
        self.user_agent = clean_user_agent(user_agent)
        self.running = True
        self.mutex = QMutex()
        self.thread_local = threading.local()

    def is_running_flag(self):
        """Read the thread running flag in a mutex-protected way."""
        self.mutex.lock()
        value = self.running
        self.mutex.unlock()
        return value

    def get_session(self):
        """Create one HTTP session per worker thread to reuse connections safely."""
        session = getattr(self.thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": self.user_agent})
            self.thread_local.session = session
        return session

    def flatten_json(self, value, prefix="Schema", max_depth=3, current_depth=0):
        """Flatten JSON-LD into exportable fields while limiting table growth."""
        fields = {}
        if current_depth > max_depth:
            return fields

        if isinstance(value, dict):
            for key, child_value in value.items():
                if key.startswith("@") and key not in ("@type", "@id"):
                    continue
                safe_key = str(key).replace(" ", "_")
                new_prefix = f"{prefix}_{safe_key}"
                if isinstance(child_value, (dict, list)):
                    fields.update(self.flatten_json(child_value, new_prefix, max_depth, current_depth + 1))
                else:
                    fields[new_prefix] = self.safe_text(child_value, 250)
        elif isinstance(value, list):
            for index, item in enumerate(value[:5]):
                new_prefix = f"{prefix}_{index + 1}"
                if isinstance(item, (dict, list)):
                    fields.update(self.flatten_json(item, new_prefix, max_depth, current_depth + 1))
                else:
                    fields[new_prefix] = self.safe_text(item, 250)
        else:
            fields[prefix] = self.safe_text(value, 250)

        return fields

    def extract_json_schema_fields(self, json_ld):
        """Parse a JSON-LD block and return flattened schema fields."""
        try:
            if not json_ld:
                return {}
            schema_data = json.loads(json_ld)
            return self.flatten_json(schema_data)
        except Exception:
            return {}

    @staticmethod
    def safe_text(value, limit=500):
        """Convert any value into compact single-line text with a maximum length."""
        if value is None:
            return ""
        text = str(value).replace("\r", " ").replace("\n", " ").strip()
        while "  " in text:
            text = text.replace("  ", " ")
        return text[:limit]

    def extract_data_from_html(self, html, url):
        """Extract selected SEO fields from an HTML document."""
        data = {}
        try:
            soup = BeautifulSoup(html, "html.parser")

            if "H1" in self.columns_to_extract:
                h1_tags = soup.find_all("h1")
                data["H1"] = self.safe_text(h1_tags[0].get_text(" ", strip=True), 300) if h1_tags else "N/A"
                data["H1 Count"] = str(len(h1_tags))

            if "Title" in self.columns_to_extract:
                title = soup.find("title")
                data["Title"] = self.safe_text(title.get_text(" ", strip=True), 300) if title else "N/A"

            if "Meta Description" in self.columns_to_extract:
                meta_desc = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "description"})
                data["Meta Description"] = self.safe_text(meta_desc.get("content", "N/A"), 500) if meta_desc else "N/A"

            if "Canonical" in self.columns_to_extract:
                canonical = soup.find("link", attrs={"rel": lambda value: value and "canonical" in value})
                data["Canonical"] = self.safe_text(canonical.get("href", "N/A"), 500) if canonical else "N/A"

            if "Robots" in self.columns_to_extract:
                robots = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "robots"})
                data["Robots"] = self.safe_text(robots.get("content", "N/A"), 300) if robots else "N/A"

            if "JSON Schema" in self.columns_to_extract:
                json_scripts = soup.find_all("script", type="application/ld+json")
                data["Schema Count"] = str(len(json_scripts))
                for idx, json_script in enumerate(json_scripts[:3], start=1):
                    schema_fields = self.extract_json_schema_fields(json_script.string or json_script.get_text())
                    for key, value in schema_fields.items():
                        data[f"Schema {idx} {key.replace('Schema_', '')}"] = value

        except Exception as exc:
            data["Extract Error"] = self.safe_text(exc, 300)

        return data

    def fetch_url(self, url):
        """Fetch one URL inside the worker pool and return status plus extracted data."""
        if not self.is_running_flag():
            return "STOPPED", {}

        status_code = "ERROR"
        data = {}
        try:
            session = self.get_session()
            response = session.get(url, timeout=self.timeout, allow_redirects=True)
            status_code = str(response.status_code)
            data["Final URL"] = response.url
            data["Content Type"] = response.headers.get("Content-Type", "")[:120]

            content_type = response.headers.get("Content-Type", "").lower()
            if response.status_code == 200 and "text/html" in content_type:
                data.update(self.extract_data_from_html(response.text, url))
            elif response.status_code == 200:
                data["Note"] = "HTTP 200 response, but content does not look like HTML"

        except requests.Timeout:
            status_code = "TIMEOUT"
        except requests.ConnectionError:
            status_code = "CONNECTION ERROR"
        except Exception as exc:
            status_code = "ERROR"
            data["Error"] = str(exc)[:300]

        if self.delay > 0 and self.is_running_flag():
            slept = 0.0
            while slept < self.delay:
                if not self.is_running_flag():
                    break
                time.sleep(min(0.1, self.delay - slept))
                slept += 0.1

        return status_code, data

    def run(self):
        """Run the background task managed by this thread."""
        executor = None
        try:
            total = len(self.urls)
            if total == 0:
                self.finished.emit()
                return

            workers = max(1, min(self.worker_count, total))
            completed = 0
            executor = ThreadPoolExecutor(max_workers=workers)
            future_to_url = {}

            for url in self.urls:
                if not self.is_running_flag():
                    break
                future = executor.submit(self.fetch_url, url)
                future_to_url[future] = url

            for future in as_completed(future_to_url):
                if not self.is_running_flag():
                    break

                url = future_to_url[future]
                try:
                    status_code, data = future.result()
                except Exception as exc:
                    status_code = "ERROR"
                    data = {"Error": str(exc)[:300]}

                if not self.is_running_flag():
                    break

                completed += 1
                self.progress.emit(completed, total, url, status_code, data)

            self.finished.emit()
        except Exception as exc:
            if self.is_running_flag():
                self.error.emit(f"General error: {str(exc)}")
        finally:
            if executor is not None:
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except TypeError:
                    executor.shutdown(wait=False)

    def stop(self):
        """Request the running worker to stop as soon as possible."""
        self.mutex.lock()
        self.running = False
        self.mutex.unlock()



# -----------------------------------------------------------------------------
# Table selection helper
# -----------------------------------------------------------------------------
class CustomTableWidget(QTableWidget):
    """Table widget with checkbox selection, Shift/Ctrl behavior, and keyboard shortcuts."""

    selection_changed = pyqtSignal()

    def __init__(self):
        """Initialize table selection helper state."""
        super().__init__()
        self.last_checked_row = -1
        self.blocking = False

    def mousePressEvent(self, event):
        """Handle checkbox selection with normal, Ctrl, and Shift clicks."""
        item = self.itemAt(event.pos())
        if item:
            row = self.row(item)
            checkbox = self.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox):
                self.blocking = True

                if event.modifiers() == Qt.ShiftModifier and self.last_checked_row != -1:
                    start = min(self.last_checked_row, row)
                    end = max(self.last_checked_row, row)
                    for r in range(start, end + 1):
                        if not self.isRowHidden(r):
                            cb = self.cellWidget(r, 0)
                            if cb:
                                cb.setChecked(True)
                elif event.modifiers() == Qt.ControlModifier:
                    checkbox.setChecked(not checkbox.isChecked())
                else:
                    checkbox.setChecked(not checkbox.isChecked())

                self.last_checked_row = row
                self.blocking = False
                self.selection_changed.emit()

        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for bulk table selection."""
        if event.key() == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            self.blocking = True
            for row in range(self.rowCount()):
                if not self.isRowHidden(row):
                    cb = self.cellWidget(row, 0)
                    if cb:
                        cb.setChecked(True)
                if row % 200 == 0:
                    QApplication.processEvents()
            self.blocking = False
            self.selection_changed.emit()
        elif event.key() == Qt.Key_Escape:
            self.blocking = True
            for row in range(self.rowCount()):
                cb = self.cellWidget(row, 0)
                if cb:
                    cb.setChecked(False)
                if row % 200 == 0:
                    QApplication.processEvents()
            self.blocking = False
            self.selection_changed.emit()
        else:
            super().keyPressEvent(event)



# -----------------------------------------------------------------------------
# Main desktop application
# -----------------------------------------------------------------------------
class SitemapCrawler(QMainWindow):
    """Main window that coordinates UI state, background threads, and exports."""

    def __init__(self):
        """Initialize the application state, UI widgets, and auto-save timer."""
        super().__init__()

        # URL and sitemap state. The dictionary maps each URL to its source sitemap.
        self.urls = {}
        self.crawler_thread = None
        self.detector_thread = None
        self.detected_sitemaps = []
        self.sitemap_urls_map = {}
        # Table state is keyed by URL so sorting/filtering does not break updates.
        self.table_data = {}
        self.url_to_row = {}
        self.selected_count = 0
        self.updating_button = False
        # Progress state allows sessions to be saved and resumed later.
        self.progress_file_path = None
        self.progress_dirty = False
        self.auto_save_every = 10
        self.processed_since_autosave = 0
        # User-Agent profiles include built-in presets plus local custom entries.
        self.custom_user_agents = []
        self.user_agent_options = []

        self.init_ui()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setGeometry(100, 100, 2200, 900)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.auto_save_if_needed)
        self.autosave_timer.start(15000)

    def closeEvent(self, event):
        """Ask to save unsaved progress before closing the application."""
        if self.progress_dirty:
            reply = QMessageBox.question(
                self,
                "Save Progress",
                "There are unsaved changes. Do you want to save progress before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.Yes:
                if not self.save_progress():
                    event.ignore()
                    return

        self.stop_all_threads()
        event.accept()

    def stop_all_threads(self):
        """Stop active background threads before starting a new task or closing."""
        try:
            if self.detector_thread and self.detector_thread.isRunning():
                self.detector_thread.stop()
                self.detector_thread.wait(3000)

            if self.crawler_thread and self.crawler_thread.isRunning():
                self.crawler_thread.stop()
                self.crawler_thread.wait(3000)
        except Exception:
            pass

    def init_ui(self):
        """Build the complete PyQt5 user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()

        left_panel = QVBoxLayout()

        # Left panel: input, execution settings, progress controls, and actions.
        url_label = QLabel("Domain or Sitemap:")
        url_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("example.com or https://example.com/sitemap.xml")
        left_panel.addWidget(url_label)
        left_panel.addWidget(self.url_input)

        info_label = QLabel("Enter a domain or a direct sitemap URL")
        info_label.setFont(QFont("Arial", 8))
        info_label.setStyleSheet("color: gray;")
        left_panel.addWidget(info_label)

        self.load_btn = QPushButton("Detect Sitemaps")
        self.load_btn.clicked.connect(self.auto_detect_sitemaps)
        left_panel.addWidget(self.load_btn)

        log_label = QLabel("Detected Sitemaps:")
        log_label.setFont(QFont("Arial", 9, QFont.Bold))
        left_panel.addWidget(log_label)

        self.sitemaps_list = QListWidget()
        self.sitemaps_list.itemSelectionChanged.connect(self.on_sitemap_selected)
        left_panel.addWidget(self.sitemaps_list)

        self.process_btn = QPushButton("Process Selected URLs")
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self.reload_selected)
        self.process_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        left_panel.addWidget(self.process_btn)

        self.pending_btn = QPushButton("Process Pending and Failed URLs")
        self.pending_btn.setEnabled(False)
        self.pending_btn.clicked.connect(self.reload_pending_or_errors)
        left_panel.addWidget(self.pending_btn)

        self.stop_btn = QPushButton("Stop Execution")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_all_threads)
        left_panel.addWidget(self.stop_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_panel.addWidget(self.progress_bar)

        self.progress_label = QLabel("No active process")
        self.progress_label.setFont(QFont("Arial", 8))
        self.progress_label.setStyleSheet("color: #666;")
        left_panel.addWidget(self.progress_label)

        config_group = QGroupBox("Execution Settings")
        config_layout = QVBoxLayout()

        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("Timeout (sec):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setValue(10)
        self.timeout_spin.setRange(1, 120)
        timeout_layout.addWidget(self.timeout_spin)
        config_layout.addLayout(timeout_layout)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay per URL (sec):"))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setValue(0.2)
        self.delay_spin.setRange(0, 10)
        self.delay_spin.setSingleStep(0.1)
        delay_layout.addWidget(self.delay_spin)
        config_layout.addLayout(delay_layout)

        workers_layout = QHBoxLayout()
        workers_layout.addWidget(QLabel("Concurrent Requests:"))
        self.workers_spin = QSpinBox()
        self.workers_spin.setValue(8)
        self.workers_spin.setRange(1, 50)
        workers_layout.addWidget(self.workers_spin)
        config_layout.addLayout(workers_layout)

        agent_layout = QVBoxLayout()
        agent_layout.addWidget(QLabel("HTTP Agent / User-Agent:"))

        self.user_agent_combo = QComboBox()
        self.user_agent_combo.setMinimumWidth(260)
        agent_layout.addWidget(self.user_agent_combo)

        agent_buttons_layout = QHBoxLayout()
        self.add_user_agent_btn = QPushButton("Add Agent")
        self.add_user_agent_btn.clicked.connect(self.add_user_agent)
        agent_buttons_layout.addWidget(self.add_user_agent_btn)

        self.remove_user_agent_btn = QPushButton("Remove Agent")
        self.remove_user_agent_btn.clicked.connect(self.remove_user_agent)
        agent_buttons_layout.addWidget(self.remove_user_agent_btn)

        agent_layout.addLayout(agent_buttons_layout)
        config_layout.addLayout(agent_layout)
        self.load_user_agents_config()
        self.refresh_user_agent_combo()

        self.autosave_check = QCheckBox("Auto-save Progress")
        self.autosave_check.setChecked(True)
        config_layout.addWidget(self.autosave_check)

        config_group.setLayout(config_layout)
        left_panel.addWidget(config_group)

        columns_group = QGroupBox("Fields to Extract")
        columns_layout = QVBoxLayout()
        self.column_checks = {}
        columns = ["H1", "Title", "Meta Description", "Canonical", "Robots", "JSON Schema"]
        default_checked = {"H1", "Title", "Meta Description", "Canonical"}

        for col in columns:
            check = QCheckBox(col)
            check.setChecked(col in default_checked)
            self.column_checks[col] = check
            columns_layout.addWidget(check)

        columns_group.setLayout(columns_layout)
        left_panel.addWidget(columns_group)

        progress_group = QGroupBox("Progress Management")
        progress_layout = QVBoxLayout()

        save_btn = QPushButton("Save Progress")
        save_btn.clicked.connect(self.save_progress)
        progress_layout.addWidget(save_btn)

        save_as_btn = QPushButton("Save Progress As...")
        save_as_btn.clicked.connect(self.save_progress_as)
        progress_layout.addWidget(save_as_btn)

        load_progress_btn = QPushButton("Load Progress")
        load_progress_btn.clicked.connect(self.load_progress)
        progress_layout.addWidget(load_progress_btn)

        self.progress_file_label = QLabel("File: not set")
        self.progress_file_label.setFont(QFont("Arial", 8))
        self.progress_file_label.setStyleSheet("color: #666;")
        self.progress_file_label.setWordWrap(True)
        progress_layout.addWidget(self.progress_file_label)

        progress_group.setLayout(progress_layout)
        left_panel.addWidget(progress_group)

        left_panel.addStretch()

        reload_all_btn = QPushButton("Process All URLs")
        reload_all_btn.clicked.connect(self.reload_all)
        left_panel.addWidget(reload_all_btn)

        export_btn = QPushButton("Export to Excel")
        export_btn.clicked.connect(self.export_to_excel)
        left_panel.addWidget(export_btn)

        right_panel = QVBoxLayout()

        # Right panel: searchable URL audit table.
        table_label = QLabel("Detected URLs:")
        table_label.setFont(QFont("Arial", 10, QFont.Bold))
        right_panel.addWidget(table_label)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filter:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search URLs, sitemap origin, status, or extracted data...")
        self.search_input.textChanged.connect(self.filter_table)
        search_layout.addWidget(self.search_input)
        right_panel.addLayout(search_layout)

        self.counter_label = QLabel("URLs: 0 | Visible: 0 | Selected: 0 | Processed: 0")
        self.counter_label.setFont(QFont("Arial", 9))
        right_panel.addWidget(self.counter_label)

        selection_info = QLabel("Ctrl+A: select visible rows | Shift+Click: range | Ctrl+Click: toggle | Esc: clear selection")
        selection_info.setFont(QFont("Arial", 8))
        selection_info.setStyleSheet("color: #666; font-style: italic;")
        right_panel.addWidget(selection_info)

        # The table starts with stable columns; extracted SEO fields are added dynamically.
        self.table = CustomTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["✓", "URL", "Source Sitemap", "HTTP Status", "Last Checked"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setSortingEnabled(True)
        self.table.selection_changed.connect(self.on_table_selection_changed)
        right_panel.addWidget(self.table)

        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setMaximumWidth(430)

        right_widget = QWidget()
        right_widget.setLayout(right_panel)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, 1)
        central_widget.setLayout(main_layout)

    def load_user_agents_config(self):
        """Load custom User-Agent profiles from a local JSON file next to the script."""
        self.custom_user_agents = []
        try:
            if os.path.exists(USER_AGENTS_FILE):
                with open(USER_AGENTS_FILE, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
                for item in payload.get("custom_user_agents", []):
                    name = str(item.get("name", "")).strip()
                    value = clean_user_agent(item.get("value", ""))
                    if name and value:
                        self.custom_user_agents.append({"name": name, "value": value, "preset": False})
        except Exception:
            self.custom_user_agents = []

    def save_user_agents_config(self):
        """Save only custom User-Agent profiles; built-in presets stay in code."""
        payload = {
            "schema_version": 1,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "custom_user_agents": self.custom_user_agents,
        }
        with open(USER_AGENTS_FILE, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    def refresh_user_agent_combo(self, selected_agent=None):
        """Rebuild the User-Agent combo box from presets and custom profiles."""
        previous_agent = selected_agent or self.get_selected_user_agent()
        self.user_agent_combo.blockSignals(True)
        self.user_agent_combo.clear()
        self.user_agent_options = []

        seen = set()
        for item in PRESET_USER_AGENTS + self.custom_user_agents:
            value = clean_user_agent(item.get("value"))
            if value in seen:
                continue
            seen.add(value)
            option = {
                "name": item.get("name", "Unnamed agent"),
                "value": value,
                "preset": bool(item.get("preset", False)),
            }
            self.user_agent_options.append(option)
            prefix = "Preset" if option["preset"] else "Custom"
            self.user_agent_combo.addItem(f'{option["name"]} ({prefix})', option)

        selected_index = 0
        for index, option in enumerate(self.user_agent_options):
            if option["value"] == previous_agent:
                selected_index = index
                break
        self.user_agent_combo.setCurrentIndex(selected_index)
        self.user_agent_combo.blockSignals(False)

    def get_selected_user_agent(self):
        """Return the currently selected User-Agent value."""
        if not hasattr(self, "user_agent_combo"):
            return DEFAULT_USER_AGENT
        data = self.user_agent_combo.currentData()
        if isinstance(data, dict):
            return clean_user_agent(data.get("value"))
        return DEFAULT_USER_AGENT

    def add_user_agent(self):
        """Ask the user for a custom User-Agent and persist it locally."""
        name, ok = QInputDialog.getText(self, "Add HTTP Agent", "Agent name:")
        if not ok:
            return
        name = str(name).strip()
        if not name:
            QMessageBox.warning(self, "HTTP Agent", "You must enter an agent name.")
            return

        value, ok = QInputDialog.getMultiLineText(self, "Add HTTP Agent", "Full User-Agent:", "")
        if not ok:
            return
        value = clean_user_agent(value)
        if not value:
            QMessageBox.warning(self, "HTTP Agent", "You must enter the full User-Agent value.")
            return

        for option in PRESET_USER_AGENTS + self.custom_user_agents:
            if clean_user_agent(option.get("value")) == value:
                QMessageBox.information(self, "HTTP Agent", "That User-Agent already exists in the list.")
                self.refresh_user_agent_combo(value)
                return

        self.custom_user_agents.append({"name": name, "value": value, "preset": False})
        try:
            self.save_user_agents_config()
        except Exception as exc:
            QMessageBox.warning(self, "HTTP Agent", f"The agent was added, but the local configuration file could not be saved:\n{str(exc)}")

        self.refresh_user_agent_combo(value)
        self.mark_dirty()
        QMessageBox.information(self, "HTTP Agent", "Agent added successfully.")

    def remove_user_agent(self):
        """Remove the selected custom User-Agent profile."""
        data = self.user_agent_combo.currentData()
        if not isinstance(data, dict):
            return
        if data.get("preset"):
            QMessageBox.information(self, "HTTP Agent", "Preset agents cannot be removed.")
            return

        reply = QMessageBox.question(
            self,
            "Remove HTTP Agent",
            f'Remove custom agent "{data.get("name", "")}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        value_to_remove = clean_user_agent(data.get("value"))
        self.custom_user_agents = [
            item for item in self.custom_user_agents
            if clean_user_agent(item.get("value")) != value_to_remove
        ]
        try:
            self.save_user_agents_config()
        except Exception as exc:
            QMessageBox.warning(self, "HTTP Agent", f"The local configuration file could not be updated:\n{str(exc)}")

        self.refresh_user_agent_combo(DEFAULT_USER_AGENT)
        self.mark_dirty()

    def mark_dirty(self):
        """Mark the current project state as changed since the last save."""
        self.progress_dirty = True

    def set_buttons_processing(self, processing):
        """Enable or disable controls depending on whether a task is running."""
        self.load_btn.setEnabled(not processing)
        self.process_btn.setEnabled((not processing) and bool(self.urls))
        self.pending_btn.setEnabled((not processing) and bool(self.urls))
        self.stop_btn.setEnabled(processing)

    def add_log(self, message):
        """Append a status message to the sitemap log list."""
        item = QListWidgetItem(message)
        self.sitemaps_list.addItem(item)
        self.sitemaps_list.scrollToBottom()

    def auto_detect_sitemaps(self):
        """Start sitemap discovery for the domain or sitemap entered by the user."""
        self.stop_all_threads()
        url = self.url_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Error", "Please enter a valid URL")
            return

        if self.progress_dirty and self.urls:
            reply = QMessageBox.question(
                self,
                "Replace Current Data",
                "This will replace the current URL list. Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self.sitemaps_list.clear()
        self.table.setRowCount(0)
        self.urls = {}
        self.detected_sitemaps = []
        self.sitemap_urls_map = {}
        self.table_data = {}
        self.url_to_row = {}
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)
        self.progress_label.setText("Detecting sitemaps...")
        self.set_buttons_processing(True)

        self.detector_thread = DetectorThread(url, self.timeout_spin.value(), self.get_selected_user_agent())
        self.detector_thread.progress.connect(self.add_log)
        self.detector_thread.finished.connect(self.detection_finished)
        self.detector_thread.error.connect(self.detection_error)
        self.detector_thread.start()

    def detection_finished(self, detected_sitemaps, urls_dict, sitemap_urls_map):
        """Receive sitemap discovery results and populate the URL table."""
        try:
            self.detected_sitemaps = detected_sitemaps
            self.urls = urls_dict
            self.sitemap_urls_map = sitemap_urls_map

            self.sitemaps_list.clear()
            for sitemap in detected_sitemaps:
                count = len(sitemap_urls_map.get(sitemap, []))
                item_text = f"📄 {sitemap.split('/')[-1]} ({count} URLs)"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, sitemap)
                self.sitemaps_list.addItem(item)

            self.populate_table()
            self.progress_bar.setVisible(False)
            self.progress_label.setText(f"Detection completed: {len(urls_dict)} unique URLs")
            self.set_buttons_processing(False)
            self.mark_dirty()
            self.auto_save_if_needed(force=True)

            QMessageBox.information(
                self,
                "Success",
                f"Found {len(detected_sitemaps)} sitemap(s)\nwith {len(urls_dict)} unique URL(s)",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Error completing sitemap detection: {str(exc)}")
            self.set_buttons_processing(False)
            self.progress_bar.setVisible(False)

    def detection_error(self, error_msg):
        """Display an error reported by the sitemap detection thread."""
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Detection error")
        self.set_buttons_processing(False)
        QMessageBox.critical(self, "Error", error_msg)

    def populate_table(self):
        """Populate the table from the current URL and table-data dictionaries."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.urls))
        self.url_to_row.clear()

        for idx, (url, sitemap_origin) in enumerate(self.urls.items()):
            sitemap_name = sitemap_origin.split("/")[-1] if sitemap_origin else "N/A"
            if url not in self.table_data:
                self.table_data[url] = {
                    "url": url,
                    "sitemap": sitemap_name,
                    "status": "Pending",
                    "last_checked": "",
                    "data": {},
                    "selected": False,
                }
            else:
                self.table_data[url]["sitemap"] = self.table_data[url].get("sitemap") or sitemap_name

            self.url_to_row[url] = idx
            self.create_or_update_row(idx, url)

            # Process UI events every few rows when loading large sitemaps.
            if idx % 200 == 0:
                QApplication.processEvents()

        self.table.setSortingEnabled(True)
        self.rebuild_url_to_row()
        self.update_button_text()

    def create_or_update_row(self, row, url):
        """Create or refresh one table row for a URL."""
        row_data = self.table_data.get(url, {})

        checkbox = QCheckBox()
        checkbox.setChecked(bool(row_data.get("selected", False)))
        checkbox.stateChanged.connect(self.on_checkbox_state_changed)
        self.table.setCellWidget(row, 0, checkbox)

        self.set_table_item(row, 1, url)
        self.set_table_item(row, 2, row_data.get("sitemap", "N/A"))
        self.set_table_item(row, 3, row_data.get("status", "Pending"))
        self.color_status_cell(row_data.get("status", "Pending"), row, 3)
        self.set_table_item(row, 4, row_data.get("last_checked", ""))

        for key, value in row_data.get("data", {}).items():
            col_idx = self.ensure_column(key)
            self.set_table_item(row, col_idx, value)

    def set_table_item(self, row, col, value):
        """Insert a non-editable text item into the table."""
        item = QTableWidgetItem(str(value) if value is not None else "")
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, col, item)

    def color_status_cell(self, status, row, col):
        """Apply a background color that reflects the HTTP status."""
        item = self.table.item(row, col)
        if not item:
            return

        status = str(status)
        if status == "200":
            item.setBackground(QColor(144, 238, 144))
        elif status.startswith("4") or status.startswith("5"):
            item.setBackground(QColor(255, 99, 71))
        elif status in ("TIMEOUT", "CONNECTION ERROR"):
            item.setBackground(QColor(255, 215, 0))
        elif status == "Pending":
            item.setBackground(QColor(255, 255, 255))
        else:
            item.setBackground(QColor(211, 211, 211))

    def ensure_column(self, col_name):
        """Create a dynamic table column if it does not already exist."""
        for col in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(col)
            if header and header.text() == col_name:
                return col

        col_idx = self.table.columnCount()
        self.table.insertColumn(col_idx)
        self.table.setHorizontalHeaderItem(col_idx, QTableWidgetItem(col_name))
        return col_idx

    def rebuild_url_to_row(self):
        """Rebuild the fast lookup map from URL to visible table row."""
        self.url_to_row.clear()
        for row in range(self.table.rowCount()):
            url_item = self.table.item(row, 1)
            if url_item:
                self.url_to_row[url_item.text()] = row

    def on_checkbox_state_changed(self):
        """React to manual checkbox changes in the table."""
        if not self.table.blocking:
            self.mark_dirty()
            self.on_table_selection_changed()

    def on_table_selection_changed(self):
        """Debounce table selection changes before updating counters."""
        if not self.updating_button:
            self.updating_button = True
            QTimer.singleShot(100, self.update_button_text)

    def update_button_text(self):
        """Refresh counters and process-button text based on current selection."""
        self.rebuild_url_to_row()
        self.selected_count = 0
        visible_count = 0
        processed_count = 0

        for row in range(self.table.rowCount()):
            url_item = self.table.item(row, 1)
            if not url_item:
                continue

            url = url_item.text()
            checkbox = self.table.cellWidget(row, 0)
            selected = bool(checkbox and checkbox.isChecked())
            if url in self.table_data:
                self.table_data[url]["selected"] = selected

            if not self.table.isRowHidden(row):
                visible_count += 1
                if selected:
                    self.selected_count += 1

            status = self.table_data.get(url, {}).get("status", "Pending")
            if status and status != "Pending":
                processed_count += 1

        if self.selected_count > 0:
            self.process_btn.setText(f"Process Selection ({self.selected_count} URLs)")
        else:
            self.process_btn.setText("Process Selected URLs")

        self.counter_label.setText(
            f"URLs: {len(self.urls)} | Visible: {visible_count} | Selected: {self.selected_count} | Processed: {processed_count}"
        )
        self.updating_button = False

    def on_sitemap_selected(self):
        """Select table URLs that belong to the selected sitemap entries."""
        selected_items = self.sitemaps_list.selectedItems()
        self.table.blocking = True

        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)

        for item in selected_items:
            sitemap_url = item.data(Qt.UserRole)
            urls_in_sitemap = set(self.sitemap_urls_map.get(sitemap_url, []))
            for url in urls_in_sitemap:
                row = self.url_to_row.get(url)
                if row is not None:
                    checkbox = self.table.cellWidget(row, 0)
                    if checkbox:
                        checkbox.setChecked(True)

        self.table.blocking = False
        self.mark_dirty()
        self.update_button_text()

    def filter_table(self):
        """Show only rows matching the search field."""
        search_text = self.search_input.text().lower().strip()

        for row in range(self.table.rowCount()):
            match = True
            if search_text:
                values = []
                for col in range(1, self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        values.append(item.text().lower())
                match = search_text in " | ".join(values)
            self.table.setRowHidden(row, not match)

        self.update_button_text()

    def get_selected_urls(self):
        """Return visible URLs that are currently selected."""
        selected = []
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            checkbox = self.table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                url_item = self.table.item(row, 1)
                if url_item:
                    selected.append(url_item.text())
        return selected

    def get_pending_or_error_urls(self):
        """Return URLs that are pending or previously failed."""
        urls = []
        for url, row_data in self.table_data.items():
            status = str(row_data.get("status", "Pending"))
            if status in ("", "Pending", "TIMEOUT", "CONNECTION ERROR", "ERROR") or status.startswith("4") or status.startswith("5"):
                urls.append(url)
        return urls

    def reload_selected(self):
        """Start crawling for selected visible URLs."""
        selected = self.get_selected_urls()
        if not selected:
            QMessageBox.warning(self, "Notice", "Select at least one visible URL")
            return
        self.start_crawling(selected)

    def reload_pending_or_errors(self):
        """Start crawling for URLs that still need attention."""
        selected = self.get_pending_or_error_urls()
        if not selected:
            QMessageBox.information(self, "Notice", "There are no pending or failed URLs")
            return
        self.start_crawling(selected)

    def reload_all(self):
        """Start crawling for every loaded URL."""
        if not self.urls:
            QMessageBox.warning(self, "Notice", "Load a sitemap first")
            return
        self.start_crawling(list(self.urls.keys()))

    def start_crawling(self, urls_to_crawl):
        """Configure and launch the concurrent crawler thread."""
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.crawler_thread.stop()
            self.crawler_thread.wait(3000)

        columns = [col for col, check in self.column_checks.items() if check.isChecked()]
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(urls_to_crawl))
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"Processing 0 of {len(urls_to_crawl)} with {self.workers_spin.value()} concurrent requests")
        self.set_buttons_processing(True)
        self.processed_since_autosave = 0

        self.crawler_thread = CrawlerThread(
            urls_to_crawl,
            self.timeout_spin.value(),
            self.delay_spin.value(),
            columns,
            self.workers_spin.value(),
            self.get_selected_user_agent(),
        )
        self.crawler_thread.progress.connect(self.update_progress)
        self.crawler_thread.finished.connect(self.crawling_finished)
        self.crawler_thread.error.connect(self.crawling_error)
        self.crawler_thread.start()

    def update_progress(self, current, total, url, status, data):
        """Receive one crawled URL result and update the table."""
        row = self.url_to_row.get(url)
        if row is None:
            self.rebuild_url_to_row()
            row = self.url_to_row.get(url)
            if row is None:
                return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sitemap_name = self.table_data.get(url, {}).get("sitemap", "N/A")
        old_data = self.table_data.get(url, {}).get("data", {})
        merged_data = dict(old_data)
        merged_data.update(data or {})

        self.table_data[url] = {
            "url": url,
            "sitemap": sitemap_name,
            "status": status,
            "last_checked": now,
            "data": merged_data,
            "selected": self.table_data.get(url, {}).get("selected", False),
        }

        self.table.setSortingEnabled(False)
        self.set_table_item(row, 3, status)
        self.color_status_cell(status, row, 3)
        self.set_table_item(row, 4, now)

        for col_name, value in merged_data.items():
            col_idx = self.ensure_column(col_name)
            self.set_table_item(row, col_idx, value)

        self.table.setSortingEnabled(True)
        self.rebuild_url_to_row()

        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Processing {current} of {total}: {status} | {url[:90]}")
        self.processed_since_autosave += 1
        self.mark_dirty()

        if self.autosave_check.isChecked() and self.processed_since_autosave >= self.auto_save_every:
            self.auto_save_if_needed(force=True, silent=True)
            self.processed_since_autosave = 0

        self.update_button_text()

    def crawling_finished(self):
        """Finalize the UI state after crawling completes."""
        self.set_buttons_processing(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Processing completed")
        self.auto_save_if_needed(force=True, silent=True)
        QMessageBox.information(self, "Success", "Processing completed ✓")

    def crawling_error(self, error_msg):
        """Display an error reported by the crawler thread."""
        self.set_buttons_processing(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Processing error")
        QMessageBox.critical(self, "Error", error_msg)

    def build_progress_payload(self):
        """Build the JSON-serializable progress payload."""
        selected_columns = [col for col, check in self.column_checks.items() if check.isChecked()]
        payload = {
            "schema_version": PROGRESS_SCHEMA_VERSION,
            "app": APP_NAME,
            "version": APP_VERSION,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "url_input": self.url_input.text().strip(),
            "timeout": self.timeout_spin.value(),
            "delay": self.delay_spin.value(),
            "workers": self.workers_spin.value(),
            "user_agent": self.get_selected_user_agent(),
            "custom_user_agents": self.custom_user_agents,
            "selected_columns": selected_columns,
            "detected_sitemaps": self.detected_sitemaps,
            "sitemap_urls_map": self.sitemap_urls_map,
            "urls": self.urls,
            "table_data": self.table_data,
        }
        return payload

    def save_progress_as(self):
        """Ask for a target file and save the current progress there."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Progress",
            self.default_progress_filename(),
            "JSON Files (*.json)",
        )
        if not file_path:
            return False
        self.progress_file_path = file_path
        return self.save_progress()

    def save_progress(self):
        """Save the current progress to the selected JSON file."""
        if not self.progress_file_path:
            return self.save_progress_as()

        try:
            payload = self.build_progress_payload()
            with open(self.progress_file_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)

            self.progress_dirty = False
            self.update_progress_file_label()
            self.progress_label.setText(f"Progress saved: {os.path.basename(self.progress_file_path)}")
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Progress could not be saved:\n{str(exc)}")
            return False

    def auto_save_if_needed(self, force=False, silent=True):
        """Auto-save when enabled and the state has changed."""
        if not self.autosave_check.isChecked():
            return
        if not self.progress_dirty and not force:
            return
        if not self.urls:
            return

        if not self.progress_file_path:
            self.progress_file_path = os.path.abspath(self.default_progress_filename())

        try:
            payload = self.build_progress_payload()
            with open(self.progress_file_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)

            self.progress_dirty = False
            self.update_progress_file_label()
            if not silent:
                self.progress_label.setText(f"Progress auto-saved: {os.path.basename(self.progress_file_path)}")
        except Exception as exc:
            if not silent:
                QMessageBox.warning(self, "Auto-save", f"Auto-save failed:\n{str(exc)}")

    def load_progress(self):
        """Load a saved progress JSON file and rebuild the UI state."""
        if self.progress_dirty:
            reply = QMessageBox.question(
                self,
                "Load Progress",
                "There are unsaved changes. Do you want to continue and replace the current state?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        file_path, _ = QFileDialog.getOpenFileName(self, "Load Progress", "", "JSON Files (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)

            if int(payload.get("schema_version", 0)) != PROGRESS_SCHEMA_VERSION:
                QMessageBox.warning(
                    self,
                    "Progress File Version",
                    "The progress file has a different version. I will try to load it anyway.",
                )

            self.progress_file_path = file_path
            self.url_input.setText(payload.get("url_input", ""))
            self.timeout_spin.setValue(int(payload.get("timeout", 10)))
            self.delay_spin.setValue(float(payload.get("delay", 0.2)))
            self.workers_spin.setValue(int(payload.get("workers", 8)))

            loaded_custom_agents = payload.get("custom_user_agents", []) or []
            if loaded_custom_agents:
                existing = {clean_user_agent(item.get("value")) for item in self.custom_user_agents}
                for item in loaded_custom_agents:
                    name = str(item.get("name", "")).strip()
                    value = clean_user_agent(item.get("value", ""))
                    if name and value and value not in existing:
                        self.custom_user_agents.append({"name": name, "value": value, "preset": False})
                        existing.add(value)
                try:
                    self.save_user_agents_config()
                except Exception:
                    pass

            self.refresh_user_agent_combo(payload.get("user_agent", DEFAULT_USER_AGENT))

            selected_columns = set(payload.get("selected_columns", []))
            for col, check in self.column_checks.items():
                check.setChecked(col in selected_columns)

            self.detected_sitemaps = payload.get("detected_sitemaps", []) or []
            self.sitemap_urls_map = payload.get("sitemap_urls_map", {}) or {}
            self.urls = payload.get("urls", {}) or {}
            self.table_data = payload.get("table_data", {}) or {}

            self.sitemaps_list.clear()
            for sitemap in self.detected_sitemaps:
                count = len(self.sitemap_urls_map.get(sitemap, []))
                item_text = f"📄 {sitemap.split('/')[-1]} ({count} URLs)"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, sitemap)
                self.sitemaps_list.addItem(item)

            self.populate_table()
            self.progress_dirty = False
            self.update_progress_file_label()
            self.progress_label.setText(f"Progress loaded: {os.path.basename(file_path)}")
            self.set_buttons_processing(False)
            QMessageBox.information(self, "Success", "Progress loaded successfully")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Progress could not be loaded:\n{str(exc)}")

    def default_progress_filename(self):
        """Generate a safe default progress filename for the current domain."""
        parsed = urlparse(self.url_input.text().strip())
        domain = parsed.netloc or parsed.path or "sitemap"
        domain = domain.replace("/", "_").replace(":", "_").replace(".", "_")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"sitemap_audit_progress_{domain}_{stamp}.json"

    def update_progress_file_label(self):
        """Update the label that shows the active progress file path."""
        if self.progress_file_path:
            self.progress_file_label.setText(f"File: {self.progress_file_path}")
        else:
            self.progress_file_label.setText("File: not set")

    def export_to_excel(self):
        """Export the current table contents to an Excel workbook."""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Notice", "There is no data to export")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel File", "sitemap_audit_export.xlsx", "Excel Files (*.xlsx)")
        if not file_path:
            return

        if not file_path.lower().endswith(".xlsx"):
            file_path += ".xlsx"

        try:
            rows = []
            headers = []
            for col in range(1, self.table.columnCount()):
                header = self.table.horizontalHeaderItem(col)
                headers.append(header.text() if header else f"Col{col}")

            for row in range(self.table.rowCount()):
                row_data = []
                for col in range(1, self.table.columnCount()):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else "")
                rows.append(row_data)

            df = pd.DataFrame(rows, columns=headers)
            df.to_excel(file_path, index=False)
            QMessageBox.information(self, "Success", f"File saved: {file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Export error: {str(exc)}")



# Application entry point.
if __name__ == "__main__":
    app = QApplication(sys.argv)
    crawler = SitemapCrawler()
    crawler.show()
    sys.exit(app.exec_())
