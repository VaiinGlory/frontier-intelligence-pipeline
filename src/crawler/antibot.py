"""
FrontierAtlas Data Intelligence Pipeline
Anti-Bot Navigation & Stealth Scraper Architecture
Demonstrates production strategies for Cloudflare, Datadome, and heavily JavaScript-rendered domains.
"""

import random
from typing import Dict, List, Optional

class AntiBotManager:
    """
    Manages browser identity, TLS fingerprinting, user-agent pools, and proxy rotation.
    Provides stealth execution parameters for high-value intelligence sources.
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:135.0) Gecko/20100101 Firefox/135.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15"
    ]

    SEC_CH_UA_LIST = [
        '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        '"Chromium";v="133", "Not(A:Brand";v="24", "Google Chrome";v="133"',
        '"Not A(Brand";v="8", "Chromium";v="132", "Microsoft Edge";v="132"'
    ]

    def __init__(self, proxy_pool: Optional[List[str]] = None):
        self.proxy_pool = proxy_pool or []

    def get_stealth_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        """
        Constructs realistic browser headers that mimic genuine desktop clients.
        Includes HTTP/2 pseudo-header order, Sec-Ch-Ua, and localized language preferences.
        """
        ua = random.choice(self.USER_AGENTS)
        sec_ua = random.choice(self.SEC_CH_UA_LIST)

        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site" if referer else "none",
            "Sec-Fetch-User": "?1",
            "Sec-Ch-Ua": sec_ua,
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"' if "Windows" in ua else ('"macOS"' if "Macintosh" in ua else '"Linux"')
        }
        if referer:
            headers["Referer"] = referer

        return headers

    def get_proxy(self) -> Optional[str]:
        """Returns next rotating residential or data center proxy."""
        if not self.proxy_pool:
            return None
        return random.choice(self.proxy_pool)

    @staticmethod
    def get_playwright_stealth_scripts() -> str:
        """
        JavaScript injection payload for headless Playwright / Puppeteer.
        Defeats common client-side bot detection checks (navigator.webdriver, chrome.runtime, permissions).
        """
        return """
        // 1. Remove navigator.webdriver flag
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        // 2. Mock Chrome runtime object
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };

        // 3. Mock plugins list
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });

        // 4. Mock notification permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """
