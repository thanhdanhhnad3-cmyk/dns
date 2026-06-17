"""
Tinyhost API client for temporary email operations
"""
import time
import random
import string
import requests
from typing import Optional

from config import (
    TINYHOST_BASE_URL,
    TINYHOST_RANDOM_DOMAINS_URL,
    TINYHOST_INBOX_URL,
    EMAIL_POLL_INTERVAL,
    EMAIL_POLL_TIMEOUT,
)
from logger import log


class TinyhostClient:
    """Client for tinyhost.shop temporary email API"""

    def __init__(self, proxy: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
        self._available_domains: Optional[list[str]] = None

    def _get_random_user(self, length: int = 10) -> str:
        """Generate a random username."""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def get_available_domains(self, limit: int = 20) -> list[str]:
        """Fetch available email domains from tinyhost."""
        try:
            resp = self.session.get(
                TINYHOST_RANDOM_DOMAINS_URL,
                params={"limit": limit},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            domains = data.get("domains", [])
            if domains:
                log.info(f"  [Tinyhost] Found {len(domains)} domains available")
                return domains
            return []
        except Exception as e:
            log.error(f"  [Tinyhost] Failed to get domains: {e}")
            return []

    def generate_email(self) -> tuple[str, str, str]:
        """Generate a new temporary email address. Returns (full_email, domain, user)."""
        if not self._available_domains:
            self._available_domains = self.get_available_domains(30)
            if not self._available_domains:
                # Fallback to hardcoded list
                self._available_domains = [
                    "tinyhost.shop", "fhost.shop", "onepices.shop",
                    "gwsop.shop", "shopzgi.shop", "jngpfy.shop",
                    "gopagb.shop", "onxea.shop", "mhostz.shop",
                    "hostpda.shop", "tempmail.shop", "tmpmail.shop",
                    "mailn.shop", "tempmailz.shop", "tempemailz.shop",
                    "mailtem.shop", "tmpmailz.shop", "shopea.shop",
                    "eztvg.shop", "gopgop.shop", "shophost.shop",
                    "tempmail.shop", "mailtemp.shop", "tempemail.shop",
                ]
                log.warning("  [Tinyhost] Using fallback domain list")

        # Filter out tinyhost.shop since it might be reserved
        candidates = [d for d in self._available_domains if d != "tinyhost.shop"]
        if not candidates:
            candidates = self._available_domains

        domain = random.choice(candidates)
        user = self._get_random_user(12)
        full_email = f"{user}@{domain}"

        log.info(f"  [Tinyhost] Generated: {full_email}")
        return full_email, domain, user

    def get_inbox(self, domain: str, user: str, page: int = 1, limit: int = 20) -> dict:
        """Get emails from inbox."""
        try:
            resp = self.session.get(
                f"{TINYHOST_BASE_URL}/api/email/{domain}/{user}/",
                params={"page": page, "limit": limit},
                timeout=15
            )
            if resp.status_code == 404:
                return {"emails": []}
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.debug(f"  [Tinyhost] Inbox check failed: {e}")
            return {"emails": []}

    def get_email_by_id(self, domain: str, user: str, email_id: int) -> dict:
        """Read full email content by ID."""
        try:
            resp = self.session.get(
                f"{TINYHOST_BASE_URL}/api/email/{domain}/{user}/{email_id}",
                timeout=15
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.error(f"  [Tinyhost] Failed to read email {email_id}: {e}")
            return {}

    def wait_for_email(
        self,
        domain: str,
        user: str,
        timeout: int = EMAIL_POLL_TIMEOUT,
        interval: int = EMAIL_POLL_INTERVAL,
        subject_contains: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Poll inbox until an email arrives (or times out).
        If subject_contains is provided, waits for email matching that substring.
        """
        log.info(f"  [Tinyhost] Waiting for email (timeout={timeout}s)...")
        start = time.time()

        while time.time() - start < timeout:
            inbox = self.get_inbox(domain, user)
            emails = inbox.get("emails", [])

            if emails:
                for email in emails:
                    subject = email.get("subject", "")
                    if subject_contains is None or subject_contains.lower() in subject.lower():
                        elapsed = int(time.time() - start)
                        log.info(f"  [Tinyhost] Email found after {elapsed}s: {subject}")
                        return email

            time.sleep(interval)

        log.warning(f"  [Tinyhost] Timed out waiting for email")
        return None

    def get_latest_email_body(self, domain: str, user: str) -> Optional[str]:
        """Get the body of the most recent email."""
        inbox = self.get_inbox(domain, user)
        emails = inbox.get("emails", [])
        if not emails:
            return None

        latest = emails[0]
        email_id = latest.get("id")
        if not email_id:
            return latest.get("body")

        full_email = self.get_email_by_id(domain, user, email_id)
        return full_email.get("body") or full_email.get("html_body", "")
