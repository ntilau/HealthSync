# Health Data Sync

Sync Samsung Health export data into Google Fit — push step counts and read them back.

## Setup

1. Copy your OAuth client secret JSON to `credentials.json`.
   - Use a Google Cloud project with the **Fitness API** enabled.
   - For an installed app, the redirect URI must include `http://localhost`.

2. Install dependencies:
   ```bash
   ./setup.sh
   ```

3. Add your Google account as a test user (if the OAuth consent screen is still in testing):
   - Go to **APIs & Services** > **OAuth consent screen** in the [Google Cloud Console](https://console.cloud.google.com/apis/credentials/consent).
   - Under **Test users**, add your Google account and save.

## Usage

Activate the virtual environment first:
```bash
source .venv/bin/activate
```

### Push step counts to Google Fit
```bash
python push.py
```
Reads `Samsung_Health/` CSVs (`tracker.pedometer_day_summary` and `activity.day_summary`), extracts daily step counts, and uploads them to Google Fit. Subsequent runs skip already-uploaded dates via `uploaded_dates.json`.

### Read step counts back
```bash
python read.py                  # last 30 days
python read.py 2025-01-01       # from a start date to today
python read.py 2025-01-01 2025-12-31  # explicit date range
```
Queries Google Fit via the aggregate API and prints daily step counts with a total.

## How it works

- **OAuth** — First run opens your browser for Google sign-in. Credentials are persisted in `token.pickle` (push) and `token_read.pickle` (read) and refreshed silently on expiry.
- **CSV parsing** — Handles Samsung Health's two-row header format (metadata row + column names) and both epoch-ms and datetime-string `day_time` values.
- **Deduplication** — `uploaded_dates.json` tracks every date successfully pushed to Google Fit, so re-runs only upload new data.
- **Data source** — Uses a writable `raw:com.google.step_count.delta` data source instead of Google's read-only derived source.

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Error 403: access_denied` | Add your Google account as a test user on the OAuth consent screen |
| `Cannot read data of type com.google.step_count.delta` | The script is using a read-only data source — this is now handled |
| `The caller does not have permission` | Verify the Fitness API is enabled and your account is a test user |
| `Unable to fetch DataSource` | The data source wasn't auto-created — re-run; if it persists, check API enablement |
