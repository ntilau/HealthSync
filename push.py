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

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.write',
    'https://www.googleapis.com/auth/fitness.location.write',
]
TOKEN_PATH = os.path.join(os.path.dirname(__file__), 'token.pickle')
UPLOAD_LOG_PATH = os.path.join(os.path.dirname(__file__), 'uploaded_dates.json')

DATA_SOURCE_STEPS = "raw:com.google.step_count.delta:362088348000:samsung_health_import"
DATA_SOURCE_DISTANCE = "raw:com.google.distance.delta:362088348000:samsung_health_import"
DATA_SOURCE_CALORIES = "raw:com.google.calories.expended:362088348000:samsung_health_import"

SAMSUNG_HEALTH_DIR = os.path.join(os.path.dirname(__file__), "Samsung_Health")


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


def load_upload_log():
    if os.path.exists(UPLOAD_LOG_PATH):
        with open(UPLOAD_LOG_PATH) as f:
            data = json.load(f)
    else:
        return {}

    if isinstance(data, list):
        return {"steps": set(data), "calories": set(), "distance": set()}

    return {metric: set(dates) for metric, dates in data.items()}


def save_upload_log(upload_log):
    with open(UPLOAD_LOG_PATH, 'w') as f:
        json.dump({m: sorted(ds) for m, ds in upload_log.items()}, f)


def parse_day_time(value):
    if not value:
        return None
    value = value.strip().rstrip('.')
    try:
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


def push_point(service, data_source_id, start_ns, end_ns, data_type_name, value):
    data_set = {
        "dataSourceId": data_source_id,
        "minStartTimeNs": start_ns,
        "maxEndTimeNs": end_ns,
        "point": [{
            "startTimeNanos": start_ns,
            "endTimeNanos": end_ns,
            "dataTypeName": data_type_name,
            "value": [value]
        }]
    }
    service.users().dataSources().datasets().patch(
        userId='me',
        dataSourceId=data_source_id,
        datasetId=f"{start_ns}-{end_ns}",
        body=data_set
    ).execute()


def upload_file(service, file, seen, upload_log):
    with open(file, newline="", encoding='utf-8-sig') as f:
        next(f)  # skip metadata row
        reader = csv.DictReader(f)
        for row in reader:
            try:
                step_count = int(float(row.get("step_count", 0)))
                distance = float(row.get("distance", 0)) if row.get("distance") else 0.0
                calorie = float(row.get("calorie", 0)) if row.get("calorie") else 0.0
                day_time_raw = row.get("day_time")

                if step_count <= 0 and distance <= 0.0 and calorie <= 0.0:
                    continue

                dt = parse_day_time(day_time_raw)
                if not dt:
                    continue

                date_key = str(dt.date())
                start_ns = int(dt.timestamp() * 1e9)
                end_ns = int((dt + datetime.timedelta(days=1)).timestamp() * 1e9) - 1

                for metric in ("steps", "distance", "calories"):
                    upload_log.setdefault(metric, set())
                    seen.setdefault(metric, set())

                if step_count > 0 and date_key not in upload_log["steps"] and date_key not in seen["steps"]:
                    push_point(service, DATA_SOURCE_STEPS, start_ns, end_ns,
                               "com.google.step_count.delta", {"intVal": step_count})
                    upload_log["steps"].add(date_key)
                    seen["steps"].add(date_key)
                    save_upload_log(upload_log)
                    print(f"Steps:   {step_count:>6}         {date_key}")

                if distance > 0.0 and date_key not in upload_log["distance"] and date_key not in seen["distance"]:
                    push_point(service, DATA_SOURCE_DISTANCE, start_ns, end_ns,
                               "com.google.distance.delta", {"fpVal": distance})
                    upload_log["distance"].add(date_key)
                    seen["distance"].add(date_key)
                    save_upload_log(upload_log)
                    print(f"Distance:{distance:>9.1f} m      {date_key}")

                if calorie > 0.0 and date_key not in upload_log["calories"] and date_key not in seen["calories"]:
                    push_point(service, DATA_SOURCE_CALORIES, start_ns, end_ns,
                               "com.google.calories.expended", {"fpVal": calorie})
                    upload_log["calories"].add(date_key)
                    seen["calories"].add(date_key)
                    save_upload_log(upload_log)
                    print(f"Calories:{calorie:>9.1f} kcal   {date_key}")

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

    print(f"Found {len(files)} CSVs.")
    upload_log = load_upload_log()
    seen = {}
    for file in files:
        upload_file(service, file, seen, upload_log)


if __name__ == "__main__":
    service = get_fit_service()
    upload_all_day_summaries(service)
