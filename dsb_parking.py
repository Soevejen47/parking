"""
DSB Plus daily free-parking registration.

This script walks the same flow you would do by hand:
  1. Open https://www.dsb.dk/dsb-plus/fri-parkering/
  2. Accept the cookie banner if it appears.
  3. Log in to DSB Plus using DSB_EMAIL and DSB_PASSWORD from the environment.
  4. After login, click the daily "Tilmeld parkering ..." link.
     That link opens ParkCare / ParkZone in a NEW tab. The exact URL is a
     one-time token (it changes every day), so we never hardcode it -- we
     just read its href off the page.
  5. On the ParkCare page, fill in the license plate and email, then click
     the "Opret" (Create) button.
  6. Print the confirmation message that ParkCare shows.

Selectors used in this script were verified against the live site, so they
should be stable enough for everyday use. If DSB ever changes them, the
script prints the error and exits non-zero so the GitHub Actions log
makes it obvious.

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

DSB_URL = "https://www.dsb.dk/dsb-plus/fri-parkering/"
DEFAULT_PLATE = "CJ73789"


# --- helpers -----------------------------------------------------------------

def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(
            f"ERROR: environment variable {name} is empty.\n"
            f"       Set it in a .env file or in your PowerShell session.",
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
            # 1) Open the DSB Plus parking page.
            print(f"[*] Opening {DSB_URL}")
            page.goto(DSB_URL, wait_until="domcontentloaded")

            # 2) Accept the cookie banner if it shows up.
            #    The banner is rendered by Cookie Information and uses the
            #    CSS class .coi-banner__accept on its "Acceptér alle" button.
            try:
                page.locator("button.coi-banner__accept").first.click(timeout=5000)
                print("[*] Cookie banner accepted.")
            except PlaywrightTimeoutError:
                print("[*] No cookie banner shown -- continuing.")

            # 3) Click the big "Log ind eller tilmeld dig gratis" CTA.
            #    There are two on the page (hero + body); .first is fine.
            page.get_by_role(
                "link", name="Log ind eller tilmeld dig gratis"
            ).first.click()

            # 4) Fill the login form.
            page.wait_for_url("**/auth/log-ind**", timeout=15_000)
            page.locator('input[type="email"]').wait_for(state="visible", timeout=15_000)
            page.locator('input[type="email"]').fill(email)
            page.locator('input[type="password"]').fill(password)
            # The submit button has type=submit and text "Log ind".
            page.locator('button[type="submit"]:has-text("Log ind")').click()
            print("[*] Login form submitted.")

            # 5) After login, DSB redirects back to /dsb-plus/fri-parkering/
            #    and the "Tilmeld parkering <date>" link becomes visible.
            page.wait_for_url("**/dsb-plus/fri-parkering/**", timeout=20_000)
            tilmeld_link = page.locator('a[href*="parkcare.parkzone.dk"]').first
            tilmeld_link.wait_for(state="visible", timeout=20_000)
            print("[*] Logged in. Found 'Tilmeld parkering' link.")

            # 6) The Tilmeld link has target="_blank" -- it opens a new tab.
            #    expect_page() captures that new tab cleanly.
            with context.expect_page(timeout=15_000) as new_page_info:
                tilmeld_link.click()
            parkcare = new_page_info.value
            parkcare.wait_for_load_state("domcontentloaded")
            print(f"[*] ParkCare opened: {parkcare.url}")

            # 7) Fill the ParkCare form.
            #    #TBRegNo = license plate field (placeholder "Nummerplade")
            #    #Email   = email field
            #    #BCreate = "Opret" submit button
            parkcare.locator("#TBRegNo").wait_for(state="visible", timeout=15_000)
            parkcare.locator("#TBRegNo").fill(plate)
            parkcare.locator("#Email").fill(email)
            parkcare.locator("#BCreate").click()
            print(f"[*] Submitted plate {plate} to ParkCare.")

            # 8) Wait for ParkCare's response message and print it.
            #    The result text is rendered inside the span #LMessage.
            message_locator = parkcare.locator("#LMessage")
            message_locator.wait_for(state="visible", timeout=15_000)
            message = message_locator.inner_text().strip()

            print()
            print("=" * 72)
            if "digital p-tilladelse" in message.lower():
                print("SUCCESS")
            else:
                print("RESULT (unexpected wording -- please verify)")
            print("=" * 72)
            print(message)
            print("=" * 72)
            return 0 if "digital p-tilladelse" in message.lower() else 1

        except Exception as exc:
            print(f"[!] Flow failed: {exc!r}", file=sys.stderr)
            return 1

        finally:
            context.close()
            browser.close()


def main() -> int:
    email = require_env("DSB_EMAIL")
    password = require_env("DSB_PASSWORD")
    plate = os.environ.get("LICENSE_PLATE", DEFAULT_PLATE).strip().upper()
    headless = os.environ.get("HEADLESS", "0") == "1"

    print(f"[*] DSB_EMAIL      = {email}")
    print(f"[*] LICENSE_PLATE  = {plate}")
    print(f"[*] HEADLESS       = {headless}")

    return register_parking(email, password, plate, headless)


if __name__ == "__main__":
    sys.exit(main())
