# Health Data Sync

Utilities for syncing Samsung Health export data into Google Fit.

## Setup

1. Copy your OAuth client secret JSON to `credentials.json`.
   - Use a Google Cloud project with the Fitness API enabled.
   - For an installed app, the redirect URI should include `http://localhost`.

2. Install dependencies:
   ```bash
   ./setup.sh
   ```

3. If the OAuth consent screen is still in testing:
   - Open the Google Cloud Console for your project.
   - Go to `APIs & Services` → `OAuth consent screen`.
   - Add your Google account under `Test users`.
   - Save the changes.

## Usage

```bash
source .venv/bin/activate
python push.py
```

## Important

If you see a Google OAuth error like:

- `health-data-sync has not completed the Google verification process`
- `Error 403: access_denied`

then your app is still in testing mode and your account is not allowed yet. Add your Google account as a test user or publish/verify the OAuth consent screen to resolve this.

## Notes

- `push.py` currently requests the write-only fitness scope:
  `https://www.googleapis.com/auth/fitness.activity.write`
- `setup.sh` creates and activates a `.venv`, then installs dependencies from `requirements.txt`.
