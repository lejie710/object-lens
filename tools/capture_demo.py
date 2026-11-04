"""Capture the app in isolated headless Chrome using the real model."""
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from serve import make_server
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

OUT = ROOT / 'artifacts' / 'extension-demo'
OUT.mkdir(parents=True, exist_ok=True)
DOWNLOADS = OUT / 'downloads' / uuid.uuid4().hex[:12]
DOWNLOADS.mkdir(parents=True, exist_ok=True)
os.environ['SE_CACHE_PATH'] = str(ROOT / '.local' / 'selenium')
os.environ['SE_AVOID_STATS'] = 'true'
os.environ['SE_OFFLINE'] = 'true'


def state(driver):
    return driver.find_element(By.TAG_NAME, 'html').get_attribute('data-state')


def predictions(driver):
    return [{'label': row.get_attribute('data-label'), 'score': float(row.get_attribute('data-score'))}
            for row in driver.find_elements(By.CSS_SELECTOR, '.result-row')]


def minimum(driver, value):
    driver.execute_script("""
        const input = document.getElementById('minimum-score');
        input.value = arguments[0]; input.dispatchEvent(new Event('input', {bubbles: true}));
    """, str(value))


def main():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--window-size=1440,1000')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1')
    options.add_experimental_option('prefs', {'download.default_directory': str(DOWNLOADS),
                                             'download.prompt_for_download': False})
    options.set_capability('goog:loggingPrefs', {'browser': 'ALL', 'performance': 'ALL'})
    server = make_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report = {'evidence_type': 'real model demonstration and rendered layout check',
              'limits': 'One Windows laptop and Chrome; not a general accuracy or performance benchmark.',
              'viewports': []}
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.execute_cdp_cmd('Browser.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(DOWNLOADS)})
        report['browser_version'] = driver.capabilities['browserVersion']
        driver.get(f'http://127.0.0.1:{server.server_port}')
        WebDriverWait(driver, 120).until(lambda d: state(d) in {'ready', 'error'})
        assert state(driver) == 'ready'
        driver.save_screenshot(str(OUT / 'empty.png'))
        start = time.perf_counter()
        driver.find_element(By.ID, 'try-sample').click()
        WebDriverWait(driver, 120).until(lambda d: state(d) in {'complete', 'empty', 'error'})
        assert state(driver) == 'complete'
        assert driver.find_element(By.ID, 'filename').text == 'coffee.png'
        report['sample_ui_seconds'] = round(time.perf_counter() - start, 3)
        report['all_predictions'] = predictions(driver)
        driver.find_element(By.CSS_SELECTOR, '.result-row[data-label="cup"]').click()
        driver.save_screenshot(str(OUT / 'desktop.png'))
        minimum(driver, 0.8)
        report['filtered_predictions'] = predictions(driver)
        assert report['filtered_predictions'] == [p for p in report['all_predictions'] if p['score'] >= 0.8]
        driver.save_screenshot(str(OUT / 'filtered.png'))
        before = set(DOWNLOADS.glob('*.png'))
        driver.find_element(By.ID, 'save-result').click()
        files = WebDriverWait(driver, 15).until(lambda d: list(set(DOWNLOADS.glob('*.png')) - before))
        report['export_filename'] = files[0].name
        report['export_relative_path'] = files[0].relative_to(OUT).as_posix()
        assert files[0].read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
        minimum(driver, 1.0)
        assert state(driver) == 'filtered-empty'
        assert not driver.find_element(By.ID, 'save-result').is_enabled()
        driver.save_screenshot(str(OUT / 'filtered-empty.png'))
        minimum(driver, 0.8)
        for width in [320, 390, 768, 1440]:
            driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',
                                   {'width': width, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False})
            metrics = driver.execute_script("""
                return {width: innerWidth, availableWidth: document.documentElement.clientWidth,
                  contentWidth: document.documentElement.scrollWidth,
                  controls: ['choose-image','try-sample','clear-image','save-result','minimum-score'].map(id => {
                    const r = document.getElementById(id).getBoundingClientRect();
                    return {id, left: r.left, right: r.right, width: r.width};
                  })};
            """)
            assert metrics['contentWidth'] <= metrics['availableWidth'] + 1, metrics
            assert all(c['left'] >= -1 and c['right'] <= metrics['availableWidth'] + 1 and c['width'] > 0
                       for c in metrics['controls']), metrics
            report['viewports'].append(metrics)
            driver.save_screenshot(str(OUT / f'width-{width}.png'))
        driver.execute_cdp_cmd('Emulation.clearDeviceMetricsOverride', {})
        driver.find_element(By.ID, 'clear-image').click()
        assert state(driver) == 'ready'
        report['console'] = driver.get_log('browser')
        urls = set()
        for entry in driver.get_log('performance'):
            event = json.loads(entry['message'])['message']
            if event['method'] == 'Network.requestWillBeSent':
                url = event['params']['request']['url']
                if url.startswith(('http://', 'https://')):
                    urls.add(url)
        report['external_http_requests'] = [url for url in sorted(urls) if urlsplit(url).hostname != '127.0.0.1']
        assert not report['external_http_requests']
        report['passed'] = True
    finally:
        (OUT / 'observations.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        if driver is not None:
            driver.quit()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
