# parking

Small Python script that registers a license plate on a daily web form.
It logs in to the operator's site, follows the day's one-time link, fills
in the plate + email on the permit portal, and submits.

## How it works

1. Opens the start page.
2. Accepts the cookie banner if shown.
3. Logs in with credentials from environment variables.
4. Finds the daily registration link on the page and follows it. The URL
   is a one-time token that changes daily, so the script reads it
   dynamically -- nothing is hardcoded.
5. Fills in the license plate + email on the permit portal and submits.
6. Prints the confirmation message returned by the portal.

If anything goes wrong, the error is printed to stderr -- check the
GitHub Actions log (or your terminal when running locally).

## Requirements

- Python 3.10+
- Chromium (installed automatically by Playwright)
- An account on the operator's site

## Setup

```powershell
git clone https://github.com/<you>/parking.git
cd parking

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
playwright install chromium

Copy-Item .env.example .env
notepad .env   # fill in LOGIN_EMAIL and LOGIN_PASSWORD
```

On macOS / Linux replace the venv activation line with
`source .venv/bin/activate` and `Copy-Item` with `cp`.

## Run

```powershell
python parking.py
```

The first time you run it, leave `HEADLESS=0` in `.env` so the browser
window is visible -- handy for spotting problems. Switch to `HEADLESS=1`
once you're confident.

## Environment variables

| Variable         | Required | Default   | Description                            |
| ---------------- | -------- | --------- | -------------------------------------- |
| `LOGIN_EMAIL`    | yes      | -         | Account email                          |
| `LOGIN_PASSWORD` | yes      | -         | Account password                       |
| `LICENSE_PLATE`  | no       | `CJ73789` | Plate to register                      |
| `HEADLESS`       | no       | `0`       | `1` to hide the browser window         |

## Scheduling

The permit only covers the day you register it, so it needs to run every
morning. A GitHub Actions workflow at `.github/workflows/daily-parking.yml`
handles this automatically. To use it, push the repo and add these in
**Settings -> Secrets and variables -> Actions**:

| Type     | Name             | Value                  |
| -------- | ---------------- | ---------------------- |
| Secret   | `LOGIN_EMAIL`    | your account email     |
| Secret   | `LOGIN_PASSWORD` | your account password  |
| Variable | `LICENSE_PLATE`  | plate (optional)       |

For local-only use on Windows, Task Scheduler works too: run
`python C:\path\to\parking.py` daily with the working directory set
to the project folder so `.env` is picked up.

## Safety notes

- Never commit your real `.env` -- it is already in `.gitignore`.
- If you rotate the password, just update `.env` and the matching
  GitHub secret.

## Files

- `parking.py` -- the script
- `requirements.txt` -- Python deps (`playwright`, `python-dotenv`)
- `.env.example` -- template for your secrets
- `.gitignore` -- excludes `.env`, virtualenvs, caches
- `.github/workflows/daily-parking.yml` -- daily scheduled run
