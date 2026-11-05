"""Shared browser/server fixtures. Every browser runs headlessly."""
from __future__ import annotations

import json
import logging
import os
import re
import struct
import threading
import warnings
import zlib
from datetime import datetime, timezone
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from helpers import WORKER_TRACE_SCRIPT
from serve import AppHandler, make_server

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def controlled_url():
    """Only this server exposes the simulated worker; no model is loaded."""
    server = make_server(port=0, test_mode=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def real_url():
    """The ordinary application server never exposes controlled predictions."""
    server = make_server(port=0, test_mode=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def recoverable_worker_url():
    """Simulate one HTTP failure while loading the controlled worker, then recover."""
    class FailFirstWorkerRequest(AppHandler):
        def do_GET(self):
            if urlsplit(self.path).path == "/test-worker.js" and self.server.failures_left:
                self.server.failures_left -= 1
                content = b"Simulated worker loading failure."
                self.send_response(503)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)
                return
            super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(FailFirstWorkerRequest, test_mode=True))
    server.failures_left = 1
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def browser(request):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-search-engine-choice-screen")
    # The application and model are local. Keep this isolated test browser from
    # resolving unrelated hosts or starting ambient network downloads.
    options.add_argument("--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    os.environ.setdefault("SE_CACHE_PATH", str(ROOT / ".local" / "selenium"))
    os.environ.setdefault("SE_AVOID_STATS", "true")
    driver = webdriver.Chrome(options=options)
    try:
        driver.set_page_load_timeout(30)
        driver.set_script_timeout(30)
        # Record worker inference requests and replies on every page this browser opens.
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": WORKER_TRACE_SCRIPT})
        yield driver
        failed = any(
            getattr(request.node, f"rep_{phase}", None)
            and getattr(request.node, f"rep_{phase}").failed
            for phase in ("setup", "call")
        )
        if failed:
            name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", request.node.nodeid)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            target = ROOT / "artifacts" / "test-failures" / name / timestamp
            try:
                target.mkdir(parents=True, exist_ok=True)
                driver.save_screenshot(str(target / "browser.png"))
                (target / "page.html").write_text(driver.page_source, encoding="utf-8")
                (target / "console.json").write_text(
                    json.dumps(driver.get_log("browser"), indent=2), encoding="utf-8"
                )
                (target / "context.json").write_text(
                    json.dumps({"url": driver.current_url, "title": driver.title,
                                "test": request.node.nodeid,
                                "evidence_type": "real inference" if "inference" in request.node.keywords
                                else "controlled application test"}, indent=2),
                    encoding="utf-8",
                )
            except Exception as error:
                logging.getLogger(__name__).warning(
                    "Could not capture failure evidence for %s: %s", request.node.nodeid, error
                )
                try:
                    (target / "capture-error.txt").write_text(str(error), encoding="utf-8")
                except Exception as capture_error:
                    logging.getLogger(__name__).warning(
                        "Could not write capture-error.txt for %s: %s", request.node.nodeid, capture_error
                    )
    finally:
        driver.quit()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


# A Windows runner can briefly run out of socket buffer space, so one static file
# fails to load before any application code runs. That is the test machine, not the
# app, and it is the only failure that earns one reload.
RUNNER_NETWORK_ERROR = "net::ERR_NO_BUFFER_SPACE"


def _page_ready(driver, timeout):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.find_element("tag name", "html").get_attribute("data-state") == "ready"
        )
        return True
    except TimeoutException:
        return False


def _page_load_report(driver, browser_log):
    loaded = driver.execute_script(
        "return performance.getEntriesByType('resource').map((entry) => entry.name.split('/').pop());"
    )
    state = driver.find_element("tag name", "html").get_attribute("data-state")
    errors = [entry.get("message", "") for entry in browser_log if entry.get("level") == "SEVERE"]
    return f"page state {state!r}; loaded files {loaded}; browser errors {errors}"


@pytest.fixture
def app(browser, controlled_url):
    browser.get(controlled_url)
    if _page_ready(browser, 10):
        return browser
    browser_log = browser.get_log("browser")
    report = _page_load_report(browser, browser_log)
    if not any(RUNNER_NETWORK_ERROR in entry.get("message", "") for entry in browser_log):
        pytest.fail(f"The controlled page did not become ready within 10 s: {report}")
    warnings.warn(f"Reloaded the controlled page once after a runner network error: {report}")
    browser.get(controlled_url)
    if not _page_ready(browser, 10):
        report = _page_load_report(browser, browser.get_log("browser"))
        pytest.fail(f"The controlled page did not become ready after one reload: {report}")
    return browser


@pytest.fixture
def downloads(browser, tmp_path):
    folder = tmp_path / "downloads"
    folder.mkdir()
    browser.execute_cdp_cmd("Browser.setDownloadBehavior", {
        "behavior": "allow", "downloadPath": str(folder), "eventsEnabled": True,
    })
    return folder


@pytest.fixture
def make_image(tmp_path):
    """Create a valid, synthetic solid-colour PNG without an imaging dependency."""
    def create(name="normal.png", width=640, height=480, colour=(102, 143, 179), total_bytes=None):
        def chunk(kind, payload):
            return (struct.pack(">I", len(payload)) + kind + payload
                    + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

        header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        row = b"\x00" + bytes(colour) * width
        data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                + chunk(b"IDAT", zlib.compress(row * height, level=6)))
        ending = chunk(b"IEND", b"")
        if total_bytes is not None:
            extra_bytes = total_bytes - len(data) - len(ending)
            if extra_bytes < 0:
                raise ValueError("Requested size is smaller than the encoded PNG")
            if extra_bytes:
                # A legal ancillary text chunk changes file size without changing pixels.
                # Its 12-byte chunk framing and keyword/separator are part of the total.
                keyword = b"Padding\x00"
                text_bytes = extra_bytes - 12 - len(keyword)
                if text_bytes < 0:
                    raise ValueError("Requested padding is too small for a PNG tEXt chunk")
                data += chunk(b"tEXt", keyword + b"x" * text_bytes)
        data += ending
        path = tmp_path / name
        path.write_bytes(data)
        return path

    return create
