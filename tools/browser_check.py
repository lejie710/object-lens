"""Verify a headless Chrome session without interacting with the user's desktop."""
import json
import os
from pathlib import Path

from selenium import webdriver

ROOT = Path(__file__).resolve().parents[1]
os.environ["SE_CACHE_PATH"] = str(ROOT / ".local" / "selenium")
os.environ["SE_AVOID_STATS"] = "true"
options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--window-size=1440,1000")
options.add_argument("--disable-extensions")
options.add_argument("--no-first-run")
options.add_argument("--no-default-browser-check")
driver = webdriver.Chrome(options=options)
try:
    driver.get("data:text/html,<title>Object Lens browser check</title><p>Ready</p>")
    print(json.dumps({"title": driver.title, "browser": driver.capabilities.get("browserVersion"),
                      "driver": driver.capabilities.get("chrome", {}).get("chromedriverVersion")}, indent=2))
finally:
    driver.quit()
