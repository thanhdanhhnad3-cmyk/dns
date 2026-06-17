"""
NextDNS registration engine using Playwright browser automation.
Handles: signup -> generate API key -> extract credentials.
"""
import asyncio
import re
import time
import random
import string
from datetime import datetime, timezone
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from typing import Optional
from dataclasses import dataclass

from config import NEXTDNS_WEB_URL
from logger import log


@dataclass
class NextDNSResult:
    success: bool
    email: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    profile_id: Optional[str] = None
    error: Optional[str] = None
    cookies: Optional[dict] = None
    created_at: Optional[str] = None  # ISO timestamp when registered


class NextDNSEngine:
    """
    Handles the full NextDNS registration flow via Playwright.
    Flow: /signup -> fill form -> submit -> /{profileId}/setup
          -> /account -> GENERATE API KEY -> extract key
    """

    def __init__(
        self,
        email: str,
        password: str,
        headless: bool = True,
        timeout: int = 90,
    ):
        self.email = email
        self.password = password
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def _launch(self) -> bool:
        """Launch browser and create context."""
        try:
            pw = await async_playwright().start()
            self.browser = await pw.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-gpu',
                ]
            )
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self.page = await self.context.new_page()
            self._playwright = pw  # keep reference so it can be stopped
            return True
        except Exception as e:
            log.error(f"  [NextDNS] Failed to launch browser: {e}")
            return False

    async def _cleanup(self):
        """Close browser resources."""
        try:
            if self.page:
                await self.page.close()
                self.page = None
        except Exception:
            pass
        try:
            if self.context:
                await self.context.close()
                self.context = None
        except Exception:
            pass
        try:
            if self.browser:
                await self.browser.close()
                self.browser = None
        except Exception:
            pass
        try:
            # Force close playwright
            from playwright.async_api import async_playwright
            # Kill any orphaned processes
            pass
        except Exception:
            pass

    async def _fill_and_submit_signup(self) -> tuple[bool, Optional[str]]:
        """
        Navigate to /signup, fill form, submit.
        Returns (success, profile_id).
        """
        try:
            await self.page.goto(
                f"{NEXTDNS_WEB_URL}/signup",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await self.page.wait_for_timeout(2500)  # Wait for React hydration

            # Fill email
            email_input = await self.page.query_selector("input[type='email']")
            if not email_input:
                log.error("  [NextDNS] Email input not found")
                return False, None
            await email_input.fill(self.email)

            # Fill password
            pass_input = await self.page.query_selector("input[type='password']")
            if not pass_input:
                log.error("  [NextDNS] Password input not found")
                return False, None
            await pass_input.fill(self.password)

            # Submit
            submit_btn = await self.page.query_selector("button[type='submit']")
            if submit_btn:
                await submit_btn.click()
            else:
                await self.page.keyboard.press("Enter")

            # Wait for redirect to setup or account page
            await self.page.wait_for_url(
                lambda url: "/setup" in url or "/account" in url,
                timeout=60000,
            )
            await self.page.wait_for_timeout(2000)

            # Extract profile ID from URL
            match = re.search(r'/([a-f0-9]{6,})/setup', self.page.url)
            profile_id = match.group(1) if match else None
            return True, profile_id

        except asyncio.TimeoutError:
            log.error("  [NextDNS] Signup timeout")
            return False, None
        except Exception as e:
            log.error(f"  [NextDNS] Signup error: {e}")
            return False, None

    async def _generate_api_key(self) -> Optional[str]:
        """
        Navigate to /account, click GENERATE API KEY, extract key.
        Returns API key string or None.
        """
        try:
            await self.page.goto(
                f"{NEXTDNS_WEB_URL}/account",
                wait_until="networkidle",
                timeout=20000,
            )
            await self.page.wait_for_timeout(2000)

            # Click GENERATE API KEY button
            generate_btn = await self.page.query_selector(
                "button:has-text('Generate')"
            )
            if not generate_btn:
                log.error("  [NextDNS] GENERATE API KEY button not found")
                return None

            await generate_btn.click()
            await self.page.wait_for_timeout(3000)

            # Extract 40-char hex from page
            page_text = await self.page.inner_text("body")
            matches = re.findall(r'\b([a-f0-9]{40})\b', page_text)
            for match in matches:
                return match

            # Also scan HTML for the key
            html = await self.page.content()
            matches = re.findall(r'\b([a-f0-9]{40})\b', html)
            for match in matches:
                # Verify it's near API-related text
                idx = html.find(match)
                ctx = html[max(0, idx - 150):idx + 150].lower()
                if any(kw in ctx for kw in ['api', 'key', 'generate', 'secret']):
                    return match

            log.error("  [NextDNS] API key not found after generation")
            return None

        except Exception as e:
            log.error(f"  [NextDNS] API key generation error: {e}")
            return None

    async def register(self) -> NextDNSResult:
        """
        Execute full registration flow.
        Returns NextDNSResult with credentials.
        """
        if not await self._launch():
            return NextDNSResult(success=False, error="browser_launch_failed")

        try:
            # Step 1: Signup
            ok, profile_id = await self._fill_and_submit_signup()
            if not ok:
                return NextDNSResult(success=False, error="signup_failed")

            log.info(f"  [NextDNS] Registered! Profile: {profile_id}")

            # Step 2: Generate API key
            api_key = await self._generate_api_key()
            if not api_key:
                return NextDNSResult(
                    success=True,
                    email=self.email,
                    password=self.password,
                    api_key="NOT_FOUND",
                    profile_id=profile_id,
                    error="api_key_not_found",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )

            log.info(f"  [NextDNS] API Key: {api_key}")

            # Step 3: Get cookies
            cookies_list = await self.context.cookies()
            cookies = {c["name"]: c["value"] for c in cookies_list}

            return NextDNSResult(
                success=True,
                email=self.email,
                password=self.password,
                api_key=api_key,
                profile_id=profile_id,
                cookies=cookies,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        finally:
            await self._cleanup()


async def register_account(
    email: str,
    password: str,
    headless: bool = True,
) -> NextDNSResult:
    """Convenience function to register a single account."""
    engine = NextDNSEngine(email, password, headless=headless)
    return await engine.register()
