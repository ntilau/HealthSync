# HealthSync

Sync Samsung Health export data into Google Fit — push step counts, distance, calories, weight, body fat, hydration, sleep, and heart points; read everything back with a single command.

## Data Flows

- **Samsung Health → Google Fit**: Use `python scripts/push.py` to upload CSV files from `raw_exports/samsung_health/` to Google Fit (steps, distance, calories, weight, body fat, hydration, sleep, heart points).
- **Google Takeout (Fit + Google Health) → Apple Health**: Use `python scripts/prepare_apple_health_data.py` to convert JSON/CSV files from `raw_exports/google_fit/` and `raw_exports/google_health/` into Apple Health‑compatible CSV files in `apple_health_import/`.
- **Google Fit → Local Summary**: Use `python scripts/read.py` to read data from the Google Fit API and output a daily table of steps, distance, calories, heart points, and sleep, plus latest body metrics.
- **Apple Health → Local Export**: Use the iOS app in `ios_app/` to read data from Apple Health and export CSV files compatible with `apple_health_import/` format.

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

4. Prepare your data:
   - Export your Samsung Health data and place the CSV files in `raw_exports/samsung_health/` preserving the folder structure (see below).
   - Place your Google Takeout data (from Google Fit and Google Health) in `raw_exports/google_fit/` and `raw_exports/google_health/` respectively.
   - Expected Samsung Health structure inside `raw_exports/samsung_health/`:
     ```
     raw_exports/samsung_health/
     └── <timestamped subdirectory>/  (e.g., samsunghealth_ntilau_20260321185675/)
         ├── com.samsung.shealth.<category>/
         │   ├── tracker.pedometer_day_summary.*.csv
         │   ├── activity.day_summary.*.csv
         │   ├── pedometer_step_count.*.csv
         │   ├── com.samsung.health.weight.*.csv
         │   ├── com.samsung.health.height.*.csv
         │   ├── calories_burned.details.*.csv
         │   ├── water_intake.*.csv
         │   ├── com.samsung.shealth.sleep.*.csv
         │   └── com.samsung.health.exercise.*.csv
     ```
   - Google Takeout data should already be in the correct internal structure:
     ```
     raw_exports/google_fit/
     ├── activities/
     ├── all_data/
     ├── all_sessions/
     └── daily_activity_metrics/
     raw_exports/google_health/
     ├── account_changes/
     ├── atrial_fibrillation_ppg/
     ├── biometrics/
     ├── commerce_google_data/
     ├── daily_readiness/
     ├── discover/
     ├── email_notifications_settings_google_data/
     └── global_export_data/
     ```

## Usage

Activate the virtual environment first:
```bash
source .venv/bin/activate
```

### Push data to Google Fit
```bash
python scripts/push.py
```
Reads Samsung Health CSVs from `raw_exports/samsung_health/` and uploads the following to Google Fit:

| Category | Data type | Source CSV |
|----------|-----------|------------|
| Activity | Steps, distance, calories (daily totals) | `tracker.pedometer_day_summary`, `activity.day_summary` |
| Activity | Steps, distance, calories (minute-level) | `pedometer_step_count` |
| Activity | Heart Points (computed from speed) | `pedometer_step_count`, `com.samsung.health.exercise` |
| Body | Weight, body fat percentage | `com.samsung.health.weight` |
| Body | Height | `com.samsung.health.height` |
| Nutrition | Hydration (water intake) | `water_intake` |
| Nutrition | Total daily calories (resting + active) | `calories_burned.details` |
| Sleep | Sleep segments | `com.samsung.shealth.sleep` |

Subsequent runs skip already-uploaded dates via `uploaded_dates.json`.

### Read data back from Google Fit
```bash
python scripts/read.py                      # last 30 days
python scripts/read.py 2025-01-01           # from a start date to today
python scripts/read.py 2025-01-01 2025-12-31  # explicit date range
```
Outputs a daily table with steps, distance, calories, heart points, and sleep, plus latest body metrics (weight, height, body fat).

### Prepare Google Takeout data for Apple Health import
```bash
python scripts/prepare_apple_health_data.py
```
Reads data from `raw_exports/google_fit/` and `raw_exports/google_health/` and writes Apple Health-compatible CSV files to `apple_health_import/`.

### Export data from Apple Health (iOS app)
1. Open the `ios_app/` directory in Xcode
2. Configure signing with your Apple ID
3. Build and run on your iPhone
4. Grant HealthKit permissions when prompted
5. Select date range and fetch data from Apple Health
6. Export to CSV files in the app's Documents directory
7. Transfer exported CSV files to `apple_health_import/` directory

See `ios_app/README.md` for detailed instructions.

## How it works

- **OAuth** — First run opens your browser for Google sign-in. Credentials are persisted in `token.pickle` (push) and `token_read.pickle` (read) and refreshed silently on expiry.
- **CSV parsing** — Handles Samsung Health's two-row header format (metadata row + column names) and both epoch-ms and datetime-string timestamps.
- **Deduplication** — `uploaded_dates.json` tracks every date successfully pushed per metric, so re-runs only upload new data.
- **Data source** — Uses writable `raw:com.google.*` data sources instead of Google's read-only derived sources.
- **Heart Points** — Computed from walking/running speed during minute-level intervals: ≥4 km/h earns 1 point/min, ≥7 km/h earns 2 points/min per [WHO guidelines](https://www.who.int/news-room/fact-sheets/detail/physical-activity).

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Error 403: access_denied` | Add your Google account as a test user on the OAuth consent screen |
| `Cannot read data of type com.google.step_count.delta` | The data source may not exist yet — run `python scripts/push.py` first to create it |
| `The caller does not have permission` | Verify the Fitness API is enabled and your account is a test user |
| `Unable to fetch DataSource` | The data source wasn't auto-created — re-run; if it persists, check API enablement |

## iOS App Development

The `ios_app/` contains a SwiftUI iOS application for reading data from Apple Health (HealthKit) and exporting it in CSV format compatible with this repository's `apple_health_import/` directory.

See `ios_app/README.md` for build and usage instructions.