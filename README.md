# DSB Plus daily parking automation

Small Python script that registers your car for the daily free parking offered
to DSB Plus members. It logs in to dsb.dk, follows the daily ParkCare /
ParkZone link, fills in your license plate + email, and submits.

## How it works

1. Opens `https://www.dsb.dk/dsb-plus/fri-parkering/`.
2. Accepts the cookie banner if shown.
3. Logs in with credentials from environment variables.
4. Finds the `Tilmeld parkering <date>` link on the parking page and follows
   it. The URL is a one-time token that changes daily, so the script reads
   it dynamically -- nothing is hardcoded.
5. Fills in the license plate + email on ParkCare and clicks `Opret`.
6. Prints the confirmation message returned by ParkCare.

If anything goes wrong, the error is printed to stderr -- check the
GitHub Actions log (or your terminal when running locally).

## Requirements

- Python 3.10+
- Chromium (installed automatically by Playwright)
- A DSB Plus account

## Setup

```powershell
git clone https://github.com/<you>/dsb-parking.git
cd dsb-parking

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
playwright install chromium

Copy-Item .env.example .env
notepad .env   # fill in DSB_EMAIL and DSB_PASSWORD
```

On macOS / Linux replace the venv activation line with
`source .venv/bin/activate` and `Copy-Item` with `cp`.

## Run

```powershell
python dsb_parking.py
```

The first time you run it, leave `HEADLESS=0` in `.env` so the browser
window is visible -- handy for spotting problems. Switch to `HEADLESS=1`
once you're confident.

## Environment variables

| Variable        | Required | Default   | Description                            |
| --------------- | -------- | --------- | -------------------------------------- |
| `DSB_EMAIL`     | yes      | -         | Your DSB Plus account email            |
| `DSB_PASSWORD`  | yes      | -         | Your DSB Plus account password         |
| `LICENSE_PLATE` | no       | `CJ73789` | Plate to register                      |
| `HEADLESS`      | no       | `0`       | `1` to hide the browser window         |

## Scheduling it daily

The DSB permit only covers the day you register it, so you need to run the
script every morning. On Windows, use Task Scheduler with the action
`python C:\path\to\dsb_parking.py` and set the working directory to the
project folder so `.env` is picked up. On Linux / macOS, use cron.

## Safety notes

- Never commit your real `.env` -- it is already in `.gitignore`.
- If you rotate your DSB password, just update `.env`.

## Files

- `dsb_parking.py` -- the script
- `requirements.txt` -- Python deps (`playwright`, `python-dotenv`)
- `.env.example` -- template for your secrets
- `.gitignore` -- excludes `.env`, virtualenvs, caches
