"""
Daily parking registration.

Logs in to the operator's website, follows the daily registration link
(which opens a third-party permit portal in a new tab), fills in license
plate + email, and submits the form. Prints the confirmation text.

The daily link is a one-time token that changes every day -- the script
reads its href off the page, so nothing needs to be hardcoded.

If the upstream site ever changes its markup, the script prints the
error to stderr and exits non-zero so the run log makes it obvious.

See the README for install + run instructions.
"""

from __future__ import annotations

import os
import sys

# python-dotenv is optional. If it is installed and a .env file is present
# next to this script, the variables in it are loaded into os.environ.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


# --- configuration -----------------------------------------------------------

START_URL = "https://www.dsb.dk/dsb-plus/fri-parkering/"
PERMIT_HOST = "parkcare.parkzone.dk"
DEFAULT_PLATE = "CJ73789"
SUCCESS_MARKER = "digital p-tilladelse"


# --- helpers -----------------------------------------------------------------

def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(
            f"ERROR: environment variable {name} is empty.\n"
            f"       Set it in a .env file or in your shell session.",
            file=sys.stderr,
        )
        sys.exit(2)
    return value


# --- main flow ---------------------------------------------------------------

def register_parking(email: str, password: str, plate: str, headless: bool) -> int:
    """Run the full registration flow. Returns a process exit code."""

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        # A fresh context = no cookies from a previous run.
        context = browser.new_context()
        page = context.new_page()

        try:
            # 1) Open the start page.
            print(f"[*] Opening start page")
            page.goto(START_URL, wait_until="domcontentloaded")

            # 2) Accept the cookie banner if it shows up.
            #    Rendered by Cookie Information; uses the CSS class
            #    .coi-banner__accept on its "Acceptér alle" button.
            try:
                page.locator("button.coi-banner__accept").first.click(timeout=5000)
                print("[*] Cookie banner accepted.")
            except PlaywrightTimeoutError:
                print("[*] No cookie banner shown -- continuing.")

            # 3) Click the big login / signup CTA.
            #    Two copies on the page (hero + body); .first is fine.
            page.get_by_role(
                "link", name="Log ind eller tilmeld dig gratis"
            ).first.click()

            # 4) Fill the login form.
            page.wait_for_url("**/auth/log-ind**", timeout=15_000)
            page.locator('input[type="email"]').wait_for(state="visible", timeout=15_000)
            page.locator('input[type="email"]').fill(email)
            page.locator('input[type="password"]').fill(password)
            page.locator('button[type="submit"]:has-text("Log ind")').click()
            print("[*] Login form submitted.")

            # 5) After login the site redirects back to the start page and
            #    a daily registration link to the permit portal appears.
            page.wait_for_url("**/dsb-plus/fri-parkering/**", timeout=20_000)
            permit_link = page.locator(f'a[href*="{PERMIT_HOST}"]').first
            permit_link.wait_for(state="visible", timeout=20_000)
            print("[*] Logged in. Found daily registration link.")

            # 6) The link has target="_blank" -- it opens a new tab.
            with context.expect_page(timeout=15_000) as new_page_info:
                permit_link.click()
            portal = new_page_info.value
            portal.wait_for_load_state("domcontentloaded")
            print("[*] Permit portal opened.")

            # 7) Fill the portal form.
            #    #TBRegNo = license plate field
            #    #Email   = email field
            #    #BCreate = "Opret" submit button
            portal.locator("#TBRegNo").wait_for(state="visible", timeout=15_000)
            portal.locator("#TBRegNo").fill(plate)
            portal.locator("#Email").fill(email)
            portal.locator("#BCreate").click()
            print(f"[*] Submitted plate {plate}.")

            # 8) Read and print the response message (span #LMessage).
            message_locator = portal.locator("#LMessage")
            message_locator.wait_for(state="visible", timeout=15_000)
            message = message_locator.inner_text().strip()

            ok = SUCCESS_MARKER in message.lower()
            print()
            print("=" * 72)
            print("SUCCESS" if ok else "RESULT (unexpected wording -- please verify)")
            print("=" * 72)
            print(message)
            print("=" * 72)
            return 0 if ok else 1

        except Exception as exc:
            print(f"[!] Flow failed: {exc!r}", file=sys.stderr)
            return 1

        finally:
            context.close()
            browser.close()


def main() -> int:
    email = require_env("LOGIN_EMAIL")
    password = require_env("LOGIN_PASSWORD")
    plate = os.environ.get("LICENSE_PLATE", DEFAULT_PLATE).strip().upper()
    headless = os.environ.get("HEADLESS", "0") == "1"

    print(f"[*] LOGIN_EMAIL    = {email}")
    print(f"[*] LICENSE_PLATE  = {plate}")
    print(f"[*] HEADLESS       = {headless}")

    return register_parking(email, password, plate, headless)


if __name__ == "__main__":
    sys.exit(main())
