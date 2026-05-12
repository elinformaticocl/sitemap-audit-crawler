# /sitemap_crawler_pro_v11.py
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


APP_NAME = "Sitemap Crawler Pro"
APP_VERSION = "v11"
PROGRESS_SCHEMA_VERSION = 1
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36 SitemapCrawlerPro/11"
)


USER_AGENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sitemap_crawler_user_agents.json")

PRESET_USER_AGENTS = [
    {
        "name": "Chrome en Windows",
        "value": DEFAULT_USER_AGENT,
        "preset": True,
    },
    {
        "name": "Chrome en macOS",
        "value": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "preset": True,
    },
    {
        "name": "Firefox en Windows",
        "value": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
            "Gecko/20100101 Firefox/121.0"
        ),
        "preset": True,
    },
    {
        "name": "Safari en macOS",
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


def clean_user_agent(value):
    text = (value or "").replace("\r", " ").replace("\n", " ").strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text or DEFAULT_USER_AGENT


class SitemapDetector:
    """Detecta y parsea sitemaps de forma recursiva."""

    def __init__(self, base_url, timeout=10, stop_checker=None, user_agent=None):
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
        return bool(self.stop_checker and self.stop_checker())

    def normalize_url(self, url):
        """Normaliza la URL para soportar dominio o sitemap directo."""
        url = (url or "").strip()
        if not url:
            return ""

        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        return url

    def get_base_domain(self):
        parsed = urlparse(self.base_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def find_sitemaps_from_robots(self, progress_callback=None):
        """Busca sitemaps en robots.txt."""
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
                                    progress_callback(f"❌ No accesible: {sitemap_url}")
        except Exception as exc:
            if progress_callback:
                progress_callback(f"⚠ Error leyendo robots.txt: {str(exc)[:80]}")

        return potential_sitemaps

    def find_sitemaps_typical_paths(self, progress_callback=None):
        """Busca sitemaps en rutas típicas como fallback."""
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
                    progress_callback(f"✓ Encontrado: {path}")

        return potential_sitemaps

    def find_sitemaps(self, progress_callback=None):
        """Busca sitemaps: si el input ya es XML, intenta usarlo directo."""
        if self.base_url.lower().endswith(".xml") and self.check_url_exists(self.base_url):
            self.detected_sitemaps = [self.base_url]
            if progress_callback:
                progress_callback(f"✓ Sitemap directo: {self.base_url}")
            return self.detected_sitemaps

        sitemaps_from_robots = self.find_sitemaps_from_robots(progress_callback)
        if sitemaps_from_robots:
            self.detected_sitemaps = sitemaps_from_robots
            if progress_callback:
                progress_callback(f"ℹ️ Usando {len(sitemaps_from_robots)} sitemap(s) desde robots.txt")
            return sitemaps_from_robots

        if progress_callback:
            progress_callback("ℹ️ No encontrado en robots.txt, buscando en rutas típicas...")

        sitemaps_from_paths = self.find_sitemaps_typical_paths(progress_callback)
        self.detected_sitemaps = sitemaps_from_paths
        return sitemaps_from_paths

    def check_url_exists(self, url):
        """Verifica si una URL existe. Primero HEAD, luego GET si falla."""
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
        """Parsea los sitemaps detectados de forma recursiva."""
        pending = list(self.detected_sitemaps)
        for sitemap in pending:
            if self.should_stop():
                break
            self.sitemap_urls_map.setdefault(sitemap, [])
            self.parse_sitemap(sitemap, progress_callback, parent_sitemap=sitemap)
        return self.all_urls

    def parse_sitemap(self, sitemap_url, progress_callback=None, parent_sitemap=None):
        """Parsea un sitemap XML o sitemap index."""
        if self.should_stop():
            return

        if sitemap_url in self.processed_sitemaps:
            return

        self.processed_sitemaps.add(sitemap_url)

        if self.recursion_count >= self.max_recursion:
            if progress_callback:
                progress_callback("⚠ Límite de recursión alcanzado")
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
                        progress_callback(f"❌ XML inválido: {sitemap_url}")
                    return

            nested_sitemaps = self.extract_nested_sitemaps(root)
            urls_found = self.extract_urls_from_sitemap(root, parent_sitemap)

            if urls_found > 0 and progress_callback:
                progress_callback(f"✓ {urls_found} URLs en: {sitemap_url.split('/')[-1]}")
            elif nested_sitemaps and progress_callback:
                progress_callback(f"📄 Sitemap Index con {len(nested_sitemaps)} sitemaps")

            for nested_sitemap in nested_sitemaps:
                if self.should_stop():
                    break

                if nested_sitemap not in self.detected_sitemaps:
                    self.detected_sitemaps.append(nested_sitemap)
                    self.sitemap_urls_map.setdefault(nested_sitemap, [])

                if progress_callback:
                    progress_callback(f"📄 Procesando: {nested_sitemap.split('/')[-1]}")

                self.parse_sitemap(nested_sitemap, progress_callback, parent_sitemap=nested_sitemap)

        except requests.Timeout:
            if progress_callback:
                progress_callback(f"⏱ TIMEOUT: {sitemap_url}")
        except requests.ConnectionError:
            if progress_callback:
                progress_callback(f"❌ ERROR DE CONEXIÓN: {sitemap_url}")
        except Exception as exc:
            if progress_callback:
                progress_callback(f"❌ ERROR: {str(exc)[:100]}")

    def extract_nested_sitemaps(self, root):
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
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def find_child_text(self, elem, child_name):
        for child in elem:
            if self.strip_namespace(child.tag) == child_name and child.text:
                return child.text.strip()
        return None


class DetectorThread(QThread):
    """Thread para detectar sitemaps sin bloquear la UI."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(list, dict, dict)
    error = pyqtSignal(str)

    def __init__(self, url, timeout, user_agent=None):
        super().__init__()
        self.url = url
        self.timeout = timeout
        self.user_agent = clean_user_agent(user_agent)
        self._running = True
        self.mutex = QMutex()

    def is_running_flag(self):
        self.mutex.lock()
        value = self._running
        self.mutex.unlock()
        return value

    def should_stop(self):
        return not self.is_running_flag()

    def run(self):
        try:
            detector = SitemapDetector(self.url, self.timeout, stop_checker=self.should_stop, user_agent=self.user_agent)
            detected = detector.find_sitemaps(self.progress.emit)

            if self.should_stop():
                return

            if not detected:
                self.error.emit("No se encontraron sitemaps")
                return

            urls_dict = detector.parse_sitemaps_recursive(self.progress.emit)

            if self.should_stop():
                return

            self.finished.emit(detected, urls_dict, detector.sitemap_urls_map)

        except Exception as exc:
            if not self.should_stop():
                self.error.emit(f"Error: {str(exc)}")

    def stop(self):
        self.mutex.lock()
        self._running = False
        self.mutex.unlock()


class CrawlerThread(QThread):
    progress = pyqtSignal(int, int, str, str, dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, urls, timeout, delay, columns_to_extract, worker_count=8, user_agent=None):
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
        self.mutex.lock()
        value = self.running
        self.mutex.unlock()
        return value

    def get_session(self):
        """Crea una sesión HTTP por hilo para reutilizar conexiones sin compartir estado entre hilos."""
        session = getattr(self.thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": self.user_agent})
            self.thread_local.session = session
        return session

    def flatten_json(self, value, prefix="Schema", max_depth=3, current_depth=0):
        """Aplana JSON-LD para exportar campos útiles sin explotar la tabla."""
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
        try:
            if not json_ld:
                return {}
            schema_data = json.loads(json_ld)
            return self.flatten_json(schema_data)
        except Exception:
            return {}

    @staticmethod
    def safe_text(value, limit=500):
        if value is None:
            return ""
        text = str(value).replace("\r", " ").replace("\n", " ").strip()
        while "  " in text:
            text = text.replace("  ", " ")
        return text[:limit]

    def extract_data_from_html(self, html, url):
        """Extrae datos SEO del HTML según columnas seleccionadas."""
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
        """Ejecuta una consulta HTTP. Esta función corre en los workers del pool."""
        if not self.is_running_flag():
            return "DETENIDO", {}

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
                data["Note"] = "Respuesta 200, pero no parece HTML"

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
                self.error.emit(f"Error general: {str(exc)}")
        finally:
            if executor is not None:
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except TypeError:
                    executor.shutdown(wait=False)

    def stop(self):
        self.mutex.lock()
        self.running = False
        self.mutex.unlock()


class CustomTableWidget(QTableWidget):
    """Tabla con selección por checkbox, Shift/Ctrl y atajos."""

    selection_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.last_checked_row = -1
        self.blocking = False

    def mousePressEvent(self, event):
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


class SitemapCrawler(QMainWindow):
    def __init__(self):
        super().__init__()
        self.urls = {}
        self.crawler_thread = None
        self.detector_thread = None
        self.detected_sitemaps = []
        self.sitemap_urls_map = {}
        self.table_data = {}
        self.url_to_row = {}
        self.selected_count = 0
        self.updating_button = False
        self.progress_file_path = None
        self.progress_dirty = False
        self.auto_save_every = 10
        self.processed_since_autosave = 0
        self.custom_user_agents = []
        self.user_agent_options = []

        self.init_ui()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setGeometry(100, 100, 2200, 900)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.auto_save_if_needed)
        self.autosave_timer.start(15000)

    def closeEvent(self, event):
        if self.progress_dirty:
            reply = QMessageBox.question(
                self,
                "Guardar avance",
                "Hay cambios sin guardar. ¿Quieres guardar el avance antes de cerrar?",
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
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()

        left_panel = QVBoxLayout()

        url_label = QLabel("Dominio o sitemap:")
        url_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("midominio.com o https://midominio.com/sitemap.xml")
        left_panel.addWidget(url_label)
        left_panel.addWidget(self.url_input)

        info_label = QLabel("Ingresa el dominio o URL directa del sitemap")
        info_label.setFont(QFont("Arial", 8))
        info_label.setStyleSheet("color: gray;")
        left_panel.addWidget(info_label)

        self.load_btn = QPushButton("Detectar sitemaps")
        self.load_btn.clicked.connect(self.auto_detect_sitemaps)
        left_panel.addWidget(self.load_btn)

        log_label = QLabel("Sitemaps detectados:")
        log_label.setFont(QFont("Arial", 9, QFont.Bold))
        left_panel.addWidget(log_label)

        self.sitemaps_list = QListWidget()
        self.sitemaps_list.itemSelectionChanged.connect(self.on_sitemap_selected)
        left_panel.addWidget(self.sitemaps_list)

        self.process_btn = QPushButton("Procesar URLs seleccionadas")
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self.reload_selected)
        self.process_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        left_panel.addWidget(self.process_btn)

        self.pending_btn = QPushButton("Procesar pendientes y errores")
        self.pending_btn.setEnabled(False)
        self.pending_btn.clicked.connect(self.reload_pending_or_errors)
        left_panel.addWidget(self.pending_btn)

        self.stop_btn = QPushButton("Detener ejecución")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_all_threads)
        left_panel.addWidget(self.stop_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_panel.addWidget(self.progress_bar)

        self.progress_label = QLabel("Sin proceso activo")
        self.progress_label.setFont(QFont("Arial", 8))
        self.progress_label.setStyleSheet("color: #666;")
        left_panel.addWidget(self.progress_label)

        config_group = QGroupBox("Configuración de ejecución")
        config_layout = QVBoxLayout()

        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("Timeout (seg):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setValue(10)
        self.timeout_spin.setRange(1, 120)
        timeout_layout.addWidget(self.timeout_spin)
        config_layout.addLayout(timeout_layout)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay por URL (seg):"))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setValue(0.2)
        self.delay_spin.setRange(0, 10)
        self.delay_spin.setSingleStep(0.1)
        delay_layout.addWidget(self.delay_spin)
        config_layout.addLayout(delay_layout)

        workers_layout = QHBoxLayout()
        workers_layout.addWidget(QLabel("Consultas simultáneas:"))
        self.workers_spin = QSpinBox()
        self.workers_spin.setValue(8)
        self.workers_spin.setRange(1, 50)
        workers_layout.addWidget(self.workers_spin)
        config_layout.addLayout(workers_layout)

        agent_layout = QVBoxLayout()
        agent_layout.addWidget(QLabel("Agente HTTP / User-Agent:"))

        self.user_agent_combo = QComboBox()
        self.user_agent_combo.setMinimumWidth(260)
        agent_layout.addWidget(self.user_agent_combo)

        agent_buttons_layout = QHBoxLayout()
        self.add_user_agent_btn = QPushButton("Agregar agente")
        self.add_user_agent_btn.clicked.connect(self.add_user_agent)
        agent_buttons_layout.addWidget(self.add_user_agent_btn)

        self.remove_user_agent_btn = QPushButton("Eliminar agente")
        self.remove_user_agent_btn.clicked.connect(self.remove_user_agent)
        agent_buttons_layout.addWidget(self.remove_user_agent_btn)

        agent_layout.addLayout(agent_buttons_layout)
        config_layout.addLayout(agent_layout)
        self.load_user_agents_config()
        self.refresh_user_agent_combo()

        self.autosave_check = QCheckBox("Auto-guardar avance")
        self.autosave_check.setChecked(True)
        config_layout.addWidget(self.autosave_check)

        config_group.setLayout(config_layout)
        left_panel.addWidget(config_group)

        columns_group = QGroupBox("Campos a extraer")
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

        progress_group = QGroupBox("Gestión de avance")
        progress_layout = QVBoxLayout()

        save_btn = QPushButton("Guardar avance")
        save_btn.clicked.connect(self.save_progress)
        progress_layout.addWidget(save_btn)

        save_as_btn = QPushButton("Guardar avance como...")
        save_as_btn.clicked.connect(self.save_progress_as)
        progress_layout.addWidget(save_as_btn)

        load_progress_btn = QPushButton("Cargar avance")
        load_progress_btn.clicked.connect(self.load_progress)
        progress_layout.addWidget(load_progress_btn)

        self.progress_file_label = QLabel("Archivo: no definido")
        self.progress_file_label.setFont(QFont("Arial", 8))
        self.progress_file_label.setStyleSheet("color: #666;")
        self.progress_file_label.setWordWrap(True)
        progress_layout.addWidget(self.progress_file_label)

        progress_group.setLayout(progress_layout)
        left_panel.addWidget(progress_group)

        left_panel.addStretch()

        reload_all_btn = QPushButton("Procesar todas las URLs")
        reload_all_btn.clicked.connect(self.reload_all)
        left_panel.addWidget(reload_all_btn)

        export_btn = QPushButton("Exportar a Excel")
        export_btn.clicked.connect(self.export_to_excel)
        left_panel.addWidget(export_btn)

        right_panel = QVBoxLayout()

        table_label = QLabel("URLs detectadas:")
        table_label.setFont(QFont("Arial", 10, QFont.Bold))
        right_panel.addWidget(table_label)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filtrar:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar en URLs, sitemap, estado o datos extraídos...")
        self.search_input.textChanged.connect(self.filter_table)
        search_layout.addWidget(self.search_input)
        right_panel.addLayout(search_layout)

        self.counter_label = QLabel("URLs: 0 | Visibles: 0 | Seleccionadas: 0 | Procesadas: 0")
        self.counter_label.setFont(QFont("Arial", 9))
        right_panel.addWidget(self.counter_label)

        selection_info = QLabel("Ctrl+A: seleccionar visibles | Shift+Click: rango | Ctrl+Click: toggle | Esc: deseleccionar")
        selection_info.setFont(QFont("Arial", 8))
        selection_info.setStyleSheet("color: #666; font-style: italic;")
        right_panel.addWidget(selection_info)

        self.table = CustomTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["✓", "URL", "Origen (Sitemap)", "Código HTTP", "Última revisión"])
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
        """Carga agentes personalizados desde un JSON local junto al ejecutable/script."""
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
        """Guarda solo agentes personalizados; los presets viven en el código."""
        payload = {
            "schema_version": 1,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "custom_user_agents": self.custom_user_agents,
        }
        with open(USER_AGENTS_FILE, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    def refresh_user_agent_combo(self, selected_agent=None):
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
                "name": item.get("name", "Agente sin nombre"),
                "value": value,
                "preset": bool(item.get("preset", False)),
            }
            self.user_agent_options.append(option)
            prefix = "Preset" if option["preset"] else "Personalizado"
            self.user_agent_combo.addItem(f'{option["name"]} ({prefix})', option)

        selected_index = 0
        for index, option in enumerate(self.user_agent_options):
            if option["value"] == previous_agent:
                selected_index = index
                break
        self.user_agent_combo.setCurrentIndex(selected_index)
        self.user_agent_combo.blockSignals(False)

    def get_selected_user_agent(self):
        if not hasattr(self, "user_agent_combo"):
            return DEFAULT_USER_AGENT
        data = self.user_agent_combo.currentData()
        if isinstance(data, dict):
            return clean_user_agent(data.get("value"))
        return DEFAULT_USER_AGENT

    def add_user_agent(self):
        name, ok = QInputDialog.getText(self, "Agregar agente HTTP", "Nombre del agente:")
        if not ok:
            return
        name = str(name).strip()
        if not name:
            QMessageBox.warning(self, "Agente HTTP", "Debes indicar un nombre para el agente.")
            return

        value, ok = QInputDialog.getMultiLineText(self, "Agregar agente HTTP", "User-Agent completo:", "")
        if not ok:
            return
        value = clean_user_agent(value)
        if not value:
            QMessageBox.warning(self, "Agente HTTP", "Debes indicar el User-Agent completo.")
            return

        for option in PRESET_USER_AGENTS + self.custom_user_agents:
            if clean_user_agent(option.get("value")) == value:
                QMessageBox.information(self, "Agente HTTP", "Ese User-Agent ya existe en la lista.")
                self.refresh_user_agent_combo(value)
                return

        self.custom_user_agents.append({"name": name, "value": value, "preset": False})
        try:
            self.save_user_agents_config()
        except Exception as exc:
            QMessageBox.warning(self, "Agente HTTP", f"El agente fue agregado, pero no se pudo guardar el archivo local:\n{str(exc)}")

        self.refresh_user_agent_combo(value)
        self.mark_dirty()
        QMessageBox.information(self, "Agente HTTP", "Agente agregado correctamente.")

    def remove_user_agent(self):
        data = self.user_agent_combo.currentData()
        if not isinstance(data, dict):
            return
        if data.get("preset"):
            QMessageBox.information(self, "Agente HTTP", "Los agentes predefinidos no se pueden eliminar.")
            return

        reply = QMessageBox.question(
            self,
            "Eliminar agente HTTP",
            f'¿Eliminar el agente personalizado "{data.get("name", "")}"?',
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
            QMessageBox.warning(self, "Agente HTTP", f"No se pudo actualizar el archivo local:\n{str(exc)}")

        self.refresh_user_agent_combo(DEFAULT_USER_AGENT)
        self.mark_dirty()

    def mark_dirty(self):
        self.progress_dirty = True

    def set_buttons_processing(self, processing):
        self.load_btn.setEnabled(not processing)
        self.process_btn.setEnabled((not processing) and bool(self.urls))
        self.pending_btn.setEnabled((not processing) and bool(self.urls))
        self.stop_btn.setEnabled(processing)

    def add_log(self, message):
        item = QListWidgetItem(message)
        self.sitemaps_list.addItem(item)
        self.sitemaps_list.scrollToBottom()

    def auto_detect_sitemaps(self):
        self.stop_all_threads()
        url = self.url_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Error", "Por favor ingresa una URL válida")
            return

        if self.progress_dirty and self.urls:
            reply = QMessageBox.question(
                self,
                "Reemplazar datos",
                "Esto reemplazará las URLs actuales. ¿Quieres continuar?",
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
        self.progress_label.setText("Detectando sitemaps...")
        self.set_buttons_processing(True)

        self.detector_thread = DetectorThread(url, self.timeout_spin.value(), self.get_selected_user_agent())
        self.detector_thread.progress.connect(self.add_log)
        self.detector_thread.finished.connect(self.detection_finished)
        self.detector_thread.error.connect(self.detection_error)
        self.detector_thread.start()

    def detection_finished(self, detected_sitemaps, urls_dict, sitemap_urls_map):
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
            self.progress_label.setText(f"Detección completada: {len(urls_dict)} URLs únicas")
            self.set_buttons_processing(False)
            self.mark_dirty()
            self.auto_save_if_needed(force=True)

            QMessageBox.information(
                self,
                "Éxito",
                f"Se encontraron {len(detected_sitemaps)} sitemap(s)\ncon {len(urls_dict)} URL(s) únicas",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Error finalizando detección: {str(exc)}")
            self.set_buttons_processing(False)
            self.progress_bar.setVisible(False)

    def detection_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Error en detección")
        self.set_buttons_processing(False)
        QMessageBox.critical(self, "Error", error_msg)

    def populate_table(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.urls))
        self.url_to_row.clear()

        for idx, (url, sitemap_origin) in enumerate(self.urls.items()):
            sitemap_name = sitemap_origin.split("/")[-1] if sitemap_origin else "N/A"
            if url not in self.table_data:
                self.table_data[url] = {
                    "url": url,
                    "sitemap": sitemap_name,
                    "status": "Pendiente",
                    "last_checked": "",
                    "data": {},
                    "selected": False,
                }
            else:
                self.table_data[url]["sitemap"] = self.table_data[url].get("sitemap") or sitemap_name

            self.url_to_row[url] = idx
            self.create_or_update_row(idx, url)

            if idx % 200 == 0:
                QApplication.processEvents()

        self.table.setSortingEnabled(True)
        self.rebuild_url_to_row()
        self.update_button_text()

    def create_or_update_row(self, row, url):
        row_data = self.table_data.get(url, {})

        checkbox = QCheckBox()
        checkbox.setChecked(bool(row_data.get("selected", False)))
        checkbox.stateChanged.connect(self.on_checkbox_state_changed)
        self.table.setCellWidget(row, 0, checkbox)

        self.set_table_item(row, 1, url)
        self.set_table_item(row, 2, row_data.get("sitemap", "N/A"))
        self.set_table_item(row, 3, row_data.get("status", "Pendiente"))
        self.color_status_cell(row_data.get("status", "Pendiente"), row, 3)
        self.set_table_item(row, 4, row_data.get("last_checked", ""))

        for key, value in row_data.get("data", {}).items():
            col_idx = self.ensure_column(key)
            self.set_table_item(row, col_idx, value)

    def set_table_item(self, row, col, value):
        item = QTableWidgetItem(str(value) if value is not None else "")
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, col, item)

    def color_status_cell(self, status, row, col):
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
        elif status == "Pendiente":
            item.setBackground(QColor(255, 255, 255))
        else:
            item.setBackground(QColor(211, 211, 211))

    def ensure_column(self, col_name):
        for col in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(col)
            if header and header.text() == col_name:
                return col

        col_idx = self.table.columnCount()
        self.table.insertColumn(col_idx)
        self.table.setHorizontalHeaderItem(col_idx, QTableWidgetItem(col_name))
        return col_idx

    def rebuild_url_to_row(self):
        self.url_to_row.clear()
        for row in range(self.table.rowCount()):
            url_item = self.table.item(row, 1)
            if url_item:
                self.url_to_row[url_item.text()] = row

    def on_checkbox_state_changed(self):
        if not self.table.blocking:
            self.mark_dirty()
            self.on_table_selection_changed()

    def on_table_selection_changed(self):
        if not self.updating_button:
            self.updating_button = True
            QTimer.singleShot(100, self.update_button_text)

    def update_button_text(self):
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

            status = self.table_data.get(url, {}).get("status", "Pendiente")
            if status and status != "Pendiente":
                processed_count += 1

        if self.selected_count > 0:
            self.process_btn.setText(f"Procesar selección ({self.selected_count} URLs)")
        else:
            self.process_btn.setText("Procesar URLs seleccionadas")

        self.counter_label.setText(
            f"URLs: {len(self.urls)} | Visibles: {visible_count} | Seleccionadas: {self.selected_count} | Procesadas: {processed_count}"
        )
        self.updating_button = False

    def on_sitemap_selected(self):
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
        urls = []
        for url, row_data in self.table_data.items():
            status = str(row_data.get("status", "Pendiente"))
            if status in ("", "Pendiente", "TIMEOUT", "CONNECTION ERROR", "ERROR") or status.startswith("4") or status.startswith("5"):
                urls.append(url)
        return urls

    def reload_selected(self):
        selected = self.get_selected_urls()
        if not selected:
            QMessageBox.warning(self, "Aviso", "Selecciona al menos una URL visible")
            return
        self.start_crawling(selected)

    def reload_pending_or_errors(self):
        selected = self.get_pending_or_error_urls()
        if not selected:
            QMessageBox.information(self, "Aviso", "No hay URLs pendientes o con error")
            return
        self.start_crawling(selected)

    def reload_all(self):
        if not self.urls:
            QMessageBox.warning(self, "Aviso", "Carga un sitemap primero")
            return
        self.start_crawling(list(self.urls.keys()))

    def start_crawling(self, urls_to_crawl):
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.crawler_thread.stop()
            self.crawler_thread.wait(3000)

        columns = [col for col, check in self.column_checks.items() if check.isChecked()]
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(urls_to_crawl))
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"Procesando 0 de {len(urls_to_crawl)} con {self.workers_spin.value()} consultas simultáneas")
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
        self.progress_label.setText(f"Procesando {current} de {total}: {status} | {url[:90]}")
        self.processed_since_autosave += 1
        self.mark_dirty()

        if self.autosave_check.isChecked() and self.processed_since_autosave >= self.auto_save_every:
            self.auto_save_if_needed(force=True, silent=True)
            self.processed_since_autosave = 0

        self.update_button_text()

    def crawling_finished(self):
        self.set_buttons_processing(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Procesamiento completado")
        self.auto_save_if_needed(force=True, silent=True)
        QMessageBox.information(self, "Éxito", "Procesamiento completado ✓")

    def crawling_error(self, error_msg):
        self.set_buttons_processing(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Error en procesamiento")
        QMessageBox.critical(self, "Error", error_msg)

    def build_progress_payload(self):
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
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar avance",
            self.default_progress_filename(),
            "Archivos JSON (*.json)",
        )
        if not file_path:
            return False
        self.progress_file_path = file_path
        return self.save_progress()

    def save_progress(self):
        if not self.progress_file_path:
            return self.save_progress_as()

        try:
            payload = self.build_progress_payload()
            with open(self.progress_file_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)

            self.progress_dirty = False
            self.update_progress_file_label()
            self.progress_label.setText(f"Avance guardado: {os.path.basename(self.progress_file_path)}")
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el avance:\n{str(exc)}")
            return False

    def auto_save_if_needed(self, force=False, silent=True):
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
                self.progress_label.setText(f"Avance auto-guardado: {os.path.basename(self.progress_file_path)}")
        except Exception as exc:
            if not silent:
                QMessageBox.warning(self, "Auto-guardado", f"No se pudo auto-guardar:\n{str(exc)}")

    def load_progress(self):
        if self.progress_dirty:
            reply = QMessageBox.question(
                self,
                "Cargar avance",
                "Hay cambios sin guardar. ¿Quieres continuar y reemplazar el estado actual?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        file_path, _ = QFileDialog.getOpenFileName(self, "Cargar avance", "", "Archivos JSON (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)

            if int(payload.get("schema_version", 0)) != PROGRESS_SCHEMA_VERSION:
                QMessageBox.warning(
                    self,
                    "Versión de avance",
                    "El archivo de avance tiene una versión distinta. Intentaré cargarlo de todos modos.",
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
            self.progress_label.setText(f"Avance cargado: {os.path.basename(file_path)}")
            self.set_buttons_processing(False)
            QMessageBox.information(self, "Éxito", "Avance cargado correctamente")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el avance:\n{str(exc)}")

    def default_progress_filename(self):
        parsed = urlparse(self.url_input.text().strip())
        domain = parsed.netloc or parsed.path or "sitemap"
        domain = domain.replace("/", "_").replace(":", "_").replace(".", "_")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"sitemap_crawler_avance_{domain}_{stamp}.json"

    def update_progress_file_label(self):
        if self.progress_file_path:
            self.progress_file_label.setText(f"Archivo: {self.progress_file_path}")
        else:
            self.progress_file_label.setText("Archivo: no definido")

    def export_to_excel(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Aviso", "No hay datos para exportar")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", "sitemap_crawler_export.xlsx", "Archivos Excel (*.xlsx)")
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
            QMessageBox.information(self, "Éxito", f"Archivo guardado: {file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Error al exportar: {str(exc)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    crawler = SitemapCrawler()
    crawler.show()
    sys.exit(app.exec_())
