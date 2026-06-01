import os
import sys
import datetime
import json
import pickle
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import csv
import glob

SCOPES = ['https://www.googleapis.com/auth/fitness.activity.write']
TOKEN_PATH = os.path.join(os.path.dirname(__file__), 'token.pickle')
UPLOAD_LOG_PATH = os.path.join(os.path.dirname(__file__), 'uploaded_dates.json')

def get_fit_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                creds = None
        if not creds:
            try:
                creds_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            except RefreshError as e:
                sys.exit(
                    f"\nOAuth failed: {e}\n\n"
                    "Your Google Cloud project is likely in testing mode and your account\n"
                    "has not been added as a test user. To fix this:\n\n"
                    "  1. Go to https://console.cloud.google.com/apis/credentials/consent\n"
                    "  2. Select your project\n"
                    "  3. Under 'Test users', click 'Add Users' and add your Google account\n"
                    "  4. Save and re-run this script\n"
                )
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    return build('fitness', 'v1', credentials=creds)


DATA_SOURCE_ID = "raw:com.google.step_count.delta:362088348000:samsung_health_import"


SAMSUNG_HEALTH_DIR = os.path.join(os.path.dirname(__file__), "Samsung_Health")


def parse_day_time(value):
    """Parse a day_time value which may be epoch ms or a datetime string."""
    if not value:
        return None
    value = value.strip().rstrip('.')
    try:
        # epoch milliseconds (e.g. 1746921600000)
        ms = int(value)
        return datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)
    except ValueError:
        pass
    try:
        return datetime.datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError:
        return None


def load_upload_log():
    """Return a set of date strings that have already been uploaded."""
    if os.path.exists(UPLOAD_LOG_PATH):
        with open(UPLOAD_LOG_PATH) as f:
            return set(json.load(f))
    return set()


def save_upload_log(uploaded):
    with open(UPLOAD_LOG_PATH, 'w') as f:
        json.dump(sorted(uploaded), f)


def upload_file(service, file, seen_dates, upload_log):
    with open(file, newline="", encoding='utf-8-sig') as f:
        next(f)  # skip metadata row (table_name, version, field_count)
        reader = csv.DictReader(f)
        for row in reader:
            try:
                step_count = int(float(row.get("step_count", 0)))
                day_time_raw = row.get("day_time")
                if step_count <= 0:
                    continue
                dt = parse_day_time(day_time_raw)
                if not dt:
                    continue

                date_key = str(dt.date())
                if date_key in upload_log:
                    continue
                if date_key in seen_dates:
                    continue
                seen_dates.add(date_key)

                start = int(dt.timestamp() * 1e9)
                end = int((dt + datetime.timedelta(days=1)).timestamp() * 1e9) - 1

                data_set = {
                    "dataSourceId": DATA_SOURCE_ID,
                    "minStartTimeNs": start,
                    "maxEndTimeNs": end,
                    "point": [{
                        "startTimeNanos": start,
                        "endTimeNanos": end,
                        "dataTypeName": "com.google.step_count.delta",
                        "value": [{"intVal": step_count}]
                    }]
                }
                dataset_id = f"{start}-{end}"
                service.users().dataSources().datasets().patch(
                    userId='me',
                    dataSourceId=DATA_SOURCE_ID,
                    datasetId=dataset_id,
                    body=data_set
                ).execute()
                upload_log.add(date_key)
                save_upload_log(upload_log)
                print(f"Uploaded {step_count} steps for {date_key} from {os.path.basename(file)}")
            except HttpError as e:
                if e.resp.status == 403:
                    sys.exit(
                        f"\nAPI returned 403 for {file}: {e}\n\n"
                        "The Fitness API may not be enabled, or your account lacks access.\n"
                        "Check:\n"
                        "  1. https://console.cloud.google.com/apis/library/fitness.googleapis.com\n"
                        "  2. Ensure your account is a test user on the OAuth consent screen\n"
                    )
                print(f"API error in {file}: {e}")
            except Exception as e:
                print(f"Error processing row in {file}: {e}")


def upload_all_day_summaries(service, samsung_health_dir=SAMSUNG_HEALTH_DIR):
    patterns = [
        "com.samsung.shealth.tracker.pedometer_day_summary.*.csv",
        "com.samsung.shealth.activity.day_summary.*.csv",
    ]
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(samsung_health_dir, "*", pat)))

    print(f"Found {len(files)} step-count CSVs.")
    upload_log = load_upload_log()
    seen_dates = set()
    for file in files:
        upload_file(service, file, seen_dates, upload_log)


if __name__ == "__main__":
    service = get_fit_service()
    upload_all_day_summaries(service)
