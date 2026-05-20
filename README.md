# parking

[![Daily parking](https://github.com/Soevejen47/parking/actions/workflows/daily-parking.yml/badge.svg)](https://github.com/Soevejen47/parking/actions/workflows/daily-parking.yml)

Small Python automation that registers one or more license plates on a
daily web form. Runs unattended via GitHub Actions every morning.

## How it works

1. Opens the operator's start page in headless Chromium.
2. Accepts the cookie banner if shown.
3. Logs in with credentials from environment variables.
4. Follows the day's one-time registration link to a third-party permit
   portal (the link's token changes daily, so the script reads its `href`
   dynamically -- nothing is hardcoded).
5. Submits the portal form once per `PLATE:receipt-email` entry.
6. Prints a per-plate summary; exits non-zero if any plate failed.

## Requirements

- Python 3.10 or newer
- Chromium (installed by Playwright on first run)
- An account on the operator's site

## Setup

```powershell
git clone https://github.com/Soevejen47/parking.git
cd parking

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
playwright install chromium

Copy-Item .env.example .env
notepad .env   # fill in real values
```

On macOS / Linux, replace the venv activation with
`source .venv/bin/activate` and `Copy-Item` with `cp`.

## Run

```powershell
python parking.py
```

Leave `HEADLESS=0` in `.env` the first time so you can watch the browser.
Flip it to `1` once it works.

## Environment variables

| Variable         | Required | Default | Description                                           |
| ---------------- | -------- | ------- | ----------------------------------------------------- |
| `LOGIN_EMAIL`    | yes      | -       | Account login email                                   |
| `LOGIN_PASSWORD` | yes      | -       | Account password                                      |
| `REGISTRATIONS`  | yes      | -       | One or more `PLATE:receipt-email` entries (see below) |
| `HEADLESS`       | no       | `0`     | `1` to hide the browser window                        |
| `TIMEOUT_MS`     | no       | `20000` | Per-action Playwright timeout, in ms                  |
| `MAX_ATTEMPTS`   | no       | `2`     | Retries on transient timeouts (login / portal open)   |

### REGISTRATIONS format

Comma- or newline-separated `PLATE:email` pairs. The email per entry is the
address the operator sends the receipt to -- it does not have to match
`LOGIN_EMAIL`. Lines starting with `#` are skipped.

```
REGISTRATIONS=AB12345:alice@example.com,CD67890:bob@example.com
```

You can also use newlines inside a single secret value:

```
AB12345:alice@example.com
CD67890:bob@example.com
# spare car, disabled for now
# EF99999:alice@example.com
```

## Scheduling on GitHub Actions

The permit only covers the day you register it, so the workflow at
[.github/workflows/daily-parking.yml](.github/workflows/daily-parking.yml)
fires just past local midnight. GitHub cron is UTC; the triggers are
chosen to land after midnight in both Danish winter and summer:

| Trigger (UTC) | Copenhagen winter | Copenhagen summer | Role     |
| ------------- | ----------------- | ----------------- | -------- |
| `23:12`       | `00:12`           | `01:12`           | primary  |
| `23:42`       | `00:42`           | `01:42`           | fallback |
| `00:27`       | `01:27`           | `02:27`           | fallback |

GitHub can delay or skip scheduled triggers, so the two fallbacks act as
a safety net. A `check` job guards every run: once any run has succeeded
that night, the remaining triggers detect it and skip the work, so the
car is registered at most once per night.

Add these in **Settings -> Secrets and variables -> Actions -> Secrets**:

| Name             | Value                                       |
| ---------------- | ------------------------------------------- |
| `LOGIN_EMAIL`    | your account email                          |
| `LOGIN_PASSWORD` | your account password                       |
| `REGISTRATIONS`  | `PLATE:email,PLATE:email,...` (see above)   |

Trigger a one-off run from **Actions -> Daily parking -> Run workflow**
to verify your secrets before relying on the schedule.

For local-only use on Windows, Task Scheduler works too: run
`python C:\path\to\parking.py` daily with the working directory set to the
project folder so `.env` is loaded.

## Troubleshooting

- **`LOGIN_EMAIL is empty`** -- the secret/env var isn't set or is blank.
  Check **Settings -> Secrets and variables -> Actions** on GitHub, or
  your local `.env`.
- **`Bad REGISTRATIONS entry ...`** -- format error. Each entry is
  `PLATE:email`, separated by commas or newlines. Plates have no colons,
  but emails do not either -- it's safe to split on the first `:`.
- **All attempts timed out** -- the login form or portal didn't respond.
  Bump `TIMEOUT_MS` (e.g. `30000`) and try again. If the operator changed
  its markup, look for the recent change in `parking.py`.
- **One plate fails, others succeed** -- the script keeps going after
  per-plate errors. Check the summary at the bottom of the Actions log.
- **Workflow not running on schedule** -- GitHub disables scheduled
  workflows on repos that have had no activity for 60 days. Push any
  commit to wake it up, or trigger it manually.

## Safety notes

- Never commit `.env` -- it is gitignored.
- Secrets and any string that matches a secret are auto-masked in
  workflow logs by GitHub.
- If you rotate the password, update both `.env` (local) and the
  matching GitHub Actions secret.

## Files

- `parking.py` -- the script
- `requirements.txt` -- pinned Python deps
- `.env.example` -- template for your secrets
- `.gitignore` -- excludes `.env`, virtualenvs, caches
- `.github/workflows/daily-parking.yml` -- daily scheduled run
- `LICENSE` -- MIT

## License

MIT -- see [LICENSE](LICENSE).
