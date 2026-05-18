"""
Daily parking registration -- supports multiple plates per run.

Logs in to the operator's site once, opens the daily permit-portal link,
then submits the portal form once per (plate, receipt-email) entry. A
single workflow run can therefore register several cars at once.

The daily portal link is a one-time token that changes every day -- the
script reads its href off the operator page, so nothing is hardcoded.

Config comes from environment variables. See the README for the list.
"""

from __future__ import annotations

import os
import sys
import time

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


# --- configuration -----------------------------------------------------------

START_URL = "https://www.dsb.dk/dsb-plus/fri-parkering/"
PERMIT_HOST = "parkcare.parkzone.dk"

# Lowercase substrings -- if any are present in the portal's response, treat
# the registration as successful. Both fresh and idempotent re-registrations
# (same plate twice in one day) end up matching.
SUCCESS_MARKERS: tuple[str, ...] = (
    "digital p-tilladelse",
    "allerede registreret",
)

DEFAULT_TIMEOUT_MS = int(os.environ.get("TIMEOUT_MS", "20000"))
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "2"))
RETRY_DELAY_SECONDS = 30

# How long to poll for the portal's response message to refresh between
# successive submissions on the same page.
MESSAGE_POLL_TIMEOUT_S = 15
MESSAGE_POLL_INTERVAL_S = 0.5


# --- exit codes --------------------------------------------------------------

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_CONFIG = 2


# --- helpers -----------------------------------------------------------------

def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR: environment variable {name} is empty.", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    return value


def parse_registrations(raw: str) -> list[tuple[str, str]]:
    """Parse "plate1:email1, plate2:email2, ..." into a list of pairs.

    Plates are uppercased and stripped of whitespace; emails are stripped.
    Lines/entries that are empty or commented with '#' are skipped.
    """
    items: list[tuple[str, str]] = []
    # Support both comma and newline separators -- both feel natural.
    for chunk in raw.replace("\n", ",").split(","):
        entry = chunk.strip()
        if not entry or entry.startswith("#"):
            continue
        if ":" not in entry:
            raise ValueError(
                f"Bad REGISTRATIONS entry {entry!r} -- expected 'PLATE:email'"
            )
        plate, email = entry.split(":", 1)
        plate = plate.strip().upper()
        email = email.strip()
        if not plate or not email:
            raise ValueError(f"Bad REGISTRATIONS entry {entry!r}")
        items.append((plate, email))
    if not items:
        raise ValueError("REGISTRATIONS is empty after parsing")
    return items


def is_success(message: str) -> bool:
    msg = message.lower()
    return any(marker in msg for marker in SUCCESS_MARKERS)


def current_message(portal: Page) -> str:
    """Return the current #LMessage text, or '' if not present."""
    locator = portal.locator("#LMessage")
    if locator.count() == 0:
        return ""
    try:
        return locator.inner_text().strip()
    except PlaywrightTimeoutError:
        return ""


def submit_one(portal: Page, plate: str, receipt_email: str) -> str:
    """Submit one plate/email and return the portal's response message.

    Polls #LMessage until its text differs from the previous submission
    (or first becomes non-empty). Raises TimeoutError on timeout.
    """
    previous = current_message(portal)

    portal.locator("#TBRegNo").fill(plate)
    portal.locator("#Email").fill(receipt_email)
    portal.locator("#BCreate").click()

    deadline = time.monotonic() + MESSAGE_POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        current = current_message(portal)
        if current and current != previous:
            return current
        time.sleep(MESSAGE_POLL_INTERVAL_S)
    raise TimeoutError(
        f"Portal response did not arrive within {MESSAGE_POLL_TIMEOUT_S}s"
    )


# --- main flow ---------------------------------------------------------------

def run_once(
    login_email: str,
    password: str,
    registrations: list[tuple[str, str]],
    headless: bool,
) -> list[tuple[str, str, str | None]]:
    """Log in once, then submit each registration.

    Returns a list of (plate, message, error_string_or_None) tuples,
    one per registration attempted.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context()
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = context.new_page()

        try:
            page.goto(START_URL, wait_until="domcontentloaded")

            # Cookie banner -- only appears on first visit per context.
            try:
                page.locator("button.coi-banner__accept").first.click(timeout=5_000)
            except PlaywrightTimeoutError:
                pass

            # Sign in.
            page.get_by_role(
                "link", name="Log ind eller tilmeld dig gratis"
            ).first.click()
            page.wait_for_url("**/auth/log-ind**")
            page.locator('input[type="email"]').fill(login_email)
            page.locator('input[type="password"]').fill(password)
            page.locator('button[type="submit"]:has-text("Log ind")').click()
            page.wait_for_url("**/dsb-plus/fri-parkering/**")

            # Open the daily portal link in a new tab.
            permit_link = page.locator(f'a[href*="{PERMIT_HOST}"]').first
            permit_link.wait_for(state="visible")
            with context.expect_page() as popup_info:
                permit_link.click()
            portal = popup_info.value
            portal.wait_for_load_state("domcontentloaded")
            portal.locator("#TBRegNo").wait_for(state="visible")

            # Submit each registration on the same portal page.
            results: list[tuple[str, str, str | None]] = []
            for plate, receipt_email in registrations:
                try:
                    message = submit_one(portal, plate, receipt_email)
                    results.append((plate, message, None))
                except Exception as exc:
                    # Keep going -- one failure shouldn't block the rest.
                    results.append((plate, "", repr(exc)))
            return results

        finally:
            context.close()
            browser.close()


def main() -> int:
    login_email = require_env("LOGIN_EMAIL")
    password = require_env("LOGIN_PASSWORD")
    try:
        registrations = parse_registrations(require_env("REGISTRATIONS"))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    headless = os.environ.get("HEADLESS", "0") == "1"

    print(
        f"[*] {len(registrations)} registration(s) "
        f"headless={headless} timeout={DEFAULT_TIMEOUT_MS}ms "
        f"attempts={MAX_ATTEMPTS}"
    )

    # Retry the whole batch on transient timeouts during login / portal open.
    # Per-plate failures inside run_once are returned as result rows and not
    # retried -- they're typically operator-side issues (bad plate, etc).
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            results = run_once(login_email, password, registrations, headless)
            break
        except PlaywrightTimeoutError as exc:
            print(
                f"[!] attempt {attempt}/{MAX_ATTEMPTS} timed out: {exc}",
                file=sys.stderr,
            )
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
        except Exception as exc:
            print(f"[!] fatal: {exc!r}", file=sys.stderr)
            return EXIT_FAILURE
    else:
        print(f"[!] all {MAX_ATTEMPTS} attempts timed out", file=sys.stderr)
        return EXIT_FAILURE

    # Report.
    all_ok = True
    print()
    print("=" * 72)
    for plate, message, error in results:
        if error is not None:
            all_ok = False
            print(f"[FAIL] {plate}: {error}")
            continue
        ok = is_success(message)
        all_ok = all_ok and ok
        label = "OK  " if ok else "FAIL"
        print(f"[{label}] {plate}: {message}")
    print("=" * 72)

    return EXIT_OK if all_ok else EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
